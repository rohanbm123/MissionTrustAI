"""The evaluation framework: metric definitions and the mutation harness."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "evals"))

import metrics as eval_metrics  # noqa: E402

from src.config.settings import SYNTHETIC_CASES_DIR  # noqa: E402

EVALS_DIR = PROJECT_ROOT / "evals"

PROCEED = "PROCEED_TO_STANDARD_REVIEW"
REQUEST = "REQUEST_ADDITIONAL_INFORMATION"
ESCALATE = "ESCALATE_FOR_ENHANCED_REVIEW"


def golden(actual: str, expected: str, **extra) -> dict:
    record = {
        "actual_recommendation": actual,
        "expected_recommendation": expected,
        "reasons": [
            {"evidence_status": "SUPPORTED", "source_ids": ["DOC-1-CHUNK-0"], "category": "financial"}
        ],
    }
    record.update(extra)
    return record


def mutation(kind: str, base: str, actual: str, expected: str) -> dict:
    return {
        "kind": kind,
        "base_recommendation": base,
        "actual_recommendation": actual,
        "expected_recommendation": expected,
    }


# ---------------------------------------------------------------------------
# Eval assets
# ---------------------------------------------------------------------------
def test_ground_truth_is_not_reachable_from_the_case_package():
    """An expected answer must never sit where the inference pipeline can read it."""
    for metadata in SYNTHETIC_CASES_DIR.glob("*/case_metadata.json"):
        payload = json.loads(metadata.read_text())
        assert "expected_recommendation" not in payload
        assert "ground_truth" not in payload


def test_golden_cases_cover_every_recommendation_state():
    """Whatever the active caseload's size, every outcome must be represented."""
    cases = json.loads((EVALS_DIR / "golden_cases.json").read_text())["cases"]
    counts = {}
    for case in cases:
        counts[case["expected_recommendation"]] = counts.get(case["expected_recommendation"], 0) + 1
    assert counts.get(PROCEED, 0) >= 1
    assert counts.get(REQUEST, 0) >= 1
    assert counts.get(ESCALATE, 0) >= 1
    assert sum(counts.values()) == len(cases)


def test_mutation_base_cases_are_in_the_active_caseload():
    """A mutation whose base case is not loaded silently drops out of the suite."""
    golden = {c["slug"] for c in json.loads((EVALS_DIR / "golden_cases.json").read_text())["cases"]}
    payload = json.loads((EVALS_DIR / "evidence_mutation_cases.json").read_text())
    runnable = [m for m in payload["mutations"] if m["base_slug"] in golden]
    assert len(runnable) >= 5, "too few mutations can run against the active caseload"
    assert {m["kind"] for m in runnable} >= {"removal_material", "contradiction", "immaterial"}


def test_mutation_suite_covers_material_and_immaterial_changes():
    payload = json.loads((EVALS_DIR / "evidence_mutation_cases.json").read_text())
    kinds = {m["kind"] for m in payload["mutations"]}
    assert {"removal_material", "contradiction", "immaterial"} <= kinds
    for mutant in payload["mutations"]:
        assert mutant["expected_recommendation"] in {PROCEED, REQUEST, ESCALATE}
        assert mutant["remove"] or mutant["add"] or mutant.get("remove_events")


# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------
def test_recommendation_accuracy():
    records = [golden(PROCEED, PROCEED), golden(PROCEED, ESCALATE)]
    assert eval_metrics.recommendation_accuracy(records) == pytest.approx(0.5)


def test_recommendation_groundedness_counts_verified_reasons():
    weak = golden(PROCEED, PROCEED)
    weak["reasons"] = [
        {"evidence_status": "SUPPORTED", "source_ids": ["a"]},
        {"evidence_status": "UNSUPPORTED", "source_ids": []},
    ]
    assert eval_metrics.recommendation_groundedness([weak]) == pytest.approx(0.5)


