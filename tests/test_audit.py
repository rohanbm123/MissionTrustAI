"""Audit-event creation and human-review persistence."""
from __future__ import annotations

import pytest

from src.audit.logger import EventType, _scrub, get_case_trail, log_ai_event, log_human_event
from src.models.schemas import AdjudicatorAction, RecommendationState
from src.database.db import session_scope
from src.database.repositories import AuditRepository, ReviewRepository
from src.models.schemas import ReviewDecision
from src.services.review_service import (
    ACTION_LABELS,
    DECISION_LABELS,
    ReviewError,
    build_diff,
    diff_stats,
    get_adjudicator_actions,
    get_reviews,
    record_adjudicator_action,
    record_review,
    review_summary,
)


# -- audit -----------------------------------------------------------------
def test_audit_metadata_is_scrubbed_of_credentials():
    scrubbed = _scrub({"ANTHROPIC_API_KEY": "sk-live-123", "Authorization": "Bearer x", "chunks": 8})
    assert scrubbed["ANTHROPIC_API_KEY"] == "[redacted]"
    assert scrubbed["Authorization"] == "[redacted]"
    assert scrubbed["chunks"] == 8


def test_audit_metadata_truncates_oversized_values():
    scrubbed = _scrub({"blob": "x" * 5000})
    assert scrubbed["blob"].endswith("…[truncated]")
    assert len(scrubbed["blob"]) < 5000


