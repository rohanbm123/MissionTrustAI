"""Overall case recommendation synthesis.

The model drafts the narrative. This module decides the recommendation *state*,
deterministically, from what the assurance pipeline actually established about
the evidence.

Why a deterministic policy layer over a probabilistic one:

* **Evidence sensitivity.** The recommendation must move when material evidence
  moves. A rule fed by validated claims, contradiction flags and missing-evidence
  findings does that reliably; a language model asked the same question may not.
* **Auditability.** Every state change carries a named trigger and the source IDs
  behind it, so an adjudicator can see *why* the system escalated.
* **Conservatism.** Where the model and the engine disagree, the more escalated
  of the two ships, and the divergence is recorded rather than hidden.

The rules are explicitly **not** an average of category risk scores. A single
material unresolved contradiction escalates a case whose every other category is
clean, because that is how a careful human reads a file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from src.models.schemas import (
    AssuranceStatus,
    CaseAnalysisOutput,
    ClaimType,
    CategoryAssessment,
    ConcernLevel,
    ContradictionFlag,
    EvidenceCategory,
    EvidenceLink,
    FinalCaseAssessment,
    MitigatingFactor,
    RecommendationReason,
    RecommendationState,
    RemainingConcern,
    Severity,
    ValidatedClaim,
    most_conservative,
)

# --- tuning knobs (prototype heuristics; documented in the README) ----------
MATERIAL_CONTRADICTION_CONFIDENCE = 0.70
# Detectors whose output is verifiable and unit-tested, and may therefore drive
# an escalation. Matched by prefix so detector versions ("heuristic-field-value-v1")
# stay deterministic. Anything unrecognised is treated as advisory: under-escalating
# on an unknown detector is safer than reopening the model's side door.
DETERMINISTIC_DETECTOR_PREFIX = "heuristic"


def is_deterministic(flag: ContradictionFlag) -> bool:
    return (flag.detector or "").startswith(DETERMINISTIC_DETECTOR_PREFIX)
VERIFIABLE_STATUSES = {AssuranceStatus.SUPPORTED, AssuranceStatus.WEAK_SUPPORT}
MATERIAL_CONCERN_FLOOR = ConcernLevel.MODERATE
UNSUPPORTED_RATE_CEILING = 0.34  # within a material category

# Concern wording that describes *absent* evidence rather than adverse evidence.
# The distinction drives the escalate-vs-request decision: you escalate on what
# the file says, you request on what the file lacks.
ABSENCE_MARKERS = (
    "not received", "has not been received", "no record", "could not be verified",
    "unverified", "not verified", "not documented", "is not in the record",
    "not present", "no repayment agreement", "no written", "outstanding", "no response",
    "has no entry", "no entry", "remains unverified", "not been established", "unreconciled",
    "not yet", "is not documented", "no documentation", "no mitigating evidence",
)

CATEGORY_KEYWORDS: Dict[EvidenceCategory, Tuple[str, ...]] = {
    EvidenceCategory.MONITORING: (
        "monitoring alert", "continuous monitoring", "continuous evaluation", "alert cm-",
        "alert generated", "automated alert", "cm-8", "cm-2",
    ),
    EvidenceCategory.FINANCIAL: (
        "delinquen", "credit", "creditor", "collection", "balance", "repayment", "payment plan",
        "payment agreement", "financial", "debt", "judgment", "utilisation", "utilization",
        "trade line", "billing", "insurer", "servicer", "installment", "past due",
    ),
    EvidenceCategory.EMPLOYMENT: (
        "employ", "employer", "position", "payroll", "assignment", "staffing", "separation",
        "supervisor", "title", "reduction in force", "resignation", "workforce",
    ),
    EvidenceCategory.FOREIGN_TRAVEL: (
        "foreign travel", "travel", "trip", "border-crossing", "border crossing", "abroad",
        "foreign contact", "foreign national", "foreign government", "disclosure of travel",
    ),
    EvidenceCategory.LEGAL_CONDUCT: (
        "court", "citation", "criminal", "arrest", "charge", "infraction", "conviction",
        "docket", "probation", "ordinance", "legal",
    ),
    EvidenceCategory.IDENTITY_BACKGROUND: (
        "address", "residence", "resided", "lease", "landlord", "sublet", "identity",
        "developed reference", "reference interview", "mail-forwarding",
    ),
    EvidenceCategory.DOCUMENTATION: (
        "not in the record", "not received", "has not been received", "no record", "missing",
        "not present in the file", "not documented", "unverified", "could not be verified",
        "outstanding", "not yet", "has not been established",
    ),
}

CONTRADICTION_FIELD_CATEGORY: Dict[str, EvidenceCategory] = {
    "employment_end_date": EvidenceCategory.EMPLOYMENT,
    "employment_start_date": EvidenceCategory.EMPLOYMENT,
    "position_title": EvidenceCategory.EMPLOYMENT,
    "repayment_plan_effective_date": EvidenceCategory.FINANCIAL,
    "delinquency_reported_date": EvidenceCategory.FINANCIAL,
    "delinquent_amount": EvidenceCategory.FINANCIAL,
    "credit_utilisation": EvidenceCategory.FINANCIAL,
    "foreign_trip_count": EvidenceCategory.FOREIGN_TRAVEL,
    "residence_end_date": EvidenceCategory.IDENTITY_BACKGROUND,
}

CATEGORY_LABELS: Dict[EvidenceCategory, str] = {
    EvidenceCategory.FINANCIAL: "Financial",
    EvidenceCategory.EMPLOYMENT: "Employment",
    EvidenceCategory.FOREIGN_TRAVEL: "Foreign travel",
    EvidenceCategory.IDENTITY_BACKGROUND: "Identity and background",
    EvidenceCategory.MONITORING: "Monitoring",
    EvidenceCategory.LEGAL_CONDUCT: "Legal and conduct",
    EvidenceCategory.DOCUMENTATION: "Documentation completeness",
}

_WORD = re.compile(r"[a-z][a-z'-]+")


def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    return f"{count} {singular}" if count == 1 else f"{count} {plural or singular + 's'}"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify(text: str, default: EvidenceCategory = EvidenceCategory.DOCUMENTATION) -> EvidenceCategory:
    """Assign a passage of assessment text to an evidence category.

    Scored by longest-keyword match rather than first hit, so "continuous
    monitoring alert referencing the account" lands in monitoring, not financial.
    DOCUMENTATION is a fallback only: "nine months of residence history is
    unverified" is an identity finding that happens to use documentation
    vocabulary, and bucketing it as paperwork would hide it from the rules that
    care about identity concerns.
    """
    lowered = text.lower()
    best: Optional[Tuple[int, EvidenceCategory]] = None
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == EvidenceCategory.DOCUMENTATION:
            continue
        for keyword in keywords:
            if keyword in lowered and (best is None or len(keyword) > best[0]):
                best = (len(keyword), category)
    if best:
        return best[1]
    if any(keyword in lowered for keyword in CATEGORY_KEYWORDS[EvidenceCategory.DOCUMENTATION]):
        return EvidenceCategory.DOCUMENTATION
    return default


def category_for_contradiction(flag: ContradictionFlag) -> EvidenceCategory:
    known = CONTRADICTION_FIELD_CATEGORY.get(flag.conflicting_field)
    if known:
        return known
    return classify(f"{flag.conflicting_field} {flag.description}")


# ---------------------------------------------------------------------------
# Category assessment
# ---------------------------------------------------------------------------
@dataclass
class CategoryEvidence:
    """Everything the pipeline established about one category."""

    category: EvidenceCategory
    concerns: List[ValidatedClaim] = field(default_factory=list)
    mitigations: List[ValidatedClaim] = field(default_factory=list)
    facts: List[ValidatedClaim] = field(default_factory=list)
    contradictions: List[ContradictionFlag] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    finding_severity: Severity = Severity.INFORMATIONAL

    @property
    def all_claims(self) -> List[ValidatedClaim]:
        return self.concerns + self.mitigations + self.facts

    @property
    def unsupported(self) -> List[ValidatedClaim]:
        return [c for c in self.all_claims if c.assurance_status == AssuranceStatus.UNSUPPORTED]

    @property
    def verifiable_mitigations(self) -> List[ValidatedClaim]:
        return [c for c in self.mitigations if c.assurance_status in VERIFIABLE_STATUSES]

    @property
    def material_contradictions(self) -> List[ContradictionFlag]:
        """Conflicts strong enough to matter — and only from the heuristic detector.

        A conflict asserted by a language model is advisory, exactly like the
        recommendation a model proposes. Letting it escalate on its own hands the
        model a side door into the decision that the whole architecture exists to
        close: a live run flagged an $18,500 February balance against a $17,850
        May balance as a contradiction at 0.95 confidence, when the difference was
        two $325 payments. Model-declared conflicts still surface to the
        adjudicator and can still trigger an information request; they cannot
        escalate a case by themselves.
        """
        return [
            f
            for f in self.contradictions
            if f.confidence >= MATERIAL_CONTRADICTION_CONFIDENCE and is_deterministic(f)
        ]

    @property
    def advisory_contradictions(self) -> List[ContradictionFlag]:
        """Model-asserted conflicts: surfaced and actionable, but never escalating."""
        return [f for f in self.contradictions if not is_deterministic(f)]

    @property
    def cross_source_contradictions(self) -> List[ContradictionFlag]:
        """Two independent records disagreeing — the escalating kind.

        A conflict whose two sides come from the same passage is one record
        noting a discrepancy it already documents ("as reported by subject" vs
        "as confirmed by employer"). That is the investigation doing its job,
        not two sources secretly disagreeing.
        """
        return [
            f for f in self.material_contradictions if f.source_a_id != f.source_b_id
        ]

    @property
    def disclosed_discrepancies(self) -> List[ContradictionFlag]:
        return [f for f in self.material_contradictions if f.source_a_id == f.source_b_id]

    @property
    def adverse_concerns(self) -> List[ValidatedClaim]:
        """Concerns asserting something adverse, as opposed to noting a gap."""
        return [
            c
            for c in self.concerns
            if not any(marker in c.claim_text.lower() for marker in ABSENCE_MARKERS)
        ]


def derive_mitigation_claims(
    output: CaseAnalysisOutput, claim_index: Dict[str, List[ValidatedClaim]]
) -> List[ValidatedClaim]:
    """Treat the model's stated mitigating factors as mitigation evidence.

    `claim_type` is a label the model supplies, and a live model may never emit
    `mitigation` at all — one run typed every claim `fact` while putting the
    repayment plan in `factor_details`, exactly where the prompt asks for it.
    Reading only claim types made a fully-mitigated case look unmitigated. A
    factor counts only when it resolves to real, already-scored evidence.
    """
    derived: List[ValidatedClaim] = []
    seen = set()
    for factor in output.factor_details:
        key = factor.factor.strip().lower()[:90]
        if key in seen:
            continue
        links, status, score = _evidence_for(factor.source_ids, factor.factor, claim_index)
        if not links or status not in VERIFIABLE_STATUSES:
            continue
        seen.add(key)
        derived.append(
            ValidatedClaim(
                claim_text=factor.factor,
                claim_type=ClaimType.MITIGATION,
                assurance_status=status,
                confidence_score=score,
                evidence=links,
                rationale="Derived from the model's stated mitigating factors.",
            )
        )
    return derived


def gather_category_evidence(
    claims: Sequence[ValidatedClaim],
    contradictions: Sequence[ContradictionFlag],
    output: Optional[CaseAnalysisOutput] = None,
) -> Dict[EvidenceCategory, CategoryEvidence]:
    buckets: Dict[EvidenceCategory, CategoryEvidence] = {}

    def bucket(category: EvidenceCategory) -> CategoryEvidence:
        return buckets.setdefault(category, CategoryEvidence(category=category))

    for claim in claims:
        category = classify(claim.claim_text)
        target = bucket(category)
        if claim.claim_type.value == "potential_concern":
            target.concerns.append(claim)
        elif claim.claim_type.value == "mitigation":
            target.mitigations.append(claim)
        else:
            target.facts.append(claim)

    for flag in contradictions:
        bucket(category_for_contradiction(flag)).contradictions.append(flag)

    if output is not None:
        for finding in output.key_findings:
            category = classify(f"{finding.category} {finding.finding}")
            target = bucket(category)
            if finding.severity.value != "informational":
                order = {"low": 1, "moderate": 2, "high": 3, "informational": 0}
                if order[finding.severity.value] > order[target.finding_severity.value]:
                    target.finding_severity = finding.severity
        for item in output.missing_information:
            bucket(classify(item, EvidenceCategory.DOCUMENTATION)).missing.append(item)

    return buckets


def assess_category(evidence: CategoryEvidence) -> CategoryAssessment:
    """Concern level, mitigation status and completeness for one category."""
    severity_rank = {"informational": 0, "low": 1, "moderate": 2, "high": 3}
    level = ConcernLevel.NONE

    if evidence.concerns:
        level = ConcernLevel.MODERATE if len(evidence.concerns) == 1 else ConcernLevel.HIGH
    if severity_rank[evidence.finding_severity.value] >= 3:
        level = ConcernLevel.HIGH
    elif severity_rank[evidence.finding_severity.value] == 2 and level.rank < ConcernLevel.MODERATE.rank:
        level = ConcernLevel.MODERATE
    elif severity_rank[evidence.finding_severity.value] == 1 and level == ConcernLevel.NONE:
        level = ConcernLevel.LOW
    if evidence.material_contradictions and level.rank < ConcernLevel.HIGH.rank:
        level = ConcernLevel.HIGH
    elif evidence.contradictions and level.rank < ConcernLevel.MODERATE.rank:
        level = ConcernLevel.MODERATE

    verifiable = evidence.verifiable_mitigations
    # A concern is mitigated when verifiable mitigating evidence exists. An
    # unresolved conflict does not erase that evidence; it is surfaced by its own
    # rule and its own entry in the remaining-concerns list.
    mitigated = bool(verifiable) and level != ConcernLevel.NONE
    # But a gap cannot be mitigated, only filled. Where every concern in a
    # category is an absence of evidence, other evidence in the same category
    # does not answer it — the missing record still has to be produced.
    if evidence.concerns and not evidence.adverse_concerns:
        mitigated = False

    unresolved: List[str] = []
    for flag in evidence.contradictions:
        unresolved.append(
            f"Unresolved conflict on {flag.conflicting_field.replace('_', ' ')} "
            f"({flag.source_a_document} vs {flag.source_b_document})."
        )
    for claim in evidence.unsupported:
        unresolved.append(f"Unsupported statement requiring verification: {claim.claim_text}")
    unresolved.extend(evidence.missing)
    if level.rank >= MATERIAL_CONCERN_FLOOR.rank and not verifiable:
        unresolved.append("No verifiable mitigating evidence is present for this category.")

    total_claims = len(evidence.all_claims)
    completeness = 1.0
    if total_claims:
        completeness -= len(evidence.unsupported) / total_claims
    completeness -= 0.15 * len(evidence.missing)
    completeness = round(max(0.0, min(1.0, completeness)), 3)

    return CategoryAssessment(
        category=evidence.category,
        concern_level=level,
        conclusion=_category_conclusion(evidence, level, mitigated),
        mitigated=mitigated,
        evidence_count=sum(len(c.evidence) for c in evidence.all_claims),
        supporting_claims=total_claims,
        mitigating_factors=[c.claim_text for c in verifiable],
        unresolved_concerns=unresolved,
        contradictions=len(evidence.contradictions),
        unsupported_claims=len(evidence.unsupported),
        evidence_completeness=completeness,
    )


def _category_conclusion(
    evidence: CategoryEvidence, level: ConcernLevel, mitigated: bool
) -> str:
    label = CATEGORY_LABELS[evidence.category]
    if level == ConcernLevel.NONE:
        return f"{label}: no concern identified in the package."
    if evidence.material_contradictions:
        return f"{label}: sources disagree on a material fact; the conflict is unresolved."
    if mitigated:
        return f"{label}: concern identified and offset by verifiable mitigating evidence."
    if evidence.missing:
        return f"{label}: concern identified; evidence needed to resolve it is not in the package."
    return f"{label}: concern identified without verifiable mitigating evidence."


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------
@dataclass
class Trigger:
    state: RecommendationState
    rule: str
    explanation: str
    category: Optional[EvidenceCategory] = None
    source_ids: List[str] = field(default_factory=list)


def evaluate_rules(
    assessments: Dict[EvidenceCategory, CategoryAssessment],
    evidence: Dict[EvidenceCategory, CategoryEvidence],
    claims: Sequence[ValidatedClaim],
) -> List[Trigger]:
    """Evidence-sensitive rules, evaluated independently and then combined.

    Each rule that fires proposes a state; the most escalated proposal wins. No
    averaging: one material trigger is enough.
    """
    triggers: List[Trigger] = []
    material = {
        category
        for category, assessment in assessments.items()
        if assessment.concern_level.rank >= MATERIAL_CONCERN_FLOOR.rank
    }

    # --- escalation rules -------------------------------------------------
    for category in material:
        bucket = evidence[category]
        for flag in bucket.cross_source_contradictions:
            triggers.append(
                Trigger(
                    RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW,
                    "material_contradiction",
                    (
                        f"{CATEGORY_LABELS[category]}: two independent records disagree on "
                        f"{flag.conflicting_field.replace('_', ' ')} "
                        f"({flag.source_a_document} vs {flag.source_b_document}) and the package "
                        "contains nothing that resolves the conflict."
                    ),
                    category,
                    [flag.source_a_id, flag.source_b_id],
                )
            )

    for category, assessment in assessments.items():
        bucket = evidence[category]
        if assessment.concern_level != ConcernLevel.HIGH or assessment.mitigated:
            continue
        if bucket.adverse_concerns:
            triggers.append(
                Trigger(
                    RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW,
                    "unmitigated_high_concern",
                    (
                        f"{CATEGORY_LABELS[category]}: "
                        f"{_plural(len(bucket.adverse_concerns), 'adverse finding')} with no "
                        "verifiable mitigating evidence in the package."
                    ),
                    category,
                    _source_ids(bucket.adverse_concerns),
                )
            )
        else:
            # High concern built entirely out of gaps: the file lacks evidence
            # rather than containing something damaging. Ask for the evidence.
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "high_concern_pending_evidence",
                    (
                        f"{CATEGORY_LABELS[category]}: the concern rests on evidence that is "
                        "absent from the package rather than on adverse findings."
                    ),
                    category,
                    _source_ids(bucket.concerns),
                )
            )

    unmitigated_material = [
        category
        for category in material
        if not assessments[category].mitigated and evidence[category].adverse_concerns
    ]
    if len(unmitigated_material) >= 2:
        triggers.append(
            Trigger(
                RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW,
                "multiple_unmitigated_concerns",
                (
                    "Unmitigated adverse findings appear in "
                    + ", ".join(sorted(CATEGORY_LABELS[c] for c in unmitigated_material))
                    + " — the combination warrants enhanced review even though no single "
                    "category is decisive."
                ),
            )
        )

    contradicted = [c for c in claims if c.assurance_status == AssuranceStatus.CONTRADICTED]
    if contradicted:
        triggers.append(
            Trigger(
                RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW,
                "contradicted_claim",
                (
                    f"{_plural(len(contradicted), 'assessment statement')} contradicted by the "
                    "very evidence retrieved to support them."
                ),
                None,
                _source_ids(contradicted),
            )
        )

    # --- request-information rules ---------------------------------------
    for category in material:
        assessment = assessments[category]
        bucket = evidence[category]
        claimed, verifiable = bucket.mitigations, bucket.verifiable_mitigations

        if claimed and not verifiable:
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "unverifiable_mitigation",
                    (
                        f"{CATEGORY_LABELS[category]}: mitigation is asserted but the supporting "
                        "document is not in the package, so the mitigation cannot be verified."
                    ),
                    category,
                    _source_ids(claimed),
                )
            )
        if not claimed and assessment.concern_level == ConcernLevel.MODERATE:
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "unresolved_moderate_concern",
                    (
                        f"{CATEGORY_LABELS[category]}: a moderate concern has no mitigating "
                        "evidence and no resolving document in the package."
                    ),
                    category,
                    _source_ids(bucket.concerns),
                )
            )
        for flag in bucket.disclosed_discrepancies:
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "disclosed_discrepancy",
                    (
                        f"{CATEGORY_LABELS[category]}: the record documents a discrepancy on "
                        f"{flag.conflicting_field.replace('_', ' ')} between what the applicant "
                        "reported and what was confirmed; the residue is not yet closed."
                    ),
                    category,
                    [flag.source_a_id],
                )
            )
        if assessment.mitigated:
            continue  # the remaining rules describe gaps a verified mitigation already closes

        if bucket.missing:
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "material_missing_information",
                    (
                        f"{CATEGORY_LABELS[category]}: evidence needed to close this concern is "
                        f"absent — {bucket.missing[0]}"
                    ),
                    category,
                )
            )
        total = len(bucket.all_claims)
        if total and len(bucket.unsupported) / total > UNSUPPORTED_RATE_CEILING:
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "unsupported_material_statements",
                    (
                        f"{CATEGORY_LABELS[category]}: "
                        f"{len(bucket.unsupported)} of {total} statements in this category could "
                        "not be traced to evidence in the package."
                    ),
                    category,
                )
            )
        for flag in bucket.contradictions:
            if flag.confidence < MATERIAL_CONTRADICTION_CONFIDENCE:
                triggers.append(
                    Trigger(
                        RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                        "possible_conflict",
                        (
                            f"{CATEGORY_LABELS[category]}: a possible conflict on "
                            f"{flag.conflicting_field.replace('_', ' ')} needs clarification."
                        ),
                        category,
                        [flag.source_a_id, flag.source_b_id],
                    )
                )

    # An assessed category whose evidence has gone missing needs the evidence
    # back, even when the concern itself was minor. This is what separates
    # "a travel document was removed from a financial case" (no concern in that
    # category, no reaction) from "the court record was removed from the case
    # that turns on it" (the assessed category lost its basis).
    for category, assessment in assessments.items():
        if assessment.concern_level == ConcernLevel.NONE or category in material:
            continue
        bucket = evidence[category]
        total = len(bucket.all_claims)
        if total and len(bucket.unsupported) / total > UNSUPPORTED_RATE_CEILING:
            triggers.append(
                Trigger(
                    RecommendationState.REQUEST_ADDITIONAL_INFORMATION,
                    "evidence_gap_in_assessed_category",
                    (
                        f"{CATEGORY_LABELS[category]}: "
                        f"{len(bucket.unsupported)} of {total} statements in the category this "
                        "case turns on could not be traced to any document in the package."
                    ),
                    category,
                )
            )

    return triggers


def describe_conflict_sources(flag: ContradictionFlag) -> str:
    """Human phrasing for where a conflict sits.

    Both sides of a disclosed discrepancy come from the same record, so naming
    the document twice ("Employment History vs Employment History") reads like a
    rendering fault rather than a finding.
    """
    if flag.source_a_id == flag.source_b_id or flag.source_a_document == flag.source_b_document:
        return f"within {flag.source_a_document}, between what was reported and what was confirmed"
    return f"{flag.source_a_document} vs {flag.source_b_document}"


def _source_ids(claims: Iterable[ValidatedClaim]) -> List[str]:
    ids: List[str] = []
    for claim in claims:
        for link in claim.evidence[:2]:
            if link.source_id not in ids:
                ids.append(link.source_id)
    return ids


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------
def synthesize(
    output: CaseAnalysisOutput,
    claims: Sequence[ValidatedClaim],
    contradictions: Sequence[ContradictionFlag],
) -> FinalCaseAssessment:
    """Produce the decision-ready brief from validated pipeline output."""
    claim_index = _claim_index(claims)
    scored_claims = list(claims) + derive_mitigation_claims(output, claim_index)
    evidence = gather_category_evidence(scored_claims, contradictions, output)
    assessments = {category: assess_category(bucket) for category, bucket in evidence.items()}
    triggers = evaluate_rules(assessments, evidence, scored_claims)

    engine_state = most_conservative([t.state for t in triggers])
    model_state = output.proposed_recommendation
    final_state = (
        most_conservative([engine_state, model_state]) if model_state else engine_state
    )

    deciding = [t for t in triggers if t.state == final_state]
    if not deciding and model_state == final_state and engine_state != final_state:
        # The model was the more conservative of the two; say so plainly rather
        # than reporting "no rule fired" next to an escalated recommendation.
        deciding = []
    rationale = [f"[{t.rule}] {t.explanation}" for t in deciding]
    if not deciding:
        rationale.append(
            "[no_trigger] No escalation or information-request rule fired: every identified "
            "concern has verifiable mitigating evidence and no material conflict remains."
        )
    if model_state and model_state != engine_state:
        rationale.append(
            f"[model_divergence] The model proposed {model_state.value}; the evidence rules "
            f"produced {engine_state.value}. The more conservative state ships and the "
            "divergence is recorded."
        )

    reasons = _build_reasons(output, deciding, claim_index, final_state)
    factors = _build_factors(output, evidence, claim_index)
    concerns = _build_concerns(output, evidence, assessments, claim_index)
    material_issues = sum(1 for concern in concerns if concern.is_material)

    concern_level = _overall_concern_level(assessments, final_state)
    confidence = _confidence(claims, contradictions, evidence, model_state, engine_state)

    return FinalCaseAssessment(
        overall_recommendation=final_state,
        engine_recommendation=engine_state,
        overall_concern_level=concern_level,
        recommendation_confidence=confidence,
        executive_case_assessment=output.executive_case_assessment or output.executive_summary,
        why_this_recommendation=reasons,
        mitigating_factors=factors,
        remaining_concerns=concerns,
        missing_information=list(output.missing_information),
        potential_contradictions=[flag.description for flag in contradictions],
        what_could_change_recommendation=_sensitivities(
            output, evidence, assessments, final_state
        ),
        category_assessments=[assessments[c] for c in sorted(assessments, key=lambda x: x.value)],
        material_unresolved_issues=material_issues,
        model_proposed_recommendation=model_state,
        engine_rationale=rationale,
        requires_human_decision=True,
    )


def _claim_index(claims: Sequence[ValidatedClaim]) -> Dict[str, List[ValidatedClaim]]:
    """Claims keyed by every source ID they cite, for reason → evidence lookup."""
    index: Dict[str, List[ValidatedClaim]] = {}
    for claim in claims:
        for link in claim.evidence:
            index.setdefault(link.source_id, []).append(claim)
    return index


def _evidence_for(
    source_ids: Sequence[str], text: str, claim_index: Dict[str, List[ValidatedClaim]]
) -> Tuple[List[EvidenceLink], AssuranceStatus, float]:
    """Resolve a reason's citations to real, already-scored evidence links."""
    links: List[EvidenceLink] = []
    statuses: List[ValidatedClaim] = []
    seen = set()
    for source_id in source_ids:
        for claim in claim_index.get(source_id, []):
            statuses.append(claim)
            for link in claim.evidence:
                if link.source_id == source_id and link.source_id not in seen:
                    seen.add(link.source_id)
                    links.append(link)

    if not links:
        # The cited passage did not survive validation; fall back to the best
        # claim that overlaps the reason's wording so the reason is still
        # traceable, and let its status speak for itself.
        best = _best_matching_claim(text, claim_index)
        if best:
            statuses.append(best)
            links.extend(best.evidence[:2])

    if not statuses:
        return links, AssuranceStatus.UNSUPPORTED, 0.0

    ranked = sorted(statuses, key=lambda c: c.confidence_score, reverse=True)
    return links, ranked[0].assurance_status, round(ranked[0].confidence_score, 4)


