"""The decision-ready recommendation: schema, rules, synthesis and behaviour."""
from __future__ import annotations

import pytest

from src.assurance.recommendation_engine import (
    ABSENCE_MARKERS,
    CategoryEvidence,
    assess_category,
    category_for_contradiction,
    classify,
    evaluate_rules,
    gather_category_evidence,
    synthesize,
)
from src.models.schemas import (
    AdjudicatorAction,
    AssuranceStatus,
    CaseAnalysisOutput,
    ClaimType,
    ConcernLevel,
    ContradictionFlag,
    EvidenceCategory,
    EvidenceLink,
    FinalCaseAssessment,
    MitigatingFactor,
    KeyFinding,
    RecommendationReason,
    RecommendationState,
    Severity,
    ValidatedClaim,
    most_conservative,
)

PROCEED = RecommendationState.PROCEED_TO_STANDARD_REVIEW
REQUEST = RecommendationState.REQUEST_ADDITIONAL_INFORMATION
ESCALATE = RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def claim(
    text: str,
    kind: str = "fact",
    status: AssuranceStatus = AssuranceStatus.SUPPORTED,
    sources=("DOC-1-CHUNK-0",),
) -> ValidatedClaim:
    return ValidatedClaim(
        claim_text=text,
        claim_type=ClaimType(kind),
        assurance_status=status,
        confidence_score=0.85,
        evidence=[
            EvidenceLink(
                source_id=source,
                document_id="d1",
                document_name="Financial Report",
                chunk_id=source,
                evidence_text="passage",
                relevance_score=0.8,
            )
            for source in sources
        ],
    )


def flag(field: str, confidence: float, same_passage: bool = False) -> ContradictionFlag:
    return ContradictionFlag(
        conflicting_field=field,
        description="Potential contradiction requiring human review.",
        source_a_id="DOC-1-CHUNK-0",
        source_a_document="Record A",
        source_a_text="a",
        source_b_id="DOC-1-CHUNK-0" if same_passage else "DOC-2-CHUNK-0",
        source_b_document="Record A" if same_passage else "Record B",
        source_b_text="b",
        confidence=confidence,
    )


def output(**kwargs) -> CaseAnalysisOutput:
    payload = {"executive_summary": "A synthesized case assessment of sufficient length."}
    payload.update(kwargs)
    return CaseAnalysisOutput(**payload)


def decide(claims, contradictions=(), out=None) -> FinalCaseAssessment:
    return synthesize(out or output(), claims, list(contradictions))


# ---------------------------------------------------------------------------
# Schema guarantees
# ---------------------------------------------------------------------------
def test_only_decision_support_states_exist():
    values = {state.value for state in RecommendationState}
    assert values == {
        "PROCEED_TO_STANDARD_REVIEW",
        "REQUEST_ADDITIONAL_INFORMATION",
        "ESCALATE_FOR_ENHANCED_REVIEW",
    }
    for forbidden in ("APPROVE", "DENY", "GRANT", "REJECT"):
        assert not any(forbidden in value for value in values)


def test_most_conservative_picks_the_highest_escalation():
    assert most_conservative([PROCEED, ESCALATE, REQUEST]) is ESCALATE
    assert most_conservative([PROCEED, REQUEST]) is REQUEST
    assert most_conservative([]) is PROCEED


def test_human_decision_cannot_be_disabled():
    assert FinalCaseAssessment(requires_human_decision=False).requires_human_decision is True


def test_confidence_is_clamped():
    assert FinalCaseAssessment(recommendation_confidence=4.0).recommendation_confidence == 1.0
    assert FinalCaseAssessment(recommendation_confidence=-1.0).recommendation_confidence == 0.0


def test_adjudicator_actions_map_onto_recommendation_states():
    assert AdjudicatorAction.PROCEED.aligned_recommendation is PROCEED
    assert AdjudicatorAction.REQUEST_MORE_INFORMATION.aligned_recommendation is REQUEST
    assert AdjudicatorAction.ESCALATE.aligned_recommendation is ESCALATE


# ---------------------------------------------------------------------------
# Classification and category assessment
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("A continuous monitoring alert referenced the account.", EvidenceCategory.MONITORING),
        ("The applicant entered a repayment plan.", EvidenceCategory.FINANCIAL),
        ("Nine months of residence history is unverified.", EvidenceCategory.IDENTITY_BACKGROUND),
        ("Border-crossing records identified no undisclosed travel.", EvidenceCategory.FOREIGN_TRAVEL),
        ("The court classified the matter as an infraction.", EvidenceCategory.LEGAL_CONDUCT),
        ("The employer confirmed the separation date.", EvidenceCategory.EMPLOYMENT),
    ],
)
def test_classification_routes_text_to_the_right_category(text, expected):
    assert classify(text) is expected


