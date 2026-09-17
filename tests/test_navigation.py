"""Evidence navigation: citation -> exact location in the record, and back again."""
from __future__ import annotations

import pytest

from src.audit.logger import EventType, get_case_trail
from src.models.schemas import SourceType
from src.services.evidence_service import (
    SOURCE_NOT_FOUND,
    EvidenceNavigation,
    case_record_summary,
    cited_source_ids,
    document_sections,
    history_events,
    investigation_completeness,
    log_evidence_opened,
    navigation_for,
    resolve_source,
    usages_for_source,
)
from src.retrieval.retriever import Retriever


# ---------------------------------------------------------------------------
# Resolution: citation -> location
# ---------------------------------------------------------------------------
def test_document_citation_resolves_to_its_document_and_passage(alex_case):
    resolved = resolve_source(alex_case["case_id"], "DOC-4-CHUNK-0")
    assert resolved.found is True
    assert resolved.tab == "Documents"
    assert resolved.source_type == SourceType.DOCUMENT.value
    assert resolved.document_ref == "DOC-4"
    assert resolved.document_name == "Payment Plan Document"
    assert resolved.chunk_index == 0
    assert resolved.content


def test_history_citation_resolves_to_its_event(alex_case):
    resolved = resolve_source(alex_case["case_id"], "EVT-2026-05-02-001")
    assert resolved.found is True
    assert resolved.tab == "Case History"
    assert resolved.is_history is True
    assert resolved.event_ref == "EVT-2026-05-02-001"
    assert resolved.event_type == "monitoring_alert"
    assert resolved.event_date == "2026-05-02"
    assert "monitoring alert" in resolved.label.lower()


def test_resolution_is_by_stored_type_not_by_parsing_the_identifier(alex_case):
    """The destination comes from the row, not from the shape of the string."""
    for chunk in Retriever().all_chunks(alex_case["case_id"]):
        resolved = resolve_source(alex_case["case_id"], chunk.source_id)
        assert resolved.found is True
        assert resolved.source_type == chunk.source_type.value
        expected_tab = (
            "Case History" if chunk.source_type == SourceType.CASE_HISTORY else "Documents"
        )
        assert resolved.tab == expected_tab


def test_resolution_is_case_scoped(alex_case, all_cases):
    """A source ID from another case must not resolve against this one."""
    other = all_cases["elena_vasquez"]
    resolved = resolve_source(other, "EVT-2026-05-02-001")  # an Alex Morgan event
    assert resolved.found is False
    assert resolved.message == SOURCE_NOT_FOUND


def test_missing_source_reports_rather_than_raises(alex_case):
    resolved = resolve_source(alex_case["case_id"], "DOC-99-CHUNK-7")
    assert resolved.found is False
    assert resolved.message == SOURCE_NOT_FOUND
    assert resolved.case_number == alex_case["case_number"]


@pytest.mark.parametrize("case_id,source_id", [("", "DOC-1-CHUNK-0"), ("x", ""), ("", "")])
def test_empty_navigation_input_is_handled(case_id, source_id):
    assert resolve_source(case_id, source_id).found is False


def test_unknown_case_is_handled(alex_case):
    assert resolve_source("not-a-case-id", "DOC-4-CHUNK-0").found is False


# ---------------------------------------------------------------------------
# The record the adjudicator reads is the record the AI retrieved
# ---------------------------------------------------------------------------
def test_document_sections_are_the_same_rows_the_retriever_searches(alex_case):
    sections = document_sections(alex_case["case_id"], "DOC-4")
    assert sections
    assert [s["source_id"] for s in sections] == ["DOC-4-CHUNK-0", "DOC-4-CHUNK-1"]

    retrieved = {
        c.source_id: c.content
        for c in Retriever().all_chunks(alex_case["case_id"])
    }
    for section in sections:
        assert retrieved[section["source_id"]] == section["content"]


def test_history_events_expose_their_citation_identifiers(alex_case):
    events = history_events(alex_case["case_id"])
    assert len(events) == 8
    assert all(e.event_ref.startswith("EVT-") for e in events)
    assert all(e.source_id == e.event_ref for e in events)
    assert all(e.chunk_id for e in events)
    assert [e.event_date for e in events] == sorted(e.event_date for e in events)


def test_history_event_ids_are_stable_and_dated(alex_case):
    refs = [e.event_ref for e in history_events(alex_case["case_id"])]
    assert "EVT-2026-05-02-001" in refs
    assert len(set(refs)) == len(refs)


# ---------------------------------------------------------------------------
# Reverse traceability: passage -> the reasons that cite it
# ---------------------------------------------------------------------------
def test_a_cited_passage_names_the_reason_that_uses_it(analysis_bundle, alex_case):
    reason = analysis_bundle.assessment.why_this_recommendation[0]
    assert reason.evidence, "the flagship reason should carry evidence"
    source_id = reason.evidence[0].source_id

    usages = usages_for_source(alex_case["case_id"], source_id)
    assert usages
    assert any(u.reason_id == reason.reason_id for u in usages)
    assert any(u.kind == "reason" for u in usages)