def _best_matching_claim(
    text: str, claim_index: Dict[str, List[ValidatedClaim]]
) -> Optional[ValidatedClaim]:
    tokens = set(_WORD.findall(text.lower()))
    if not tokens:
        return None
    best: Optional[Tuple[float, ValidatedClaim]] = None
    seen = set()
    for claims in claim_index.values():
        for claim in claims:
            if id(claim) in seen:
                continue
            seen.add(id(claim))
            claim_tokens = set(_WORD.findall(claim.claim_text.lower()))
            if not claim_tokens:
                continue
            overlap = len(tokens & claim_tokens) / len(tokens)
            if overlap > 0.34 and (best is None or overlap > best[0]):
                best = (overlap, claim)
    return best[1] if best else None


def _build_reasons(
    output: CaseAnalysisOutput,
    deciding: Sequence[Trigger],
    claim_index: Dict[str, List[ValidatedClaim]],
    final_state: RecommendationState,
) -> List[RecommendationReason]:
    """Engine triggers first, then the model's reasons that still hold."""
    reasons: List[RecommendationReason] = []

    for trigger in deciding:
        links, status, score = _evidence_for(trigger.source_ids, trigger.explanation, claim_index)
        reasons.append(
            RecommendationReason(
                reason=trigger.explanation,
                category=trigger.category or EvidenceCategory.DOCUMENTATION,
                importance=Severity.HIGH,
                source_ids=[link.source_id for link in links] or list(trigger.source_ids),
                evidence_status=status,
                evidence=links,
                verification_score=score,
            )
        )

    for drafted in output.why_this_recommendation:
        links, status, score = _evidence_for(drafted.source_ids, drafted.reason, claim_index)
        # A drafted reason that no longer traces to supported evidence is not a
        # reason any more. Dropping it keeps the brief coherent when evidence
        # changes underneath a cached narrative.
        if status == AssuranceStatus.UNSUPPORTED and final_state != RecommendationState.PROCEED_TO_STANDARD_REVIEW:
            continue
        reasons.append(
            RecommendationReason(
                reason=drafted.reason,
                category=drafted.category,
                importance=drafted.importance,
                source_ids=[link.source_id for link in links] or list(drafted.source_ids),
                evidence_status=status,
                evidence=links,
                verification_score=score,
            )
        )

    deduped: List[RecommendationReason] = []
    seen = set()
    for reason in reasons:
        key = reason.reason.strip().lower()[:90]
        if key not in seen:
            seen.add(key)
            deduped.append(reason)
    deduped = deduped[:7]
    for position, reason in enumerate(deduped, start=1):
        reason.reason_id = f"reason-{position}"
    return deduped