def test_unsupported_recommendation_rate_flags_a_brief_with_no_reasons():
    empty = golden(PROCEED, PROCEED)
    empty["reasons"] = []
    assert eval_metrics.unsupported_recommendation_rate([empty]) == pytest.approx(1.0)


def test_unsupported_recommendation_rate_is_zero_when_reasons_are_backed():
    assert eval_metrics.unsupported_recommendation_rate([golden(PROCEED, PROCEED)]) == 0.0


def test_critical_evidence_recall():
    record = golden(
        PROCEED, PROCEED, critical_evidence=["a.txt", "b.txt"], evidence_files=["a.txt"]
    )
    assert eval_metrics.critical_evidence_recall([record]) == pytest.approx(0.5)


def test_citation_precision_penalises_irrelevant_citations():
    record = golden(
        PROCEED,
        PROCEED,
        citations=[
            {"resolved": True, "relevance": 0.9},
            {"resolved": True, "relevance": 0.05},
            {"resolved": False, "relevance": 0.9},
        ],
    )
    assert eval_metrics.citation_precision([record]) == pytest.approx(1 / 3, abs=1e-3)


def test_citation_recall_looks_for_decisive_facts_in_cited_text():
    record = golden(
        PROCEED,
        PROCEED,
        critical_evidence_terms=["March 14, 2026", "$18,500"],
        evidence_texts=["Plan effective date: March 14, 2026"],
    )
    assert eval_metrics.citation_recall([record]) == pytest.approx(0.5)


def test_reason_coverage():
    record = golden(
        PROCEED,
        PROCEED,
        expected_reason_topics=["financial", "employment"],
    )
    assert eval_metrics.reason_coverage([record]) == pytest.approx(0.5)


def test_stability_rewards_holding_under_immaterial_change():
    records = [
        mutation("immaterial", PROCEED, PROCEED, PROCEED),
        mutation("immaterial", PROCEED, ESCALATE, PROCEED),
    ]
    assert eval_metrics.recommendation_stability_score(records) == pytest.approx(0.5)


def test_material_sensitivity_requires_moving_to_the_right_state():
    """Moving for the wrong reason is instability, not sensitivity."""
    records = [
        mutation("removal_material", PROCEED, REQUEST, REQUEST),   # moved, correct
        mutation("removal_material", PROCEED, PROCEED, REQUEST),   # did not move
        mutation("contradiction", PROCEED, REQUEST, ESCALATE),     # moved, wrong state
    ]
    assert eval_metrics.material_evidence_sensitivity_score(records) == pytest.approx(1 / 3, abs=1e-3)


def test_contradiction_and_missing_information_sensitivity_are_scoped_by_kind():
    records = [
        mutation("contradiction", PROCEED, ESCALATE, ESCALATE),
        mutation("removal_material", PROCEED, PROCEED, REQUEST),
    ]
    assert eval_metrics.contradiction_sensitivity(records) == pytest.approx(1.0)
    assert eval_metrics.missing_information_sensitivity(records) == pytest.approx(0.0)


def test_human_agreement_rate():
    assert eval_metrics.human_agreement_rate(
        [{"agreed_with_ai": True}, {"agreed_with_ai": False}]
    ) == pytest.approx(0.5)


def test_summarise_reports_every_metric():
    summary = eval_metrics.summarise([golden(PROCEED, PROCEED)], [], [])
    for key in eval_metrics.METRIC_DIRECTION:
        assert key in summary


def test_empty_inputs_do_not_divide_by_zero():
    summary = eval_metrics.summarise([], [], [])
    assert summary["recommendation_accuracy"] == 0.0
    assert summary["recommendation_stability_score"] == 0.0


