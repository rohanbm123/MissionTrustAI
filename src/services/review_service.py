"""Human-in-the-loop review.

The reviewer is the decision-maker. The AI draft is never overwritten: an edit
is stored as a new `human_reviews` row holding the original text, the edited
text and a unified diff between them, so the provenance of what a human changed
is preserved alongside what the model originally said.
"""
from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional

from src.assurance.metrics import review_rates
from src.audit.logger import EventType, log_human_event
from src.config.settings import get_settings
from src.database.db import session_scope
from src.database.repositories import (
    AdjudicatorActionRepository,
    AnalysisRepository,
    CaseRepository,
    ReviewRepository,
)
from src.models.schemas import (
    AdjudicatorAction,
    CaseStatus,
    FinalCaseAssessment,
    RecommendationState,
    ReviewDecision,
)

DECISION_LABELS: Dict[str, str] = {
    ReviewDecision.ACCEPTED.value: "Accepted AI draft",
    ReviewDecision.EDITED_ACCEPTED.value: "Accepted with reviewer edits",
    ReviewDecision.REJECTED.value: "Rejected AI draft",
    ReviewDecision.MORE_EVIDENCE_REQUESTED.value: "Requested additional evidence",
}


ACTION_LABELS: Dict[str, str] = {
    AdjudicatorAction.PROCEED.value: "Proceeded to standard review",
    AdjudicatorAction.REQUEST_MORE_INFORMATION.value: "Requested additional information",
    AdjudicatorAction.ESCALATE.value: "Escalated for enhanced review",
}

ACTION_EVENT = {
    AdjudicatorAction.PROCEED.value: EventType.CASE_PROCEEDED,
    AdjudicatorAction.REQUEST_MORE_INFORMATION.value: EventType.ADDITIONAL_INFORMATION_REQUESTED,
    AdjudicatorAction.ESCALATE.value: EventType.CASE_ESCALATED,
}

ACTION_CASE_STATUS = {
    AdjudicatorAction.PROCEED.value: CaseStatus.REVIEW_COMPLETE.value,
    AdjudicatorAction.REQUEST_MORE_INFORMATION.value: CaseStatus.UNDER_REVIEW.value,
    AdjudicatorAction.ESCALATE.value: CaseStatus.UNDER_REVIEW.value,
}


class ReviewError(RuntimeError):
    """Raised when a review cannot be recorded."""


def build_diff(original: str, edited: str) -> str:
    """Unified diff of the AI draft against the reviewer's version."""
    if original.strip() == edited.strip():
        return ""
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            edited.splitlines(),
            fromfile="ai_draft",
            tofile="reviewer_edit",
            lineterm="",
            n=1,
        )
    )


def diff_stats(original: str, edited: str) -> Dict[str, int]:
    matcher = difflib.SequenceMatcher(None, original.split(), edited.split())
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"replace", "delete"}:
            removed += i2 - i1
        if tag in {"replace", "insert"}:
            added += j2 - j1
    return {
        "words_added": added,
        "words_removed": removed,
        "similarity_pct": int(round(matcher.ratio() * 100)),
    }