def test_an_uncited_passage_reports_no_usage(analysis_bundle, alex_case):
    cited = cited_source_ids(alex_case["case_id"])
    uncited = next(
        (
            c.source_id
            for c in Retriever().all_chunks(alex_case["case_id"])
            if c.source_id not in cited
        ),
        None,
    )
    if uncited is None:
        pytest.skip("every passage in this case is cited")
    assert usages_for_source(alex_case["case_id"], uncited) == []


def test_cited_source_ids_all_resolve(analysis_bundle, alex_case):
    """Nothing the brief cites may be unreachable in the record."""
    for source_id in cited_source_ids(alex_case["case_id"]):
        assert resolve_source(alex_case["case_id"], source_id).found is True


# ---------------------------------------------------------------------------
# Navigation payload
# ---------------------------------------------------------------------------
def test_navigation_payload_carries_the_destination_structurally(analysis_bundle, alex_case):
    reason = analysis_bundle.assessment.why_this_recommendation[0]
    link = reason.evidence[0]
    navigation = navigation_for(
        link, alex_case["case_id"], alex_case["case_number"], reason.reason_id
    )
    assert navigation.case_id == alex_case["case_id"]
    assert navigation.source_id == link.source_id
    assert navigation.reason_id == reason.reason_id
    assert navigation.source_type in {SourceType.DOCUMENT.value, SourceType.CASE_HISTORY.value}
    if navigation.source_type == SourceType.DOCUMENT.value:
        assert navigation.document_ref
    else:
        assert navigation.event_ref


def test_navigation_query_params_are_deep_linkable(analysis_bundle, alex_case):
    reason = analysis_bundle.assessment.why_this_recommendation[0]
    navigation = navigation_for(
        reason.evidence[0], alex_case["case_id"], alex_case["case_number"], reason.reason_id
    )
    params = navigation.query_params()
    assert params["case"] == alex_case["case_number"]
    assert params["source"] == reason.evidence[0].source_id
    assert params["reason"] == reason.reason_id
    assert "document" in params or "event" in params


def test_back_navigation_preserves_the_originating_reason(analysis_bundle, alex_case):
    reason = analysis_bundle.assessment.why_this_recommendation[0]
    navigation = navigation_for(
        reason.evidence[0], alex_case["case_id"], alex_case["case_number"], reason.reason_id
    )
    # The return path uses the same reason id the outbound trip carried.
    assert navigation.reason_id == reason.reason_id
    assert reason.reason_id.startswith("reason-")


def test_reason_ids_are_unique_within_a_brief(analysis_bundle):
    ids = [r.reason_id for r in analysis_bundle.assessment.why_this_recommendation]
    assert all(ids)
    assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------------------
# Case record overview
# ---------------------------------------------------------------------------
def test_case_record_summary_counts_documents_and_history(alex_case):
    summary = case_record_summary(alex_case["case_id"])
    assert summary["document_count"] == 8
    assert summary["history_event_count"] == 8
    assert summary["passage_count"] >= summary["document_count"] + summary["history_event_count"]
    assert summary["case_number"] == alex_case["case_number"]


def test_investigation_completeness_reports_present_and_absent_types(alex_case):
    completeness = investigation_completeness(alex_case["case_id"])
    assert 0.0 <= completeness["ratio"] <= 1.0
    assert "Financial record review" in completeness["present"]
    assert len(completeness["present"]) + len(completeness["absent"]) == 5


def test_case_record_summary_of_unknown_case_is_empty():
    assert case_record_summary("not-a-case-id") == {}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def test_opening_evidence_is_audited(analysis_bundle, alex_case):
    navigation = EvidenceNavigation(
        case_id=alex_case["case_id"],
        source_id="DOC-4-CHUNK-0",
        document_ref="DOC-4",
        reason_id="reason-1",
    )
    resolved = resolve_source(alex_case["case_id"], "DOC-4-CHUNK-0")
    log_evidence_opened(navigation, "Tester", resolved)

    events = get_case_trail(alex_case["case_id"])
    opened = [e for e in events if e.event_type == EventType.EVIDENCE_SOURCE_OPENED]
    assert opened
    metadata = opened[0].event_metadata
    assert metadata["source_id"] == "DOC-4-CHUNK-0"
    assert metadata["reason_id"] == "reason-1"
    assert metadata["document_id"] == "DOC-4"
    assert metadata["resolved"] is True


def test_a_broken_link_is_audited_as_unresolved(analysis_bundle, alex_case):
    navigation = EvidenceNavigation(case_id=alex_case["case_id"], source_id="DOC-99-CHUNK-7")
    resolved = resolve_source(alex_case["case_id"], "DOC-99-CHUNK-7")
    log_evidence_opened(navigation, "Tester", resolved)

    opened = [
        e
        for e in get_case_trail(alex_case["case_id"])
        if e.event_type == EventType.EVIDENCE_SOURCE_OPENED
    ]
    assert any(e.event_metadata.get("resolved") is False for e in opened)