def _build_factors(
    output: CaseAnalysisOutput,
    evidence: Dict[EvidenceCategory, CategoryEvidence],
    claim_index: Dict[str, List[ValidatedClaim]],
) -> List[MitigatingFactor]:
    factors: List[MitigatingFactor] = []
    seen = set()

    for drafted in output.factor_details:
        links, status, _ = _evidence_for(drafted.source_ids, drafted.factor, claim_index)
        if status == AssuranceStatus.UNSUPPORTED:
            continue  # an unverifiable mitigation is not a mitigating factor
        key = drafted.factor.strip().lower()[:90]
        if key in seen:
            continue
        seen.add(key)
        factors.append(
            MitigatingFactor(
                factor=drafted.factor,
                category=drafted.category,
                source_ids=[link.source_id for link in links] or list(drafted.source_ids),
                evidence=links,
                evidence_status=status,
            )
        )

    for text in output.mitigating_information:
        key = text.strip().lower()[:90]
        if key in seen:
            continue
        links, status, _ = _evidence_for([], text, claim_index)
        if status == AssuranceStatus.UNSUPPORTED:
            continue
        seen.add(key)
        factors.append(
            MitigatingFactor(
                factor=text,
                category=classify(text),
                source_ids=[link.source_id for link in links],
                evidence=links,
                evidence_status=status,
            )
        )

    for bucket in evidence.values():
        for claim in bucket.verifiable_mitigations:
            key = claim.claim_text.strip().lower()[:90]
            if key in seen:
                continue
            seen.add(key)
            factors.append(
                MitigatingFactor(
                    factor=claim.claim_text,
                    category=bucket.category,
                    source_ids=[link.source_id for link in claim.evidence],
                    evidence=claim.evidence[:3],
                    evidence_status=claim.assurance_status,
                )
            )
    return factors[:8]


