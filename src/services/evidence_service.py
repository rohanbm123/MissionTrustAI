"""Evidence navigation: citation -> exact location in the full case record.

Resolution is a database lookup keyed on `(case_id, source_id)`, never a parse
of the identifier string. `DOC-4-CHUNK-0` and `EVT-2026-05-06-001` are opaque
handles here; the stored `source_type` and the row they resolve to decide where
the adjudicator lands.

Traceability runs both ways:

* `resolve_source` — from an AI citation to the passage in the case record.
* `usages_for_source` — from a passage back to the reasons that cite it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.audit.logger import EventType, log_event
from src.database.db import session_scope
from src.database.repositories import (
    AnalysisRepository,
    CaseRepository,
    ChunkRepository,
    DocumentRepository,
    HistoryRepository,
)
from src.models.schemas import (
    ActorType,
    FinalCaseAssessment,
    HistoryEventView,
    SourceType,
)

SOURCE_NOT_FOUND = "Source could not be located in the case record."


@dataclass
class ResolvedSource:
    """Where a citation lives in the full case record."""

    found: bool
    case_id: str = ""
    case_number: str = ""
    source_id: str = ""
    source_type: str = SourceType.DOCUMENT.value
    tab: str = "Documents"
    document_id: str = ""
    document_ref: str = ""
    document_name: str = ""
    document_type: str = ""
    document_date: str = ""
    chunk_id: str = ""
    chunk_index: int = 0
    event_id: str = ""
    event_ref: str = ""
    event_date: str = ""
    event_type: str = ""
    label: str = ""
    content: str = ""
    message: str = ""

    @property
    def is_history(self) -> bool:
        return self.source_type == SourceType.CASE_HISTORY.value


def resolve_source(case_id: str, source_id: str) -> ResolvedSource:
    """Resolve a citation to its location. Never raises; reports not-found."""
    if not case_id or not source_id:
        return ResolvedSource(found=False, message=SOURCE_NOT_FOUND)

    with session_scope() as session:
        case = CaseRepository.get(session, case_id)
        if case is None:
            return ResolvedSource(found=False, message=SOURCE_NOT_FOUND)

        chunk = ChunkRepository.get_by_source_id(session, case_id, source_id)
        if chunk is None:
            return ResolvedSource(
                found=False,
                case_id=case_id,
                case_number=case.case_number,
                source_id=source_id,
                message=SOURCE_NOT_FOUND,
            )

        meta = chunk.chunk_metadata or {}
        source_type = meta.get("source_type", chunk.source_type or SourceType.DOCUMENT.value)

        if source_type == SourceType.CASE_HISTORY.value:
            event = chunk.history_event
            if event is None:
                return ResolvedSource(
                    found=False,
                    case_id=case_id,
                    case_number=case.case_number,
                    source_id=source_id,
                    message=SOURCE_NOT_FOUND,
                )
            return ResolvedSource(
                found=True,
                case_id=case_id,
                case_number=case.case_number,
                source_id=source_id,
                source_type=SourceType.CASE_HISTORY.value,
                tab="Case History",
                chunk_id=chunk.id,
                event_id=event.id,
                event_ref=event.event_ref,
                event_date=event.event_date,
                event_type=event.event_type,
                label=event.label,
                content=chunk.content,
            )

        document = chunk.document
        if document is None:
            return ResolvedSource(
                found=False,
                case_id=case_id,
                case_number=case.case_number,
                source_id=source_id,
                message=SOURCE_NOT_FOUND,
            )
        return ResolvedSource(
            found=True,
            case_id=case_id,
            case_number=case.case_number,
            source_id=source_id,
            source_type=SourceType.DOCUMENT.value,
            tab="Documents",
            document_id=document.id,
            document_ref=document.document_ref,
            document_name=document.document_name,
            document_type=document.document_type,
            document_date=meta.get("document_date", ""),
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            label=document.document_name,
            content=chunk.content,
        )


# ---------------------------------------------------------------------------
# Full case record
# ---------------------------------------------------------------------------
def document_sections(case_id: str, document_ref: str) -> List[Dict[str, Any]]:
    """The addressable passages of one document, in reading order.

    These are the very rows the retriever searches, so what the adjudicator
    reads and what the AI cited are the same objects — one source of truth.
    """
    with session_scope() as session:
        rows = [
            chunk
            for chunk in ChunkRepository.list_for_case(session, case_id)
            if (chunk.chunk_metadata or {}).get("document_ref") == document_ref
        ]
        rows.sort(key=lambda c: c.chunk_index)
        return [
            {
                "source_id": chunk.source_id,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for chunk in rows
        ]


def history_events(case_id: str) -> List[HistoryEventView]:
    with session_scope() as session:
        events = HistoryRepository.list_for_case(session, case_id)
        chunk_by_source = {
            chunk.source_id: chunk.id for chunk in ChunkRepository.list_for_case(session, case_id)
        }
        return [
            HistoryEventView(
                event_id=event.id,
                event_ref=event.event_ref,
                event_date=event.event_date,
                event_type=event.event_type,
                category=event.category,
                label=event.label,
                detail=event.detail,
                source_id=event.event_ref,
                chunk_id=chunk_by_source.get(event.event_ref, ""),
            )
            for event in events
        ]


def case_record_summary(case_id: str) -> Dict[str, Any]:
    """Counts and completeness for the Case Details overview."""
    with session_scope() as session:
        case = CaseRepository.get(session, case_id)
        if case is None:
            return {}
        documents = DocumentRepository.list_for_case(session, case.id)
        events = HistoryRepository.list_for_case(session, case.id)
        analysis = AnalysisRepository.latest_for_case(session, case.id)
        categories = sorted({d.document_type.replace("_", " ") for d in documents})
        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "applicant_name": case.applicant_name,
            "status": case.status,
            "opened_on": case.opened_on,
            "updated_at": case.updated_at,
            "key_signal": case.key_signal,
            "scenario": case.scenario,
            "document_count": len(documents),
            "history_event_count": len(events),
            "passage_count": ChunkRepository.count_for_case(session, case.id),
            "categories": categories,
            "has_brief": analysis is not None,
            "recommendation": analysis.recommendation if analysis else None,
            "analysis_id": analysis.id if analysis else None,
        }


def investigation_completeness(case_id: str) -> Dict[str, Any]:
    """A crude coverage read across the standing record types.

    Explicitly a completeness *indicator*, not an adjudicative judgement: it
    reports which categories of record the package contains, nothing more.
    """
    expected = {
        "investigation_summary": "Investigation summary",
        "financial_report": "Financial record review",
        "employment_history": "Employment verification",
        "applicant_statement": "Applicant statement",
        "case_notes": "Investigator notes",
    }
    with session_scope() as session:
        case = CaseRepository.get(session, case_id)
        if case is None:
            return {"present": [], "absent": [], "ratio": 0.0}
        present_types = {d.document_type for d in DocumentRepository.list_for_case(session, case.id)}
    present = [label for key, label in expected.items() if key in present_types]
    absent = [label for key, label in expected.items() if key not in present_types]
    return {
        "present": present,
        "absent": absent,
        "ratio": round(len(present) / len(expected), 3),
    }


# ---------------------------------------------------------------------------
# Reverse traceability: passage -> the reasons that cite it
# ---------------------------------------------------------------------------
@dataclass
class SourceUsage:
    reason_id: str
    reason: str
    kind: str = "reason"
    evidence_status: str = ""
    relevance_score: float = 0.0


def _latest_assessment(case_id: str) -> Optional[FinalCaseAssessment]:
    with session_scope() as session:
        analysis = AnalysisRepository.latest_for_case(session, case_id)
        if analysis is None or not analysis.assessment:
            return None
        try:
            return FinalCaseAssessment.model_validate(analysis.assessment)
        except Exception:  # noqa: BLE001 - a stale row must not break navigation
            return None


def usages_for_source(case_id: str, source_id: str) -> List[SourceUsage]:
    """Which parts of the current brief cite this passage."""
    assessment = _latest_assessment(case_id)
    if assessment is None:
        return []

    usages: List[SourceUsage] = []
    for reason in assessment.why_this_recommendation:
        link = next((e for e in reason.evidence if e.source_id == source_id), None)
        if link or source_id in reason.source_ids:
            usages.append(
                SourceUsage(
                    reason_id=reason.reason_id,
                    reason=reason.reason,
                    kind="reason",
                    evidence_status=reason.evidence_status.value,
                    relevance_score=link.relevance_score if link else 0.0,
                )
            )
    for factor in assessment.mitigating_factors:
        if any(e.source_id == source_id for e in factor.evidence):
            usages.append(SourceUsage(reason_id="", reason=factor.factor, kind="mitigating factor"))
    for concern in assessment.remaining_concerns:
        if any(e.source_id == source_id for e in concern.evidence):
            usages.append(SourceUsage(reason_id="", reason=concern.concern, kind="remaining concern"))
    return usages


def cited_source_ids(case_id: str) -> Dict[str, int]:
    """Every source the current brief cites, with how many times."""
    assessment = _latest_assessment(case_id)
    if assessment is None:
        return {}
    counts: Dict[str, int] = {}
    carriers = (
        list(assessment.why_this_recommendation)
        + list(assessment.mitigating_factors)
        + list(assessment.remaining_concerns)
    )
    for item in carriers:
        for link in item.evidence:
            counts[link.source_id] = counts.get(link.source_id, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Navigation state + audit
# ---------------------------------------------------------------------------
@dataclass
class EvidenceNavigation:
    """The deep-link payload carried between the brief and the case record."""

    case_id: str
    source_id: str
    source_type: str = SourceType.DOCUMENT.value
    document_ref: str = ""
    chunk_id: str = ""
    event_ref: str = ""
    reason_id: str = ""
    origin: str = "case_review"
    extras: Dict[str, Any] = field(default_factory=dict)

    def query_params(self) -> Dict[str, str]:
        params = {"case": self.extras.get("case_number", ""), "source": self.source_id}
        if self.document_ref:
            params["document"] = self.document_ref
        if self.event_ref:
            params["event"] = self.event_ref
        if self.reason_id:
            params["reason"] = self.reason_id
        return {k: v for k, v in params.items() if v}


def navigation_for(link: Any, case_id: str, case_number: str, reason_id: str = "") -> EvidenceNavigation:
    """Build the navigation payload from a structured evidence link."""
    return EvidenceNavigation(
        case_id=case_id,
        source_id=link.source_id,
        source_type=link.source_type.value
        if hasattr(link.source_type, "value")
        else str(link.source_type),
        document_ref=link.document_ref,
        chunk_id=link.chunk_id,
        event_ref=link.event_id,
        reason_id=reason_id,
        extras={"case_number": case_number, "document_name": link.document_name},
    )


def log_evidence_opened(
    navigation: EvidenceNavigation, reviewer: str, resolved: ResolvedSource
) -> None:
    """Record that an adjudicator followed a citation into the record."""
    log_event(
        EventType.EVIDENCE_SOURCE_OPENED,
        (
            f"Opened {navigation.source_id} in the full case record"
            if resolved.found
            else f"Attempted to open {navigation.source_id}; {SOURCE_NOT_FOUND}"
        ),
        case_id=navigation.case_id,
        actor_type=ActorType.HUMAN.value,
        actor_name=reviewer,
        metadata={
            "source_id": navigation.source_id,
            "source_type": navigation.source_type,
            "document_id": resolved.document_ref or navigation.document_ref,
            "event_id": resolved.event_ref or navigation.event_ref,
            "reason_id": navigation.reason_id,
            "origin": navigation.origin,
            "resolved": resolved.found,
        },
    )