def record_review(
    *,
    case_id: str,
    analysis_id: str,
    decision: str,
    reviewer_name: Optional[str] = None,
    reviewer_role: Optional[str] = None,
    edited_text: str = "",
    review_notes: str = "",
) -> str:
    """Persist a reviewer decision and write the matching audit events."""
    if decision not in DECISION_LABELS:
        raise ReviewError(f"Unknown review decision '{decision}'.")

    settings = get_settings()
    reviewer_name = reviewer_name or settings.reviewer_name
    reviewer_role = reviewer_role or settings.reviewer_role

    with session_scope() as session:
        analysis = AnalysisRepository.get(session, analysis_id)
        if analysis is None:
            raise ReviewError(f"Analysis {analysis_id} was not found.")

        original = analysis.generated_summary
        final_text = edited_text.strip() or original
        diff = build_diff(original, final_text) if decision == ReviewDecision.EDITED_ACCEPTED.value else ""

        review = ReviewRepository.create(
            session,
            case_id=case_id,
            analysis_id=analysis_id,
            reviewer_name=reviewer_name,
            reviewer_role=reviewer_role,
            decision=decision,
            original_text=original,   # the AI draft is preserved verbatim, always
            edited_text=final_text,
            diff_text=diff,
            review_notes=review_notes.strip(),
        )

        new_status = (
            CaseStatus.UNDER_REVIEW.value
            if decision == ReviewDecision.MORE_EVIDENCE_REQUESTED.value
            else CaseStatus.REVIEW_COMPLETE.value
        )
        CaseRepository.set_status(session, case_id, new_status)
        review_id = review.id

    if decision == ReviewDecision.EDITED_ACCEPTED.value:
        log_human_event(
            EventType.SUMMARY_EDITED,
            "Reviewer edited the AI summary before acceptance",
            reviewer_name,
            case_id=case_id,
            analysis_id=analysis_id,
            metadata={"review_id": review_id, **diff_stats(original, final_text)},
        )

    log_human_event(
        EventType.EVIDENCE_REQUESTED
        if decision == ReviewDecision.MORE_EVIDENCE_REQUESTED.value
        else EventType.REVIEW_DECISION,
        f"{DECISION_LABELS[decision]} for analysis {analysis_id[:8]}",
        reviewer_name,
        case_id=case_id,
        analysis_id=analysis_id,
        metadata={
            "decision": decision,
            "reviewer_role": reviewer_role,
            "has_notes": bool(review_notes.strip()),
            "review_id": review_id,
        },
    )
    return review_id