def _build_concerns(
    output: CaseAnalysisOutput,
    evidence: Dict[EvidenceCategory, CategoryEvidence],
    assessments: Dict[EvidenceCategory, CategoryAssessment],
    claim_index: Dict[str, List[ValidatedClaim]],
) -> List[RemainingConcern]:
    """Every surviving concern, whether or not the recommendation is positive."""
    concerns: List[RemainingConcern] = []
    seen = set()

    for drafted in output.concern_details:
        key = drafted.concern.strip().lower()[:90]
        if key in seen:
            continue
        seen.add(key)
        links, status, _ = _evidence_for(drafted.source_ids, drafted.concern, claim_index)
        assessment = assessments.get(drafted.category)
        concerns.append(
            RemainingConcern(
                concern=drafted.concern,
                category=drafted.category,
                severity=drafted.severity,
                mitigation=drafted.mitigation,
                human_review_consideration=drafted.human_review_consideration,
                source_ids=[link.source_id for link in links] or list(drafted.source_ids),
                evidence=links,
                is_material=bool(
                    assessment
                    and assessment.concern_level.rank >= MATERIAL_CONCERN_FLOOR.rank
                    and not assessment.mitigated
                ),
            )
        )

    for category, bucket in evidence.items():
        assessment = assessments[category]
        for flag in bucket.contradictions:
            key = f"conflict::{flag.conflicting_field}"
            if key in seen:
                continue
            seen.add(key)
            concerns.append(
                RemainingConcern(
                    concern=(
                        f"Sources disagree on {flag.conflicting_field.replace('_', ' ')}: "
                        f"{describe_conflict_sources(flag)}."
                    ),
                    category=category,
                    # Severity and materiality track what the flag can actually
                    # do. A model-declared conflict cannot escalate, so badging
                    # it "Material / High" would tell the adjudicator it carries
                    # weight the rules never gave it.
                    severity=Severity.HIGH
                    if flag in bucket.material_contradictions
                    else Severity.MODERATE,
                    mitigation="",
                    human_review_consideration=(
                        "Compare both source passages and determine which record governs."
                    ),
                    source_ids=[flag.source_a_id, flag.source_b_id],
                    evidence=[],
                    is_material=flag in bucket.material_contradictions,
                )
            )
        for claim in bucket.concerns:
            key = claim.claim_text.strip().lower()[:90]
            if key in seen:
                continue
            seen.add(key)
            concerns.append(
                RemainingConcern(
                    concern=claim.claim_text,
                    category=category,
                    severity=Severity.MODERATE if assessment.mitigated else Severity.HIGH,
                    mitigation=(
                        assessment.mitigating_factors[0] if assessment.mitigating_factors else ""
                    ),
                    human_review_consideration=(
                        "Confirm the mitigating evidence remains current."
                        if assessment.mitigated
                        else "No mitigating evidence is present; obtain or confirm it."
                    ),
                    source_ids=[link.source_id for link in claim.evidence],
                    evidence=claim.evidence[:3],
                    is_material=not assessment.mitigated
                    and assessment.concern_level.rank >= MATERIAL_CONCERN_FLOOR.rank,
                )
            )

    concerns.sort(key=lambda c: (not c.is_material, {"high": 0, "moderate": 1, "low": 2, "informational": 3}[c.severity.value]))
    return concerns[:10]