def test_documentation_is_a_fallback_not_a_magnet():
    """Absence vocabulary must not pull a substantive finding into paperwork."""
    assert classify("Nine months of residence history is unverified.") is not (
        EvidenceCategory.DOCUMENTATION
    )
    assert classify("No itemised statement is present in the file.") is (
        EvidenceCategory.DOCUMENTATION
    )


def test_contradiction_fields_map_to_categories():
    assert category_for_contradiction(flag("employment_end_date", 0.8)) is EvidenceCategory.EMPLOYMENT
    assert category_for_contradiction(flag("delinquent_amount", 0.8)) is EvidenceCategory.FINANCIAL


def test_category_with_verifiable_mitigation_is_marked_mitigated():
    evidence = CategoryEvidence(
        category=EvidenceCategory.FINANCIAL,
        concerns=[claim("A delinquent account is reported.", "potential_concern")],
        mitigations=[claim("A repayment plan is verified.", "mitigation")],
    )
    assessment = assess_category(evidence)
    assert assessment.mitigated is True
    assert "mitigat" in assessment.conclusion.lower()


def test_category_with_unverifiable_mitigation_is_not_mitigated():
    evidence = CategoryEvidence(
        category=EvidenceCategory.FINANCIAL,
        concerns=[claim("A delinquent account is reported.", "potential_concern")],
        mitigations=[
            claim("A repayment plan exists.", "mitigation", AssuranceStatus.UNSUPPORTED)
        ],
    )
    assert assess_category(evidence).mitigated is False


def test_absence_and_adverse_concerns_are_distinguished():
    evidence = CategoryEvidence(
        category=EvidenceCategory.FINANCIAL,
        concerns=[
            claim("Revolving utilisation is reported at 97 percent.", "potential_concern"),
            claim("No repayment agreement has been received.", "potential_concern"),
        ],
    )
    assert len(evidence.adverse_concerns) == 1
    assert any(marker in ABSENCE_MARKERS for marker in ("no repayment agreement",))


# ---------------------------------------------------------------------------
# Rules — the recommendation must be evidence-sensitive, not an average
# ---------------------------------------------------------------------------
def test_clean_package_proceeds():
    assessment = decide([claim("Every record was corroborated independently.")])
    assert assessment.overall_recommendation is PROCEED
    assert assessment.material_unresolved_issues == 0


def test_mitigated_concern_proceeds():
    assessment = decide(
        [
            claim("A delinquent account is reported.", "potential_concern"),
            claim("A repayment plan is verified.", "mitigation"),
        ]
    )
    assert assessment.overall_recommendation is PROCEED


def test_one_material_contradiction_escalates_an_otherwise_clean_case():
    """The headline rule: a single unresolved conflict outweighs a quiet file."""
    claims = [claim(f"Routine verified fact number {n}.") for n in range(8)]
    claims.append(claim("The separation date is disputed.", "potential_concern"))
    assessment = decide(claims, [flag("employment_end_date", 0.75)])
    assert assessment.overall_recommendation is ESCALATE
    assert any("material_contradiction" in line for line in assessment.engine_rationale)


def test_recommendation_is_not_an_average_of_category_scores():
    """Seven clean categories do not dilute one unresolved conflict."""
    claims = [
        claim("Employment dates match the employer record."),
        claim("Foreign travel matches border-crossing records."),
        claim("The court matter is closed."),
        claim("Residence history is fully verified."),
        claim("No monitoring alert was generated."),
        claim("The financial record shows a disputed balance.", "potential_concern"),
    ]
    assert decide(claims, [flag("delinquent_amount", 0.8)]).overall_recommendation is ESCALATE


def test_discrepancy_inside_one_record_requests_rather_than_escalates():
    """'As reported' vs 'as confirmed' in one record is a documented discrepancy."""
    claims = [
        claim("The reported start date differs from the confirmed start date.", "potential_concern"),
        claim("A staffing record reconciles most of the period.", "mitigation"),
    ]
    assessment = decide(claims, [flag("employment_start_date", 0.8, same_passage=True)])
    assert assessment.overall_recommendation is REQUEST


def test_unmitigated_adverse_finding_escalates():
    claims = [
        claim("Revolving utilisation is reported at 97 percent.", "potential_concern"),
        claim("A civil judgment remains unsatisfied.", "potential_concern"),
    ]
    assert decide(claims).overall_recommendation is ESCALATE