# ---------------------------------------------------------------------------
# Mutation harness
# ---------------------------------------------------------------------------
def test_build_variant_materialises_a_mutated_package():
    from run_evals import build_variant

    scratch = Path(tempfile.mkdtemp(prefix="casebrief_test_"))
    try:
        slug = build_variant(
            {
                "id": "unit_remove_and_add",
                "base_slug": "alex_morgan",
                "label": "unit",
                "kind": "immaterial",
                "remove": ["travel_disclosure.txt"],
                "add": [
                    {
                        "file": "extra_record.txt",
                        "document_name": "Extra Record",
                        "document_type": "record_check",
                        "text": "FICTIONAL DEMONSTRATION DATA\n\nEXTRA RECORD\n\nNothing adverse.\n",
                    }
                ],
                "expected_recommendation": PROCEED,
            },
            scratch,
        )
        target = scratch / slug
        metadata = json.loads((target / "case_metadata.json").read_text())
        files = {d["file"] for d in metadata["documents"]}
        assert "travel_disclosure.txt" not in files
        assert not (target / "travel_disclosure.txt").exists()
        assert "extra_record.txt" in files
        assert (target / "extra_record.txt").exists()
        assert metadata["slug"] == slug
        assert "eval variant" in metadata["applicant_name"]
        # The source package must be untouched.
        assert (SYNTHETIC_CASES_DIR / "alex_morgan" / "travel_disclosure.txt").exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_removing_load_bearing_evidence_moves_the_recommendation(all_cases):
    """The end-to-end sensitivity property, run for real against the corpus."""
    from run_evals import build_variant

    from src.database.db import session_scope
    from src.database.repositories import CaseRepository
    from src.ingestion.document_loader import load_case
    from src.services.analysis_service import run_analysis
    from src.services.case_service import ingest_case

    base = run_analysis(all_cases["alex_morgan"]).assessment
    assert base.overall_recommendation.value == PROCEED

    scratch = Path(tempfile.mkdtemp(prefix="casebrief_test_"))
    try:
        slug = build_variant(
            {
                "id": "unit_remove_repayment_evidence",
                "base_slug": "alex_morgan",
                "label": "unit",
                "kind": "removal_material",
                "remove": ["payment_plan.txt", "investigator_notes.txt"],
                "add": [],
                "expected_recommendation": REQUEST,
            },
            scratch,
        )
        ingest_case(load_case(slug, scratch))
        with session_scope() as session:
            variant_id = CaseRepository.get_by_slug(session, slug).id
        mutated = run_analysis(variant_id).assessment
        assert mutated.overall_recommendation.value == REQUEST
        assert mutated.overall_recommendation != base.overall_recommendation
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_adding_a_benign_document_does_not_move_the_recommendation(all_cases):
    """The stability property: noise must not change the answer."""
    from run_evals import build_variant

    from src.database.db import session_scope
    from src.database.repositories import CaseRepository
    from src.ingestion.document_loader import load_case
    from src.services.analysis_service import run_analysis
    from src.services.case_service import ingest_case

    base = run_analysis(all_cases["alex_morgan"]).assessment

    scratch = Path(tempfile.mkdtemp(prefix="casebrief_test_"))
    try:
        slug = build_variant(
            {
                "id": "unit_add_benign_document",
                "base_slug": "alex_morgan",
                "label": "unit",
                "kind": "immaterial",
                "remove": [],
                "add": [
                    {
                        "file": "education_verification.txt",
                        "document_name": "Education Verification",
                        "document_type": "record_check",
                        "text": (
                            "FICTIONAL DEMONSTRATION DATA\n\nEDUCATION VERIFICATION\n\n"
                            "Verification completed: 2026-03-04\nDegree awarded: Bachelor of "
                            "Science\nThe dates reported match the institution's record. No "
                            "discrepancy was identified.\n"
                        ),
                    }
                ],
                "expected_recommendation": PROCEED,
            },
            scratch,
        )
        ingest_case(load_case(slug, scratch))
        with session_scope() as session:
            variant_id = CaseRepository.get_by_slug(session, slug).id
        mutated = run_analysis(variant_id).assessment
        assert mutated.overall_recommendation == base.overall_recommendation
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
