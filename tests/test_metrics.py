"""Contradiction detection and prototype assurance metrics."""
from __future__ import annotations

import pytest

from src.assurance.contradiction_detector import (
    claim_conflicts_with_evidence,
    detect_contradictions,
    extract_field_values,
    normalise_month_year,
    reflow,
)
from src.assurance.metrics import (
    ACCEPTANCE_SCORE,
    aggregate_metrics,
    compute_metrics,
    review_rates,
)
from src.models.schemas import (
    AssuranceStatus,
    ClaimType,
    ContradictionFlag,
    EvidenceLink,
    ReviewDecision,
    RetrievedChunk,
    ValidatedClaim,
)


def chunk(source_id: str, document_id: str, name: str, content: str) -> RetrievedChunk:
    return RetrievedChunk(
        source_id=source_id, chunk_id=source_id, document_id=document_id, document_name=name,
        document_type="test", chunk_index=0, content=content, score=0.5,
    )


def claim(status: AssuranceStatus, sources=(), documents=()) -> ValidatedClaim:
    return ValidatedClaim(
        claim_text="A claim.",
        claim_type=ClaimType.FACT,
        assurance_status=status,
        confidence_score=0.8,
        evidence=[
            EvidenceLink(
                source_id=source_id, document_id=document_id, document_name="Doc",
                chunk_id=source_id, evidence_text="text", relevance_score=0.8,
            )
            for source_id, document_id in zip(sources, documents)
        ],
    )


# -- field extraction ------------------------------------------------------
def test_month_year_normalisation():
    import re

    match = re.search(r"(September)\s+(\d{1,2},\s*)?(2023)", "employment ended September 2023")
    assert normalise_month_year(match) == "2023-09"


def test_reflow_rejoins_wrapped_prose_but_keeps_record_lines():
    text = "The reference stated that employment\nended September 2023.\nTitle: Analyst"
    lines = reflow(text).splitlines()
    assert lines[0] == "The reference stated that employment ended September 2023."
    assert "Title: Analyst" in lines


def test_labelled_lines_yield_typed_values():
    values = extract_field_values("Employment end date: Employment ended June 2023")
    assert any(v.field == "employment_end_date" and v.value == "2023-06" for v in values)


def test_date_ranges_are_not_read_as_competing_values():
    values = extract_field_values("Dates confirmed by employer: June 2019 to November 2021")
    starts = {v.value for v in values if v.field == "employment_start_date"}
    ends = {v.value for v in values if v.field == "employment_end_date"}
    assert starts == {"2019-06"} and ends == {"2021-11"}


# -- contradiction detection ----------------------------------------------
def test_conflicting_separation_dates_are_flagged():
    flags = detect_contradictions(
        [
            chunk("DOC-1-CHUNK-0", "d1", "Employer Verification Record",
                  "Employment end date: Employment ended June 2023"),
            chunk("DOC-2-CHUNK-0", "d2", "Reference Interview Summary",
                  "The reference stated that employment ended September 2023."),
        ]
    )
    assert flags
    assert flags[0].conflicting_field == "employment_end_date"
    assert "human review" in flags[0].description.lower()
    assert flags[0].source_a_document != flags[0].source_b_document


def test_agreeing_sources_produce_no_flag():
    flags = detect_contradictions(
        [
            chunk("DOC-1-CHUNK-0", "d1", "Employer Record",
                  "Employment end date: Employment ended June 2023"),
            chunk("DOC-2-CHUNK-0", "d2", "Reference Summary",
                  "The reference stated that employment ended June 2023."),
        ]
    )
    assert flags == []


def test_repeated_labels_for_different_records_do_not_conflict():
    """Two positions in one employment record are not a contradiction."""
    flags = detect_contradictions(
        [
            chunk(
                "DOC-1-CHUNK-0", "d1", "Employment History",
                "POSITION 1\nDates confirmed by employer: February 2021 to present\n\n"
                "POSITION 2\nDates confirmed by employer: June 2017 to January 2021",
            )
        ]
    )
    assert flags == []


def test_clean_case_produces_no_flags(alex_case):
    from src.retrieval.retriever import Retriever

    assert detect_contradictions(Retriever().retrieve(alex_case["case_id"], top_k=30)) == []


def test_planted_contradiction_is_found_in_the_real_case(elena_case):
    from src.retrieval.retriever import Retriever

    flags = detect_contradictions(Retriever().retrieve(elena_case["case_id"], top_k=30))
    assert any(f.conflicting_field == "employment_end_date" for f in flags)


