"""Pydantic contracts for structured LLM output and internal DTOs.

Every artefact that crosses a trust boundary (LLM -> application, file -> DB)
is validated here before it is allowed further into the system.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class AssuranceStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    WEAK_SUPPORT = "WEAK_SUPPORT"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


class ClaimType(str, Enum):
    FACT = "fact"
    CONCERN = "potential_concern"
    MITIGATION = "mitigation"
    MISSING_EVIDENCE = "missing_evidence"


class Severity(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    INFORMATIONAL = "informational"


class ReviewDecision(str, Enum):
    ACCEPTED = "accepted"
    EDITED_ACCEPTED = "edited_accepted"
    REJECTED = "rejected"
    MORE_EVIDENCE_REQUESTED = "more_evidence_requested"


class CaseStatus(str, Enum):
    AWAITING_ANALYSIS = "Awaiting AI Analysis"
    AWAITING_REVIEW = "Awaiting Human Review"
    UNDER_REVIEW = "Under Review"
    REVIEW_COMPLETE = "Review Complete"


class RecommendationState(str, Enum):
    """The only recommendations this system is permitted to produce.

    Deliberately excludes APPROVE / DENY / GRANT / REJECT: CaseBrief supports
    an adjudicator's decision, it does not make one. Ordered by escalation, so
    `max()` over a set of triggers yields the most conservative outcome.
    """

    PROCEED_TO_STANDARD_REVIEW = "PROCEED_TO_STANDARD_REVIEW"
    REQUEST_ADDITIONAL_INFORMATION = "REQUEST_ADDITIONAL_INFORMATION"
    ESCALATE_FOR_ENHANCED_REVIEW = "ESCALATE_FOR_ENHANCED_REVIEW"

    @property
    def rank(self) -> int:
        return _RECOMMENDATION_RANK[self.value]

    @property
    def display(self) -> str:
        return _RECOMMENDATION_DISPLAY[self.value]


_RECOMMENDATION_RANK = {
    RecommendationState.PROCEED_TO_STANDARD_REVIEW.value: 0,
    RecommendationState.REQUEST_ADDITIONAL_INFORMATION.value: 1,
    RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW.value: 2,
}

_RECOMMENDATION_DISPLAY = {
    RecommendationState.PROCEED_TO_STANDARD_REVIEW.value: "Proceed to Standard Review",
    RecommendationState.REQUEST_ADDITIONAL_INFORMATION.value: "Request Additional Information",
    RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW.value: "Escalate for Enhanced Review",
}


def most_conservative(states: List["RecommendationState"]) -> "RecommendationState":
    """The highest-escalation state in a set; PROCEED when the set is empty."""
    if not states:
        return RecommendationState.PROCEED_TO_STANDARD_REVIEW
    return max(states, key=lambda state: state.rank)


class ConcernLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

    @property
    def rank(self) -> int:
        return {"NONE": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3}[self.value]


class EvidenceCategory(str, Enum):
    """The standing categories a completed investigation package is assessed on."""

    FINANCIAL = "financial"
    EMPLOYMENT = "employment"
    FOREIGN_TRAVEL = "foreign_travel"
    IDENTITY_BACKGROUND = "identity_background"
    MONITORING = "monitoring"
    LEGAL_CONDUCT = "legal_conduct"
    DOCUMENTATION = "documentation"


class AdjudicatorAction(str, Enum):
    PROCEED = "proceed"
    REQUEST_MORE_INFORMATION = "request_more_information"
    ESCALATE = "escalate"

    @property
    def aligned_recommendation(self) -> RecommendationState:
        return {
            AdjudicatorAction.PROCEED: RecommendationState.PROCEED_TO_STANDARD_REVIEW,
            AdjudicatorAction.REQUEST_MORE_INFORMATION: RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
            AdjudicatorAction.ESCALATE: RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW,
        }[self]


class ActorType(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


# ---------------------------------------------------------------------------
# Lenient enum coercion
# ---------------------------------------------------------------------------
def _coerce(value: Any, enum_cls: Any, default: Any) -> Any:
    """Map a model-supplied string onto an enum, falling back to `default`.

    A live model occasionally invents a plausible-but-unlisted value
    ("informational" for a claim type). Rejecting the whole payload for one
    stray label throws away fifteen good claims to punish one bad label, so
    unknown values degrade to a safe default instead. The recommendation state
    is deliberately *not* coerced — see `_coerce_state`.
    """
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        candidate = value.strip().lower().replace(" ", "_").replace("-", "_")
        for member in enum_cls:
            if member.value.lower() == candidate:
                return member
    return default


def _coerce_state(value: Any) -> Optional["RecommendationState"]:
    """Unknown recommendation states resolve to None, never to a guess.

    Guessing here would invent a decision-support outcome the model did not
    make. None simply means "the model proposed nothing usable", and the
    deterministic engine decides alone.
    """
    if isinstance(value, RecommendationState):
        return value
    if isinstance(value, str):
        candidate = value.strip().upper().replace(" ", "_").replace("-", "_")
        for member in RecommendationState:
            if member.value == candidate:
                return member
    return None


# ---------------------------------------------------------------------------
# Structured LLM output contract (what the model must return)
# ---------------------------------------------------------------------------
class KeyFinding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    finding: str = Field(min_length=3)
    category: str = "general"
    severity: Severity = Severity.INFORMATIONAL
    source_ids: List[str] = Field(default_factory=list)

    @field_validator("severity", mode="before")
    @classmethod
    def _lenient_severity(cls, v: Any) -> Any:
        return _coerce(v, Severity, Severity.INFORMATIONAL)


class GeneratedClaim(BaseModel):
    """A single factual assertion made by the model, with its own citations."""

    model_config = ConfigDict(extra="ignore")

    claim_text: str = Field(min_length=3)
    claim_type: ClaimType = ClaimType.FACT
    source_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.5

    @field_validator("claim_type", mode="before")
    @classmethod
    def _lenient_claim_type(cls, v: Any) -> Any:
        return _coerce(v, ClaimType, ClaimType.FACT)

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class PotentialConflict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str
    source_ids: List[str] = Field(default_factory=list)
    conflicting_field: str = "unspecified"


class CaseAnalysisOutput(BaseModel):
    """The full structured response the LLM is required to produce."""

    model_config = ConfigDict(extra="ignore")

    # Two names for the same prose. `executive_case_assessment` is what
    # FINAL_CASE_ASSESSMENT_V1 asks for and what the brief renders;
    # `executive_summary` is the narrative-view field kept from the earlier
    # prompt. A live model returns only what the prompt names, so whichever
    # arrives fills the other rather than failing validation.
    executive_summary: str = ""
    key_findings: List[KeyFinding] = Field(default_factory=list)
    claims: List[GeneratedClaim] = Field(default_factory=list)
    mitigating_information: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    potential_conflicts: List[PotentialConflict] = Field(default_factory=list)
    requires_human_review: bool = True

    # The decision-ready brief the model drafts. The recommendation state it
    # proposes is advisory: the deterministic engine in
    # `src.assurance.recommendation_engine` decides the state that ships.
    proposed_recommendation: Optional[RecommendationState] = None
    proposed_concern_level: Optional[ConcernLevel] = None

    @field_validator("proposed_recommendation", mode="before")
    @classmethod
    def _lenient_state(cls, v: Any) -> Any:
        return _coerce_state(v)

    @field_validator("proposed_concern_level", mode="before")
    @classmethod
    def _lenient_concern(cls, v: Any) -> Any:
        return _coerce(v, ConcernLevel, None) if v is not None else None
    executive_case_assessment: str = ""
    why_this_recommendation: List[RecommendationReason] = Field(default_factory=list)
    factor_details: List[MitigatingFactor] = Field(default_factory=list)
    concern_details: List[RemainingConcern] = Field(default_factory=list)
    what_could_change_recommendation: List[str] = Field(default_factory=list)

    @field_validator("requires_human_review")
    @classmethod
    def _always_true(cls, v: bool) -> bool:
        # Non-negotiable product rule: no output is ever auto-approved.
        return True

    @model_validator(mode="after")
    def _mirror_assessment_prose(self) -> "CaseAnalysisOutput":
        if not self.executive_summary and self.executive_case_assessment:
            self.executive_summary = self.executive_case_assessment
        elif not self.executive_case_assessment and self.executive_summary:
            self.executive_case_assessment = self.executive_summary
        return self


# ---------------------------------------------------------------------------
# Decision-ready brief: the primary product output
# ---------------------------------------------------------------------------
class RecommendationReason(BaseModel):
    """One evidence-backed reason the recommendation is what it is."""

    model_config = ConfigDict(extra="ignore")

    # Stable within an analysis, so navigation can return the adjudicator to the
    # reason they left from rather than to the top of the brief.
    reason_id: str = ""
    reason: str = Field(min_length=5)
    category: EvidenceCategory = EvidenceCategory.DOCUMENTATION
    importance: Severity = Severity.MODERATE

    @field_validator("category", mode="before")
    @classmethod
    def _lenient_category(cls, v: Any) -> Any:
        return _coerce(v, EvidenceCategory, EvidenceCategory.DOCUMENTATION)

    @field_validator("importance", mode="before")
    @classmethod
    def _lenient_importance(cls, v: Any) -> Any:
        return _coerce(v, Severity, Severity.MODERATE)
    source_ids: List[str] = Field(default_factory=list)
    evidence_status: AssuranceStatus = AssuranceStatus.WEAK_SUPPORT
    evidence: List["EvidenceLink"] = Field(default_factory=list)
    verification_score: float = 0.0


class MitigatingFactor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    factor: str = Field(min_length=5)
    category: EvidenceCategory = EvidenceCategory.DOCUMENTATION
    source_ids: List[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def _lenient_category(cls, v: Any) -> Any:
        return _coerce(v, EvidenceCategory, EvidenceCategory.DOCUMENTATION)
    evidence: List["EvidenceLink"] = Field(default_factory=list)
    evidence_status: AssuranceStatus = AssuranceStatus.WEAK_SUPPORT


class RemainingConcern(BaseModel):
    """Adverse information that survives into the brief regardless of outcome."""

    model_config = ConfigDict(extra="ignore")

    concern: str = Field(min_length=5)
    category: EvidenceCategory = EvidenceCategory.DOCUMENTATION
    severity: Severity = Severity.MODERATE

    @field_validator("category", mode="before")
    @classmethod
    def _lenient_category(cls, v: Any) -> Any:
        return _coerce(v, EvidenceCategory, EvidenceCategory.DOCUMENTATION)

    @field_validator("severity", mode="before")
    @classmethod
    def _lenient_severity(cls, v: Any) -> Any:
        return _coerce(v, Severity, Severity.MODERATE)
    mitigation: str = ""
    human_review_consideration: str = ""
    source_ids: List[str] = Field(default_factory=list)
    evidence: List["EvidenceLink"] = Field(default_factory=list)
    is_material: bool = False


class CategoryAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: EvidenceCategory
    concern_level: ConcernLevel = ConcernLevel.NONE
    conclusion: str = ""
    mitigated: bool = False
    evidence_count: int = 0
    supporting_claims: int = 0
    mitigating_factors: List[str] = Field(default_factory=list)
    unresolved_concerns: List[str] = Field(default_factory=list)
    contradictions: int = 0
    unsupported_claims: int = 0
    evidence_completeness: float = 1.0

    @property
    def label(self) -> str:
        base = f"{self.concern_level.value.title()} concern"
        if self.concern_level == ConcernLevel.NONE:
            base = "No concern identified"
        return f"{base} — mitigated" if self.mitigated else base


class FinalCaseAssessment(BaseModel):
    """The decision-ready adjudicator brief."""

    model_config = ConfigDict(extra="ignore")

    overall_recommendation: RecommendationState = (
        RecommendationState.REQUEST_ADDITIONAL_INFORMATION
    )
    overall_concern_level: ConcernLevel = ConcernLevel.MODERATE
    recommendation_confidence: float = 0.5
    executive_case_assessment: str = Field(default="", min_length=0)
    why_this_recommendation: List[RecommendationReason] = Field(default_factory=list)
    mitigating_factors: List[MitigatingFactor] = Field(default_factory=list)
    remaining_concerns: List[RemainingConcern] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    potential_contradictions: List[str] = Field(default_factory=list)
    what_could_change_recommendation: List[str] = Field(default_factory=list)
    category_assessments: List[CategoryAssessment] = Field(default_factory=list)
    material_unresolved_issues: int = 0
    model_proposed_recommendation: Optional[RecommendationState] = None
    engine_recommendation: Optional[RecommendationState] = None
    engine_rationale: List[str] = Field(default_factory=list)
    requires_human_decision: bool = True

    @field_validator("recommendation_confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @field_validator("requires_human_decision")
    @classmethod
    def _always_true(cls, v: bool) -> bool:
        # Non-negotiable: the adjudicator is the decision-maker.
        return True

    @property
    def model_agreed_with_engine(self) -> Optional[bool]:
        """Did the model and the evidence rules reach the same state?

        Compared against the *engine's* state, not the state that shipped. When
        the model is the more conservative of the two its proposal becomes the
        shipped state, and comparing against that would report agreement for a
        genuine divergence — hiding the reconciliation notice precisely when the
        adjudicator most needs to see it.
        """
        if self.model_proposed_recommendation is None:
            return None
        reference = self.engine_recommendation or self.overall_recommendation
        return self.model_proposed_recommendation == reference


# ---------------------------------------------------------------------------
# Retrieval / evidence DTOs
# ---------------------------------------------------------------------------
class SourceType(str, Enum):
    DOCUMENT = "document"
    CASE_HISTORY = "case_history"


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str
    chunk_id: str
    case_id: str = ""
    source_type: SourceType = SourceType.DOCUMENT
    document_id: str = ""
    document_ref: str = ""
    document_name: str = ""
    document_type: str = ""
    document_date: str = ""
    event_id: str = ""
    event_date: str = ""
    event_type: str = ""
    chunk_index: int = 0
    content: str
    score: float = 0.0

    @property
    def display_name(self) -> str:
        return self.document_name or self.event_type.replace("_", " ").title()


class EvidenceLink(BaseModel):
    """A citation with everything navigation needs, structurally.

    The destination is carried as data — `source_type` plus the document or
    event identifier — so the UI never infers where to go by parsing an ID.
    """

    model_config = ConfigDict(extra="ignore")

    source_id: str
    chunk_id: str
    case_id: str = ""
    source_type: SourceType = SourceType.DOCUMENT
    document_id: str = ""
    document_ref: str = ""
    document_name: str = ""
    document_date: str = ""
    event_id: str = ""
    event_date: str = ""
    event_type: str = ""
    evidence_text: str
    relevance_score: float
    cited_by_model: bool = False

    @property
    def is_history(self) -> bool:
        return self.source_type == SourceType.CASE_HISTORY

    @property
    def display_name(self) -> str:
        if self.is_history:
            return self.document_name or self.event_type.replace("_", " ").title()
        return self.document_name

    @property
    def display_date(self) -> str:
        return self.event_date if self.is_history else self.document_date


class ValidatedClaim(BaseModel):
    """A model claim after the assurance pipeline has scored it."""

    model_config = ConfigDict(extra="ignore")

    claim_text: str
    claim_type: ClaimType
    assurance_status: AssuranceStatus
    confidence_score: float
    semantic_score: float = 0.0
    retrieval_score: float = 0.0
    entailment_score: float = 0.0
    model_confidence: float = 0.5
    evidence: List[EvidenceLink] = Field(default_factory=list)
    rationale: str = ""

    @property
    def is_problematic(self) -> bool:
        return self.assurance_status in {
            AssuranceStatus.UNSUPPORTED,
            AssuranceStatus.CONTRADICTED,
        }


class ContradictionFlag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conflicting_field: str
    description: str
    source_a_id: str
    source_a_document: str
    source_a_text: str
    source_b_id: str
    source_b_document: str
    source_b_text: str
    confidence: float
    detector: str = "heuristic"


class AssuranceMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")

    groundedness: float = 0.0
    evidence_coverage: float = 0.0
    unsupported_claim_rate: float = 0.0
    contradiction_rate: float = 0.0
    source_diversity: float = 0.0
    total_claims: int = 0
    supported_claims: int = 0
    weak_claims: int = 0
    unsupported_claims: int = 0
    contradicted_claims: int = 0
    reviewer_acceptance: Optional[float] = None


class AnalysisBundle(BaseModel):
    """Everything the review UI needs for one analysis run."""

    model_config = ConfigDict(extra="ignore")

    analysis_id: str
    case_id: str
    case_number: str
    model_name: str
    prompt_version: str
    generated_at: datetime
    latency_ms: int = 0
    demo_mode: bool = True
    output: CaseAnalysisOutput
    claims: List[ValidatedClaim] = Field(default_factory=list)
    contradictions: List[ContradictionFlag] = Field(default_factory=list)
    metrics: AssuranceMetrics = Field(default_factory=AssuranceMetrics)
    assessment: "FinalCaseAssessment" = Field(default_factory=lambda: FinalCaseAssessment())
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Case-file DTOs (validate synthetic data on load)
# ---------------------------------------------------------------------------
class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: str
    label: str
    detail: str = ""
    category: str = "general"


class HistoryEventView(BaseModel):
    """One case-history event as the UI and navigation layer see it."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_ref: str
    event_date: str
    event_type: str
    category: str = "general"
    label: str = ""
    detail: str = ""
    source_id: str = ""
    chunk_id: str = ""


class CaseDocumentSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file: str
    document_name: str
    document_type: str


class CaseMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case_number: str
    applicant_name: str
    slug: str
    status: CaseStatus = CaseStatus.AWAITING_ANALYSIS
    key_signal: str = ""
    scenario: str = ""
    opened_on: str = ""
    documents: List[CaseDocumentSpec] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    known_contradictions: List[Dict[str, str]] = Field(default_factory=list)