def test_high_concern_built_from_gaps_requests_evidence_instead():
    """Escalate on what the file says; request on what the file lacks."""
    claims = [
        claim("The address could not be verified by any source.", "potential_concern"),
        claim("Nine months of residence history remains unverified.", "potential_concern"),
        claim("The data provider has no entry for the address.", "potential_concern"),
    ]
    assert decide(claims).overall_recommendation is REQUEST


def test_asserted_but_unverifiable_mitigation_requests_the_document():
    claims = [
        claim("A delinquent account is reported.", "potential_concern"),
        claim("A repayment plan exists.", "mitigation", AssuranceStatus.UNSUPPORTED),
    ]
    assessment = decide(claims)
    assert assessment.overall_recommendation is REQUEST
    assert any("unverifiable_mitigation" in line for line in assessment.engine_rationale)


def test_a_claim_contradicted_by_its_own_evidence_escalates():
    assert (
        decide([claim("A disputed statement.", "fact", AssuranceStatus.CONTRADICTED)])
        .overall_recommendation
        is ESCALATE
    )


# ---------------------------------------------------------------------------
# Reconciliation with the model
# ---------------------------------------------------------------------------
def test_engine_overrides_an_optimistic_model_and_records_the_divergence():
    claims = [
        claim("Revolving utilisation is reported at 97 percent.", "potential_concern"),
        claim("A civil judgment remains unsatisfied.", "potential_concern"),
    ]
    assessment = decide(claims, out=output(proposed_recommendation=PROCEED))
    assert assessment.overall_recommendation is ESCALATE
    assert assessment.model_proposed_recommendation is PROCEED
    assert assessment.model_agreed_with_engine is False
    assert any("model_divergence" in line for line in assessment.engine_rationale)


def test_a_more_conservative_model_is_not_overruled():
    assessment = decide([claim("A verified fact.")], out=output(proposed_recommendation=ESCALATE))
    assert assessment.overall_recommendation is ESCALATE


def test_agreement_is_recorded_when_both_agree():
    assessment = decide([claim("A verified fact.")], out=output(proposed_recommendation=PROCEED))
    assert assessment.model_agreed_with_engine is True


# ---------------------------------------------------------------------------
# Brief content
# ---------------------------------------------------------------------------
def test_adverse_information_survives_a_positive_recommendation():
    """The system must never hide adverse evidence behind a good outcome."""
    assessment = decide(
        [
            claim("A monitoring alert references the account.", "potential_concern"),
            claim("The investigator matched the monitoring alert to the disclosed account.", "mitigation"),
        ]
    )
    assert assessment.overall_recommendation is PROCEED
    assert assessment.remaining_concerns


def test_reasons_carry_resolved_evidence_and_a_verification_status():
    drafted = RecommendationReason(
        reason="The financial concern has documented mitigation.",
        category=EvidenceCategory.FINANCIAL,
        source_ids=["DOC-1-CHUNK-0"],
    )
    assessment = decide(
        [claim("A repayment plan is verified.", "mitigation")],
        out=output(why_this_recommendation=[drafted]),
    )
    reason = assessment.why_this_recommendation[0]
    assert reason.evidence
    assert reason.evidence_status is AssuranceStatus.SUPPORTED
    assert reason.verification_score > 0


def test_unverifiable_mitigation_is_not_listed_as_a_mitigating_factor():
    assessment = decide(
        [
            claim("A delinquent account is reported.", "potential_concern"),
            claim("A repayment plan exists.", "mitigation", AssuranceStatus.UNSUPPORTED),
        ]
    )
    assert all("repayment plan exists" not in f.factor.lower() for f in assessment.mitigating_factors)


def test_sensitivities_name_the_load_bearing_evidence():
    assessment = decide(
        [
            claim("A delinquent account is reported.", "potential_concern"),
            claim("A repayment plan effective March 14, 2026 is verified.", "mitigation"),
        ]
    )
    assert any("could not be verified" in item for item in assessment.what_could_change_recommendation)


def test_category_assessments_are_produced_for_every_touched_category():
    assessment = decide(
        [
            claim("A delinquent account is reported.", "potential_concern"),
            claim("Employment dates match the employer record."),
        ]
    )
    categories = {c.category for c in assessment.category_assessments}
    assert EvidenceCategory.FINANCIAL in categories
    assert EvidenceCategory.EMPLOYMENT in categories