def test_running_an_analysis_writes_the_expected_trail(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    types = {event.event_type for event in events}
    for expected in (
        EventType.CASE_INGESTED,
        EventType.ANALYSIS_REQUESTED,
        EventType.EVIDENCE_RETRIEVED,
        EventType.SUMMARY_GENERATED,
        EventType.CLAIMS_EXTRACTED,
        EventType.CLAIMS_VALIDATED,
        EventType.METRICS_COMPUTED,
    ):
        assert expected in types


def test_the_unsupported_claim_produces_its_own_audit_event(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    flagged = [e for e in events if e.event_type == EventType.UNSUPPORTED_CLAIM_DETECTED]
    assert flagged
    assert flagged[0].actor_type == "ai"


def test_generation_event_records_model_and_prompt_version(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    generated = next(e for e in events if e.event_type == EventType.SUMMARY_GENERATED)
    assert generated.event_metadata["prompt_version"] == "FINAL_CASE_ASSESSMENT_V1"
    assert generated.event_metadata["model"]
    assert "latency_ms" in generated.event_metadata


def test_events_are_returned_newest_first(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps, reverse=True)


def test_actor_type_separates_ai_from_human(alex_case):
    log_ai_event(EventType.ANALYSIS_REQUESTED, "ai action", case_id=alex_case["case_id"])
    log_human_event(EventType.CASE_OPENED, "human action", "Tester", case_id=alex_case["case_id"])
    events = get_case_trail(alex_case["case_id"])
    assert {"ai", "human"}.issubset({e.actor_type for e in events})


def test_audit_repository_exposes_no_mutation_path():
    """Append-only by construction: there is no update or delete method."""
    methods = {name for name in dir(AuditRepository) if not name.startswith("_")}
    assert methods == {"append", "list_for_case", "list_recent", "count"}


def test_audit_failure_never_raises(monkeypatch):
    from src.audit import logger as audit_logger

    def boom(*args, **kwargs):
        from sqlalchemy.exc import SQLAlchemyError

        raise SQLAlchemyError("database is down")

    monkeypatch.setattr(audit_logger.AuditRepository, "append", boom)
    assert audit_logger.log_event(EventType.ERROR, "should not raise") is None


# -- human review ----------------------------------------------------------
def test_diff_captures_reviewer_changes():
    diff = build_diff("The account was reported in February.", "The account was reported in March.")
    assert "February" in diff and "March" in diff


def test_identical_text_produces_no_diff():
    assert build_diff("same text", "same text  ") == ""


def test_diff_stats_report_word_movement():
    stats = diff_stats("one two three", "one two four five")
    assert stats["words_added"] >= 1 and stats["words_removed"] >= 1
    assert 0 <= stats["similarity_pct"] <= 100


def test_accepting_a_draft_persists_the_decision(analysis_bundle, alex_case):
    review_id = record_review(
        case_id=alex_case["case_id"],
        analysis_id=analysis_bundle.analysis_id,
        decision=ReviewDecision.ACCEPTED.value,
        reviewer_name="Tester",
        review_notes="Looks right.",
    )
    reviews = get_reviews(analysis_bundle.analysis_id)
    assert any(r["review_id"] == review_id for r in reviews)
    assert reviews[0]["decision_label"] == DECISION_LABELS[ReviewDecision.ACCEPTED.value]


def test_editing_preserves_the_original_ai_draft(analysis_bundle, alex_case):
    original = analysis_bundle.output.executive_summary
    record_review(
        case_id=alex_case["case_id"],
        analysis_id=analysis_bundle.analysis_id,
        decision=ReviewDecision.EDITED_ACCEPTED.value,
        reviewer_name="Tester",
        edited_text=original + " Reviewer addition: dispute outcome still pending.",
        review_notes="Added the outstanding item.",
    )
    latest = get_reviews(analysis_bundle.analysis_id)[0]
    assert latest["original_text"] == original          # never overwritten
    assert latest["edited_text"] != original
    assert latest["diff_text"]


def test_edit_writes_a_dedicated_audit_event(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    edits = [e for e in events if e.event_type == EventType.SUMMARY_EDITED]
    assert edits
    assert edits[0].actor_type == "human"
    assert "words_added" in edits[0].event_metadata


def test_requesting_more_evidence_keeps_the_case_under_review(analysis_bundle, alex_case):
    from src.database.repositories import CaseRepository

    record_review(
        case_id=alex_case["case_id"],
        analysis_id=analysis_bundle.analysis_id,
        decision=ReviewDecision.MORE_EVIDENCE_REQUESTED.value,
        reviewer_name="Tester",
    )
    with session_scope() as session:
        assert CaseRepository.get(session, alex_case["case_id"]).status == "Under Review"


def test_unknown_decision_is_rejected(analysis_bundle, alex_case):
    with pytest.raises(ReviewError):
        record_review(
            case_id=alex_case["case_id"],
            analysis_id=analysis_bundle.analysis_id,
            decision="rubber_stamp",
        )


def test_review_for_missing_analysis_is_rejected(alex_case):
    with pytest.raises(ReviewError):
        record_review(
            case_id=alex_case["case_id"],
            analysis_id="00000000-0000-0000-0000-000000000000",
            decision=ReviewDecision.ACCEPTED.value,
        )


def test_review_history_is_append_only(analysis_bundle):
    with session_scope() as session:
        rows = ReviewRepository.list_for_analysis(session, analysis_bundle.analysis_id)
    assert len(rows) >= 2  # earlier decisions in this module are all retained


def test_review_summary_reports_rates():
    summary = review_summary()
    assert summary["reviewed"] >= 1
    assert 0.0 <= summary["acceptance_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Adjudicator decisions
# ---------------------------------------------------------------------------
def test_recommendation_generation_is_audited(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    generated = [
        e for e in events if e.event_type == EventType.OVERALL_RECOMMENDATION_GENERATED
    ]
    assert generated
    metadata = generated[0].event_metadata
    for key in (
        "recommendation",
        "confidence",
        "material_unresolved_issues",
        "evidence_used",
        "prompt_version",
        "model",
    ):
        assert key in metadata
    assert metadata["recommendation"] in {s.value for s in RecommendationState}


def test_proceeding_records_agreement_and_preserves_the_ai_recommendation(
    analysis_bundle, alex_case
):
    ai_state = analysis_bundle.assessment.overall_recommendation
    result = record_adjudicator_action(
        case_id=alex_case["case_id"],
        analysis_id=analysis_bundle.analysis_id,
        action=AdjudicatorAction.PROCEED.value,
        adjudicator_name="Tester",
        notes="Repayment plan confirmed current.",
    )
    assert result["agreed_with_ai"] is (
        ai_state is RecommendationState.PROCEED_TO_STANDARD_REVIEW
    )
    stored = get_adjudicator_actions(analysis_bundle.analysis_id)[0]
    assert stored["ai_recommendation"] == ai_state.value  # never overwritten
    assert stored["action_label"] == ACTION_LABELS[AdjudicatorAction.PROCEED.value]


def test_departing_from_the_recommendation_is_recorded_as_disagreement(
    analysis_bundle, alex_case
):
    record_adjudicator_action(
        case_id=alex_case["case_id"],
        analysis_id=analysis_bundle.analysis_id,
        action=AdjudicatorAction.ESCALATE.value,
        adjudicator_name="Tester",
    )
    latest = get_adjudicator_actions(analysis_bundle.analysis_id)[0]
    assert latest["action"] == AdjudicatorAction.ESCALATE.value
    assert latest["agreed_with_ai"] is False

    events = get_case_trail(alex_case["case_id"])
    assert any(e.event_type == EventType.ADJUDICATOR_DISAGREED_WITH_AI for e in events)
    assert any(e.event_type == EventType.CASE_ESCALATED for e in events)


def test_agreement_writes_its_own_audit_event(analysis_bundle, alex_case):
    events = get_case_trail(alex_case["case_id"])
    assert any(e.event_type == EventType.ADJUDICATOR_AGREED_WITH_AI for e in events)


def test_requesting_information_is_audited_with_its_own_event(analysis_bundle, alex_case):
    record_adjudicator_action(
        case_id=alex_case["case_id"],
        analysis_id=analysis_bundle.analysis_id,
        action=AdjudicatorAction.REQUEST_MORE_INFORMATION.value,
        adjudicator_name="Tester",
    )
    events = get_case_trail(alex_case["case_id"])
    assert any(
        e.event_type == EventType.ADDITIONAL_INFORMATION_REQUESTED for e in events
    )


def test_adjudicator_action_history_is_append_only(analysis_bundle):
    history = get_adjudicator_actions(analysis_bundle.analysis_id)
    assert len(history) >= 3  # every decision taken above is retained


def test_unknown_adjudicator_action_is_rejected(analysis_bundle, alex_case):
    with pytest.raises(ReviewError):
        record_adjudicator_action(
            case_id=alex_case["case_id"],
            analysis_id=analysis_bundle.analysis_id,
            action="approve_clearance",
        )