def _overall_concern_level(
    assessments: Dict[EvidenceCategory, CategoryAssessment], state: RecommendationState
) -> ConcernLevel:
    """Driven by unmitigated concern, not by the raw maximum across categories."""
    if state == RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW:
        return ConcernLevel.HIGH
    unmitigated = [a for a in assessments.values() if not a.mitigated]
    peak = max((a.concern_level for a in unmitigated), default=ConcernLevel.NONE)
    if state == RecommendationState.REQUEST_ADDITIONAL_INFORMATION:
        return ConcernLevel.MODERATE if peak.rank <= ConcernLevel.MODERATE.rank else peak
    # Proceeding: a mitigated concern is no longer outstanding, but a case that
    # had one is not the same as a case that never had one. NONE is reserved for
    # a package where no category raised a concern at all.
    if peak.rank >= ConcernLevel.MODERATE.rank:
        return ConcernLevel.LOW
    any_concern = any(a.concern_level != ConcernLevel.NONE for a in assessments.values())
    return ConcernLevel.LOW if any_concern else peak


def _confidence(
    claims: Sequence[ValidatedClaim],
    contradictions: Sequence[ContradictionFlag],
    evidence: Dict[EvidenceCategory, CategoryEvidence],
    model_state: Optional[RecommendationState],
    engine_state: RecommendationState,
) -> float:
    """Confidence in the *recommendation*, not in any individual statement."""
    confidence = 0.95
    total = len(claims) or 1
    unsupported = sum(1 for c in claims if c.assurance_status == AssuranceStatus.UNSUPPORTED)
    weak = sum(1 for c in claims if c.assurance_status == AssuranceStatus.WEAK_SUPPORT)

    confidence -= 0.30 * (unsupported / total)
    confidence -= 0.10 * (weak / total)
    confidence -= 0.04 * len(contradictions)
    confidence -= 0.03 * sum(len(bucket.missing) for bucket in evidence.values())
    if model_state and model_state != engine_state:
        confidence -= 0.05
    return round(max(0.10, min(0.99, confidence)), 4)