def test_confidence_falls_as_evidence_quality_falls():
    strong = decide([claim("A verified fact.") for _ in range(4)])
    weak = decide(
        [claim("A verified fact.")]
        + [claim("An unverifiable fact.", "fact", AssuranceStatus.UNSUPPORTED) for _ in range(3)]
    )
    assert strong.recommendation_confidence > weak.recommendation_confidence


def test_missing_information_is_carried_into_the_brief():
    assessment = decide(
        [claim("A verified fact.")],
        out=output(missing_information=["The separation letter has not been received."]),
    )
    assert assessment.missing_information


def test_key_finding_severity_raises_the_category_concern_level():
    high = output(
        key_findings=[
            KeyFinding(finding="A delinquent account of $18,500.", category="financial", severity=Severity.HIGH)
        ]
    )
    evidence = gather_category_evidence([claim("A delinquent account is reported.")], [], high)
    assert assess_category(evidence[EvidenceCategory.FINANCIAL]).concern_level is ConcernLevel.HIGH


def test_rules_return_no_triggers_for_a_clean_package():
    evidence = gather_category_evidence([claim("Everything was corroborated.")], [])
    assessments = {c: assess_category(b) for c, b in evidence.items()}
    assert evaluate_rules(assessments, evidence, []) == []


# ---------------------------------------------------------------------------
# End-to-end against the real corpus
# ---------------------------------------------------------------------------
def test_every_golden_case_reaches_its_expected_recommendation(all_cases, golden_expectations):
    from src.database.db import session_scope
    from src.database.repositories import CaseRepository
    from src.services.analysis_service import run_analysis

    mismatches = []
    with session_scope() as session:
        by_number = {c.case_number: c.id for c in CaseRepository.list_all(session)}

    for case_number, truth in golden_expectations.items():
        bundle = run_analysis(by_number[case_number])
        actual = bundle.assessment.overall_recommendation.value
        if actual != truth["expected_recommendation"]:
            mismatches.append((case_number, actual, truth["expected_recommendation"]))
    assert not mismatches, f"recommendation mismatches: {mismatches}"


def test_every_brief_states_reasons_and_requires_a_human(all_cases):
    from src.services.analysis_service import run_analysis

    bundle = run_analysis(all_cases["alex_morgan"])
    assessment = bundle.assessment
    assert assessment.requires_human_decision is True
    assert 1 <= len(assessment.why_this_recommendation) <= 7
    assert assessment.executive_case_assessment
    assert all(reason.evidence or reason.source_ids for reason in assessment.why_this_recommendation)


def test_generated_claims_remain_available_alongside_the_brief(all_cases):
    """Claim-level validation is retained, not replaced, by the recommendation."""
    from src.services.analysis_service import run_analysis

    bundle = run_analysis(all_cases["alex_morgan"])
    assert bundle.claims
    assert any(c.assurance_status == AssuranceStatus.UNSUPPORTED for c in bundle.claims)


# ---------------------------------------------------------------------------
# Only deterministic detectors may escalate
# ---------------------------------------------------------------------------
def model_flag(field: str, confidence: float, detector: str) -> ContradictionFlag:
    flag = flag_for(field, confidence)
    return flag.model_copy(update={"detector": detector})


def flag_for(field: str, confidence: float) -> ContradictionFlag:
    return flag(field, confidence)


def test_a_model_declared_conflict_cannot_escalate_on_its_own():
    """The model must not have a side door into the recommendation.

    A live run flagged an $18,500 February balance against a $17,850 May balance
    as a contradiction at 0.95 — the difference was two $325 payments.
    """
    claims = [
        claim("A delinquent account is reported.", "potential_concern"),
        claim("A repayment plan is verified.", "mitigation"),
    ]
    assessment = decide(claims, [model_flag("account_balance", 0.95, "llm-verifier-v1")])
    assert assessment.overall_recommendation is not ESCALATE


def test_a_heuristic_conflict_still_escalates():
    claims = [claim("A delinquent account is reported.", "potential_concern")]
    assessment = decide(claims, [model_flag("delinquent_amount", 0.95, "heuristic-field-value-v1")])
    assert assessment.overall_recommendation is ESCALATE


def test_an_unrecognised_detector_is_treated_as_advisory():
    """Unknown detectors under-escalate rather than reopening the side door."""
    claims = [claim("A delinquent account is reported.", "potential_concern")]
    assessment = decide(claims, [model_flag("delinquent_amount", 0.99, "some-new-detector")])
    assert assessment.overall_recommendation is not ESCALATE


def test_advisory_conflicts_are_still_surfaced_to_the_adjudicator():
    """Demoted does not mean hidden."""
    claims = [claim("A delinquent account is reported.", "potential_concern")]
    assessment = decide(claims, [model_flag("account_balance", 0.95, "model-declared")])
    assert assessment.potential_contradictions


