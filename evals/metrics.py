"""Prototype evaluation metrics for the overall recommendation feature.

These are demonstration measures for a prototype, not validated benchmarks.
Every one operates on plain dictionaries so it can be unit-tested without a
database, an LLM or an ingestion run.

Records are produced by `run_evals.py`. A *golden* record describes one
unmutated case; a *mutation* record describes one controlled evidence variant
and carries the base case's recommendation for comparison.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

SUPPORTED_STATUSES = {"SUPPORTED", "WEAK_SUPPORT"}
MIN_SUPPORTED_REASON_RATIO = 0.5
CITATION_RELEVANCE_FLOOR = 0.30


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


# ---------------------------------------------------------------------------
# Golden-case metrics
# ---------------------------------------------------------------------------
def recommendation_accuracy(records: Sequence[Dict[str, Any]]) -> float:
    """Does the system produce the expected recommendation for golden cases?"""
    return _ratio(
        sum(1 for r in records if r["actual_recommendation"] == r["expected_recommendation"]),
        len(records),
    )


def concern_level_accuracy(records: Sequence[Dict[str, Any]]) -> float:
    scored = [r for r in records if r.get("expected_concern_level")]
    return _ratio(
        sum(1 for r in scored if r.get("concern_level") == r["expected_concern_level"]),
        len(scored),
    )


def recommendation_groundedness(records: Sequence[Dict[str, Any]]) -> float:
    """Share of stated reasons that are backed by verified evidence."""
    per_case = []
    for record in records:
        reasons = record.get("reasons", [])
        if not reasons:
            per_case.append(0.0)
            continue
        backed = sum(
            1
            for reason in reasons
            if reason.get("evidence_status") in SUPPORTED_STATUSES
            and reason.get("source_ids")
        )
        per_case.append(backed / len(reasons))
    return _mean(per_case)


def unsupported_recommendation_rate(records: Sequence[Dict[str, Any]]) -> float:
    """How often a recommendation ships without adequate evidential support.

    A recommendation counts as unsupported when it has no reasons at all, or
    when fewer than half of its reasons trace to verified evidence.
    """
    unsupported = 0
    for record in records:
        reasons = record.get("reasons", [])
        if not reasons:
            unsupported += 1
            continue
        backed = sum(
            1
            for reason in reasons
            if reason.get("evidence_status") in SUPPORTED_STATUSES and reason.get("source_ids")
        )
        if backed / len(reasons) < MIN_SUPPORTED_REASON_RATIO:
            unsupported += 1
    return _ratio(unsupported, len(records))


def critical_evidence_recall(records: Sequence[Dict[str, Any]]) -> float:
    """Did the brief actually reach the documents the decision depends on?"""
    per_case = []
    for record in records:
        critical = record.get("critical_evidence") or []
        if not critical:
            continue
        cited = {name.lower() for name in record.get("evidence_files", [])}
        hit = sum(1 for document in critical if document.lower() in cited)
        per_case.append(hit / len(critical))
    return _mean(per_case)


def citation_precision(records: Sequence[Dict[str, Any]]) -> float:
    """Are cited passages actually relevant to the reasons that cite them?"""
    per_case = []
    for record in records:
        citations = record.get("citations", [])
        if not citations:
            continue
        relevant = sum(
            1
            for citation in citations
            if citation.get("resolved")
            and citation.get("relevance", 0.0) >= CITATION_RELEVANCE_FLOOR
        )
        per_case.append(relevant / len(citations))
    return _mean(per_case)


def citation_recall(records: Sequence[Dict[str, Any]]) -> float:
    """Did the brief cite the decisive facts available in the package?"""
    per_case = []
    for record in records:
        terms = record.get("critical_evidence_terms") or []
        if not terms:
            continue
        corpus = " ".join(record.get("evidence_texts", [])).lower()
        per_case.append(sum(1 for term in terms if term.lower() in corpus) / len(terms))
    return _mean(per_case)


def reason_coverage(records: Sequence[Dict[str, Any]]) -> float:
    """Does the explanation cover every major evidence-backed topic?"""
    per_case = []
    for record in records:
        expected = record.get("expected_reason_topics") or []
        if not expected:
            continue
        covered = {r.get("category") for r in record.get("reasons", [])}
        per_case.append(sum(1 for topic in expected if topic in covered) / len(expected))
    return _mean(per_case)


# ---------------------------------------------------------------------------
# Evidence-mutation metrics
# ---------------------------------------------------------------------------
def _of_kind(records: Iterable[Dict[str, Any]], *kinds: str) -> List[Dict[str, Any]]:
    return [r for r in records if r.get("kind") in kinds]


def mutation_accuracy(records: Sequence[Dict[str, Any]]) -> float:
    return _ratio(
        sum(1 for r in records if r["actual_recommendation"] == r["expected_recommendation"]),
        len(records),
    )


def contradiction_sensitivity(records: Sequence[Dict[str, Any]]) -> float:
    """Does the recommendation move appropriately when conflict is introduced?"""
    return mutation_accuracy(_of_kind(records, "contradiction"))


def missing_information_sensitivity(records: Sequence[Dict[str, Any]]) -> float:
    """Does removing critical evidence push the case to REQUEST_ADDITIONAL_INFORMATION?"""
    return mutation_accuracy(_of_kind(records, "removal_material"))


def recommendation_stability_score(records: Sequence[Dict[str, Any]]) -> float:
    """How consistently the recommendation holds when *non-material* evidence changes.

    Non-material mutations add or remove documents that no material reason
    depends on. A system that reacts to them is reacting to noise.
    """
    immaterial = _of_kind(records, "immaterial")
    return _ratio(
        sum(1 for r in immaterial if r["actual_recommendation"] == r["base_recommendation"]),
        len(immaterial),
    )


def material_evidence_sensitivity_score(records: Sequence[Dict[str, Any]]) -> float:
    """How reliably the recommendation changes when *critical* evidence changes.

    Credit is given only when the recommendation both moved away from the base
    case and landed on the expected state — moving for the wrong reason is not
    sensitivity, it is instability.
    """
    material = _of_kind(records, "removal_material", "contradiction", "addition_material")
    if not material:
        return 0.0
    correct = sum(
        1
        for r in material
        if r["actual_recommendation"] != r["base_recommendation"]
        and r["actual_recommendation"] == r["expected_recommendation"]
    )
    return _ratio(correct, len(material))


def human_agreement_rate(actions: Sequence[Dict[str, Any]]) -> float:
    """How often the recorded adjudicator action matched the AI recommendation."""
    return _ratio(sum(1 for a in actions if a.get("agreed_with_ai")), len(actions))


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def summarise(
    golden: Sequence[Dict[str, Any]],
    mutations: Sequence[Dict[str, Any]],
    actions: Sequence[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    return {
        "golden_cases": len(golden),
        "mutation_cases": len(mutations),
        "recommendation_accuracy": recommendation_accuracy(golden),
        "concern_level_accuracy": concern_level_accuracy(golden),
        "recommendation_groundedness": recommendation_groundedness(golden),
        "unsupported_recommendation_rate": unsupported_recommendation_rate(golden),
        "critical_evidence_recall": critical_evidence_recall(golden),
        "citation_precision": citation_precision(golden),
        "citation_recall": citation_recall(golden),
        "reason_coverage": reason_coverage(golden),
        "mutation_accuracy": mutation_accuracy(mutations),
        "contradiction_sensitivity": contradiction_sensitivity(mutations),
        "missing_information_sensitivity": missing_information_sensitivity(mutations),
        "recommendation_stability_score": recommendation_stability_score(mutations),
        "material_evidence_sensitivity_score": material_evidence_sensitivity_score(mutations),
        "human_agreement_rate": human_agreement_rate(actions),
    }


METRIC_DIRECTION = {
    "recommendation_accuracy": "higher",
    "concern_level_accuracy": "higher",
    "recommendation_groundedness": "higher",
    "unsupported_recommendation_rate": "lower",
    "critical_evidence_recall": "higher",
    "citation_precision": "higher",
    "citation_recall": "higher",
    "reason_coverage": "higher",
    "mutation_accuracy": "higher",
    "contradiction_sensitivity": "higher",
    "missing_information_sensitivity": "higher",
    "recommendation_stability_score": "higher",
    "material_evidence_sensitivity_score": "higher",
    "human_agreement_rate": "higher",
}