def _sensitivities(
    output: CaseAnalysisOutput,
    evidence: Dict[EvidenceCategory, CategoryEvidence],
    assessments: Dict[EvidenceCategory, CategoryAssessment],
    state: RecommendationState,
) -> List[str]:
    """What would move this recommendation, derived from real dependencies."""
    items: List[str] = []
    seen = set()

    def add(text: str) -> None:
        key = text.strip().lower()[:90]
        if key not in seen and text.strip():
            seen.add(key)
            items.append(text.strip())

    # Load-bearing mitigations: remove one and the recommendation moves.
    for category, bucket in evidence.items():
        if assessments[category].concern_level.rank < MATERIAL_CONCERN_FLOOR.rank:
            continue
        for claim in bucket.verifiable_mitigations[:2]:
            add(f"If this could not be verified: {claim.claim_text}")
        for flag in bucket.contradictions[:1]:
            add(
                f"If the conflict on {flag.conflicting_field.replace('_', ' ')} is resolved in "
                "the applicant's favour with documentary evidence."
            )
        for item in bucket.missing[:1]:
            add(f"If this remains unavailable: {item}")

    for drafted in output.what_could_change_recommendation:
        add(drafted)

    if state == RecommendationState.PROCEED_TO_STANDARD_REVIEW:
        add("If new adverse activity appears in any category after this package was closed.")
    return items[:7]