# ---------------------------------------------------------------------------
# Mitigation is read from the fields the prompt asks for
# ---------------------------------------------------------------------------
def test_mitigation_is_recognised_from_factor_details_without_claim_type_labels():
    """A live model may never emit claim_type 'mitigation'.

    One run typed every claim `fact` and put the repayment plan in
    `factor_details`, exactly where the prompt asks for it.
    """
    claims = [
        claim("A delinquent account is reported.", "potential_concern"),
        claim("A repayment plan effective March 14, 2026 is on file.", "fact"),
    ]
    drafted = MitigatingFactor(
        factor="A repayment plan effective March 14, 2026 is on file.",
        category=EvidenceCategory.FINANCIAL,
        source_ids=["DOC-1-CHUNK-0"],
    )
    assessment = decide(claims, out=output(factor_details=[drafted]))
    assert assessment.overall_recommendation is PROCEED


def test_an_unverifiable_stated_factor_does_not_count_as_mitigation():
    claims = [
        claim("A delinquent account is reported.", "potential_concern"),
        claim("A plan exists.", "fact", AssuranceStatus.UNSUPPORTED),
    ]
    drafted = MitigatingFactor(factor="A plan exists.", category=EvidenceCategory.FINANCIAL)
    assessment = decide(claims, out=output(factor_details=[drafted]))
    assert assessment.overall_recommendation is not PROCEED


# ---------------------------------------------------------------------------
# A gap cannot be mitigated, only filled
# ---------------------------------------------------------------------------
def test_absence_only_concerns_are_never_marked_mitigated():
    claims = [
        claim("The address could not be verified by any source.", "potential_concern"),
        claim("Nine months of residence history remains unverified.", "potential_concern"),
        claim("A neighbouring record was verified.", "mitigation"),
    ]
    assessment = decide(claims)
    assert assessment.overall_recommendation is REQUEST
    assert any("pending_evidence" in line for line in assessment.engine_rationale)


# ---------------------------------------------------------------------------
# Agreement is measured against the engine, not against what shipped
# ---------------------------------------------------------------------------
def test_divergence_is_reported_when_the_model_is_the_conservative_one():
    """Previously this reported agreement, hiding the reconciliation notice."""
    assessment = decide([claim("A verified fact.")], out=output(proposed_recommendation=ESCALATE))
    assert assessment.overall_recommendation is ESCALATE
    assert assessment.engine_recommendation is PROCEED
    assert assessment.model_agreed_with_engine is False


def test_agreement_is_reported_when_both_reach_the_same_state():
    assessment = decide([claim("A verified fact.")], out=output(proposed_recommendation=PROCEED))
    assert assessment.engine_recommendation is PROCEED
    assert assessment.model_agreed_with_engine is True


# ---------------------------------------------------------------------------
# Conflict wording
# ---------------------------------------------------------------------------
def test_a_conflict_inside_one_record_is_not_described_as_x_versus_x():
    from src.assurance.recommendation_engine import describe_conflict_sources

    same = flag("employment_start_date", 0.8, same_passage=True)
    assert "vs" not in describe_conflict_sources(same)
    assert "within" in describe_conflict_sources(same)

    cross = flag("employment_end_date", 0.8)
    assert "vs" in describe_conflict_sources(cross)


def test_an_advisory_conflict_is_not_badged_material():
    """A flag that cannot escalate must not be presented as decision-weight.

    Surfaced from a live run: a model-declared conflict was correctly demoted
    out of the escalation rules but still rendered as "High / Material" and
    counted toward material unresolved issues.
    """
    claims = [
        claim("A delinquent account is reported.", "potential_concern"),
        claim("A repayment plan is verified.", "mitigation"),
    ]
    assessment = decide(claims, [model_flag("account_balance", 0.95, "llm-verifier-v1")])
    conflict_concerns = [c for c in assessment.remaining_concerns if "disagree" in c.concern]
    assert conflict_concerns, "the conflict should still be surfaced"
    assert all(not c.is_material for c in conflict_concerns)
    assert assessment.material_unresolved_issues == 0


def test_a_deterministic_conflict_is_badged_material():
    claims = [claim("A delinquent account is reported.", "potential_concern")]
    assessment = decide(claims, [model_flag("delinquent_amount", 0.95, "heuristic-field-value-v1")])
    conflict_concerns = [c for c in assessment.remaining_concerns if "disagree" in c.concern]
    assert any(c.is_material for c in conflict_concerns)
