"""Prototype AI assurance metrics.

These are demonstration metrics for a prototype. They are not formal
regulatory, safety or compliance measures, and nothing here should be read as
a certification of model quality. Every formula is documented in the README so
that a reviewer can see exactly what a number does and does not mean.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from src.models.schemas import (
    AssuranceMetrics,
    AssuranceStatus,
    ContradictionFlag,
    ReviewDecision,
    ValidatedClaim,
)

# A weak-support claim is half-credited: the evidence exists but a reviewer
# still has to confirm it, so it is neither grounded nor a failure.
WEAK_SUPPORT_CREDIT = 0.5
EVIDENCE_LINK_THRESHOLD = 0.35

# How a recorded human decision scores as "reviewer acceptance".
ACCEPTANCE_SCORE: Dict[str, float] = {
    ReviewDecision.ACCEPTED.value: 1.0,
    ReviewDecision.EDITED_ACCEPTED.value: 0.5,
    ReviewDecision.MORE_EVIDENCE_REQUESTED.value: 0.25,
    ReviewDecision.REJECTED.value: 0.0,
}


def _safe_ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def compute_metrics(
    claims: Sequence[ValidatedClaim],
    contradictions: Sequence[ContradictionFlag] = (),
    reviewer_acceptance: Optional[float] = None,
) -> AssuranceMetrics:
    total = len(claims)
    if total == 0:
        return AssuranceMetrics(reviewer_acceptance=reviewer_acceptance)

    supported = sum(1 for c in claims if c.assurance_status == AssuranceStatus.SUPPORTED)
    weak = sum(1 for c in claims if c.assurance_status == AssuranceStatus.WEAK_SUPPORT)
    unsupported = sum(1 for c in claims if c.assurance_status == AssuranceStatus.UNSUPPORTED)
    contradicted = sum(1 for c in claims if c.assurance_status == AssuranceStatus.CONTRADICTED)

    with_evidence = sum(
        1
        for c in claims
        if any(link.relevance_score >= EVIDENCE_LINK_THRESHOLD for link in c.evidence)
    )

    unique_documents = [
        len({link.document_id for link in c.evidence if link.relevance_score >= EVIDENCE_LINK_THRESHOLD})
        for c in claims
    ]
    diversity_pool = [n for n in unique_documents if n > 0]

    conflicted_sources = {flag.source_a_id for flag in contradictions} | {
        flag.source_b_id for flag in contradictions
    }
    touching_conflict = sum(
        1
        for c in claims
        if c.assurance_status == AssuranceStatus.CONTRADICTED
        or any(link.source_id in conflicted_sources for link in c.evidence)
    )

    return AssuranceMetrics(
        groundedness=_safe_ratio(supported + WEAK_SUPPORT_CREDIT * weak, total),
        evidence_coverage=_safe_ratio(with_evidence, total),
        unsupported_claim_rate=_safe_ratio(unsupported, total),
        contradiction_rate=_safe_ratio(touching_conflict, total),
        source_diversity=round(sum(diversity_pool) / len(diversity_pool), 2) if diversity_pool else 0.0,
        total_claims=total,
        supported_claims=supported,
        weak_claims=weak,
        unsupported_claims=unsupported,
        contradicted_claims=contradicted,
        reviewer_acceptance=reviewer_acceptance,
    )


def acceptance_score(decision: Optional[str]) -> Optional[float]:
    if decision is None:
        return None
    return ACCEPTANCE_SCORE.get(decision)


def review_rates(decisions: Iterable[str]) -> Dict[str, float]:
    """Human acceptance / edit / rejection / further-evidence rates."""
    values: List[str] = [d for d in decisions if d]
    total = len(values)
    if total == 0:
        return {
            "reviewed": 0,
            "acceptance_rate": 0.0,
            "edit_rate": 0.0,
            "rejection_rate": 0.0,
            "more_evidence_rate": 0.0,
        }
    count = lambda target: sum(1 for d in values if d == target)  # noqa: E731
    return {
        "reviewed": total,
        "acceptance_rate": _safe_ratio(count(ReviewDecision.ACCEPTED.value), total),
        "edit_rate": _safe_ratio(count(ReviewDecision.EDITED_ACCEPTED.value), total),
        "rejection_rate": _safe_ratio(count(ReviewDecision.REJECTED.value), total),
        "more_evidence_rate": _safe_ratio(
            count(ReviewDecision.MORE_EVIDENCE_REQUESTED.value), total
        ),
    }


def aggregate_metrics(rows: Sequence[AssuranceMetrics]) -> Dict[str, float]:
    """Fleet-level averages across analyses."""
    if not rows:
        return {
            "analyses": 0,
            "avg_groundedness": 0.0,
            "avg_evidence_coverage": 0.0,
            "avg_unsupported_rate": 0.0,
            "avg_contradiction_rate": 0.0,
            "avg_source_diversity": 0.0,
            "total_claims": 0,
            "total_unsupported": 0,
        }
    n = len(rows)
    mean = lambda values: round(sum(values) / n, 4)  # noqa: E731
    return {
        "analyses": n,
        "avg_groundedness": mean([r.groundedness for r in rows]),
        "avg_evidence_coverage": mean([r.evidence_coverage for r in rows]),
        "avg_unsupported_rate": mean([r.unsupported_claim_rate for r in rows]),
        "avg_contradiction_rate": mean([r.contradiction_rate for r in rows]),
        "avg_source_diversity": mean([r.source_diversity for r in rows]),
        "total_claims": sum(r.total_claims for r in rows),
        "total_unsupported": sum(r.unsupported_claims for r in rows),
    }