def test_claim_conflicting_with_its_own_evidence_is_detected():
    field = claim_conflicts_with_evidence(
        "The employer confirmed the employment end date was September 2023.",
        "Employment end date: Employment ended June 2023",
    )
    assert field == "employment_end_date"


def test_claim_agreeing_with_evidence_reports_no_conflict():
    assert (
        claim_conflicts_with_evidence(
            "The employer confirmed the employment end date was June 2023.",
            "Employment end date: Employment ended June 2023",
        )
        is None
    )


# -- metrics ---------------------------------------------------------------
def test_groundedness_half_credits_weak_support():
    metrics = compute_metrics(
        [
            claim(AssuranceStatus.SUPPORTED, ["s1"], ["d1"]),
            claim(AssuranceStatus.SUPPORTED, ["s2"], ["d2"]),
            claim(AssuranceStatus.WEAK_SUPPORT, ["s3"], ["d1"]),
            claim(AssuranceStatus.UNSUPPORTED),
        ]
    )
    assert metrics.groundedness == pytest.approx(0.625)
    assert metrics.unsupported_claim_rate == pytest.approx(0.25)
    assert metrics.total_claims == 4


def test_evidence_coverage_counts_claims_with_a_qualifying_source():
    metrics = compute_metrics(
        [claim(AssuranceStatus.SUPPORTED, ["s1"], ["d1"]), claim(AssuranceStatus.UNSUPPORTED)]
    )
    assert metrics.evidence_coverage == pytest.approx(0.5)


def test_source_diversity_averages_distinct_documents():
    metrics = compute_metrics(
        [
            claim(AssuranceStatus.SUPPORTED, ["s1", "s2"], ["d1", "d2"]),
            claim(AssuranceStatus.SUPPORTED, ["s3"], ["d1"]),
        ]
    )
    assert metrics.source_diversity == pytest.approx(1.5)


def test_contradiction_rate_counts_claims_touching_conflicting_evidence():
    flag = ContradictionFlag(
        conflicting_field="employment_end_date", description="d",
        source_a_id="s1", source_a_document="A", source_a_text="a",
        source_b_id="s9", source_b_document="B", source_b_text="b", confidence=0.7,
    )
    metrics = compute_metrics(
        [claim(AssuranceStatus.SUPPORTED, ["s1"], ["d1"]), claim(AssuranceStatus.SUPPORTED, ["s5"], ["d2"])],
        [flag],
    )
    assert metrics.contradiction_rate == pytest.approx(0.5)


def test_empty_claim_set_does_not_divide_by_zero():
    metrics = compute_metrics([])
    assert metrics.total_claims == 0 and metrics.groundedness == 0.0


def test_review_rates_split_by_decision():
    rates = review_rates(
        [
            ReviewDecision.ACCEPTED.value,
            ReviewDecision.ACCEPTED.value,
            ReviewDecision.EDITED_ACCEPTED.value,
            ReviewDecision.REJECTED.value,
        ]
    )
    assert rates["acceptance_rate"] == pytest.approx(0.5)
    assert rates["edit_rate"] == pytest.approx(0.25)
    assert rates["rejection_rate"] == pytest.approx(0.25)


def test_review_rates_with_no_reviews():
    assert review_rates([])["reviewed"] == 0


def test_acceptance_scoring_ranks_decisions():
    assert ACCEPTANCE_SCORE[ReviewDecision.ACCEPTED.value] > ACCEPTANCE_SCORE[
        ReviewDecision.EDITED_ACCEPTED.value
    ] > ACCEPTANCE_SCORE[ReviewDecision.REJECTED.value]


def test_aggregate_metrics_average_across_analyses(analysis_bundle):
    aggregate = aggregate_metrics([analysis_bundle.metrics, analysis_bundle.metrics])
    assert aggregate["analyses"] == 2
    assert aggregate["avg_groundedness"] == pytest.approx(analysis_bundle.metrics.groundedness)


def test_real_analysis_metrics_are_coherent(analysis_bundle):
    metrics = analysis_bundle.metrics
    assert metrics.total_claims == len(analysis_bundle.claims)
    assert (
        metrics.supported_claims + metrics.weak_claims
        + metrics.unsupported_claims + metrics.contradicted_claims
    ) == metrics.total_claims
    assert 0.0 <= metrics.groundedness <= 1.0