def record_adjudicator_action(
    *,
    case_id: str,
    analysis_id: str,
    action: str,
    adjudicator_name: Optional[str] = None,
    adjudicator_role: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Record the human decision taken against an AI recommendation.

    The AI recommendation is never overwritten. It is copied onto the action row
    so the record of what the adjudicator was shown survives a later re-analysis,
    and whether the human agreed with it is derived rather than self-reported.
    """
    if action not in ACTION_LABELS:
        raise ReviewError(f"Unknown adjudicator action '{action}'.")

    settings = get_settings()
    adjudicator_name = adjudicator_name or settings.reviewer_name
    adjudicator_role = adjudicator_role or settings.reviewer_role
    chosen = AdjudicatorAction(action)

    with session_scope() as session:
        analysis = AnalysisRepository.get(session, analysis_id)
        if analysis is None:
            raise ReviewError(f"Analysis {analysis_id} was not found.")

        assessment = (
            FinalCaseAssessment.model_validate(analysis.assessment)
            if analysis.assessment
            else FinalCaseAssessment()
        )
        ai_recommendation = assessment.overall_recommendation
        agreed = chosen.aligned_recommendation == ai_recommendation
        evidence_ids = sorted(
            {
                link.source_id
                for reason in assessment.why_this_recommendation
                for link in reason.evidence
            }
        )

        row = AdjudicatorActionRepository.create(
            session,
            case_id=case_id,
            analysis_id=analysis_id,
            adjudicator_name=adjudicator_name,
            adjudicator_role=adjudicator_role,
            action=action,
            ai_recommendation=ai_recommendation.value,
            ai_confidence=assessment.recommendation_confidence,
            agreed_with_ai=agreed,
            material_unresolved_issues=assessment.material_unresolved_issues,
            evidence_source_ids=evidence_ids,
            notes=notes.strip(),
        )
        CaseRepository.set_status(session, case_id, ACTION_CASE_STATUS[action])
        result = {
            "action_id": row.id,
            "action": action,
            "action_label": ACTION_LABELS[action],
            "ai_recommendation": ai_recommendation.value,
            "agreed_with_ai": agreed,
            "confidence": assessment.recommendation_confidence,
        }

    metadata = {
        "action": action,
        "adjudicator_role": adjudicator_role,
        "ai_recommendation": ai_recommendation.value,
        "ai_confidence": assessment.recommendation_confidence,
        "agreed_with_ai": agreed,
        "material_unresolved_issues": assessment.material_unresolved_issues,
        "evidence_used": evidence_ids,
        "model": analysis_model_name(analysis_id),
        "prompt_version": analysis_prompt_version(analysis_id),
        "has_notes": bool(notes.strip()),
    }

    log_human_event(
        ACTION_EVENT[action],
        f"{ACTION_LABELS[action]} for {analysis_id[:8]}",
        adjudicator_name,
        case_id=case_id,
        analysis_id=analysis_id,
        metadata=metadata,
    )
    log_human_event(
        EventType.ADJUDICATOR_AGREED_WITH_AI if agreed else EventType.ADJUDICATOR_DISAGREED_WITH_AI,
        (
            f"Adjudicator {'agreed with' if agreed else 'departed from'} the AI recommendation "
            f"({ai_recommendation.display} → {ACTION_LABELS[action]})"
        ),
        adjudicator_name,
        case_id=case_id,
        analysis_id=analysis_id,
        metadata=metadata,
    )
    return result


def analysis_model_name(analysis_id: str) -> str:
    with session_scope() as session:
        analysis = AnalysisRepository.get(session, analysis_id)
        return analysis.model_name if analysis else ""


def analysis_prompt_version(analysis_id: str) -> str:
    with session_scope() as session:
        analysis = AnalysisRepository.get(session, analysis_id)
        return analysis.prompt_version if analysis else ""


def get_adjudicator_actions(analysis_id: str) -> List[Dict[str, Any]]:
    with session_scope() as session:
        return [
            {
                "action_id": row.id,
                "action": row.action,
                "action_label": ACTION_LABELS.get(row.action, row.action),
                "adjudicator_name": row.adjudicator_name,
                "adjudicator_role": row.adjudicator_role,
                "ai_recommendation": row.ai_recommendation,
                "ai_recommendation_label": (
                    RecommendationState(row.ai_recommendation).display
                    if row.ai_recommendation
                    else "—"
                ),
                "ai_confidence": row.ai_confidence,
                "agreed_with_ai": row.agreed_with_ai,
                "material_unresolved_issues": row.material_unresolved_issues,
                "evidence_source_ids": row.evidence_source_ids or [],
                "notes": row.notes,
                "created_at": row.created_at,
            }
            for row in AdjudicatorActionRepository.list_for_analysis(session, analysis_id)
        ]


def adjudicator_summary() -> Dict[str, Any]:
    """Fleet-level human agreement and action distribution."""
    with session_scope() as session:
        latest: Dict[str, Any] = {}
        for row in AdjudicatorActionRepository.list_all(session):
            latest[row.analysis_id] = row  # ordered ascending: last write wins
        rows = list(latest.values())

    total = len(rows)
    if total == 0:
        return {
            "actions": 0,
            "agreement_rate": 0.0,
            "proceed": 0,
            "request_more_information": 0,
            "escalate": 0,
        }
    return {
        "actions": total,
        "agreement_rate": round(sum(1 for r in rows if r.agreed_with_ai) / total, 4),
        "proceed": sum(1 for r in rows if r.action == AdjudicatorAction.PROCEED.value),
        "request_more_information": sum(
            1 for r in rows if r.action == AdjudicatorAction.REQUEST_MORE_INFORMATION.value
        ),
        "escalate": sum(1 for r in rows if r.action == AdjudicatorAction.ESCALATE.value),
    }


def get_reviews(analysis_id: str) -> List[Dict[str, Any]]:
    with session_scope() as session:
        return [
            {
                "review_id": review.id,
                "reviewer_name": review.reviewer_name,
                "reviewer_role": review.reviewer_role,
                "decision": review.decision,
                "decision_label": DECISION_LABELS.get(review.decision, review.decision),
                "original_text": review.original_text,
                "edited_text": review.edited_text,
                "diff_text": review.diff_text,
                "review_notes": review.review_notes,
                "created_at": review.created_at,
            }
            for review in ReviewRepository.list_for_analysis(session, analysis_id)
        ]


def review_summary() -> Dict[str, float]:
    """Fleet-level human-review rates for the assurance dashboard."""
    with session_scope() as session:
        latest: Dict[str, str] = {}
        for review in ReviewRepository.list_all(session):
            latest[review.analysis_id] = review.decision  # ordered by created_at ascending
        return review_rates(latest.values())
