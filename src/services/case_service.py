"""Case ingestion and read services.

Owns the write path from `data/synthetic_cases/<slug>/` into the database:
load -> clean -> chunk -> embed -> persist, and the read helpers the UI uses.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.audit.logger import EventType, log_event
from src.database.db import session_scope
from src.database.repositories import (
    AdjudicatorActionRepository,
    AnalysisRepository,
    CaseRepository,
    ChunkRepository,
    DocumentRepository,
    HistoryRepository,
    ReviewRepository,
)
from src.ingestion.chunker import chunk_text, clean_text
from src.ingestion.document_loader import LoadedCase, load_all_cases, load_case
from src.ingestion.embedding_service import EmbeddingProvider, get_embedding_provider
from src.models.schemas import SourceType

logger = logging.getLogger(__name__)


# Documents state their own date on a labelled line; surfacing it lets an
# adjudicator see how current a piece of evidence is without opening it.
_DOC_DATE = re.compile(
    r"^\s*(?:Report Date|Submitted|Interview date|Record obtained|Record produced|"
    r"Verification completed|Check completed|Cross-check completed|Review date|"
    r"Entry date|Generated|Verification returned|Alert log covering|Plan effective date|Date)\s*:\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def document_date(raw_text: str) -> str:
    match = _DOC_DATE.search(raw_text)
    return match.group(1).strip() if match else ""


def source_id_for(document_ref: str, chunk_index: int) -> str:
    return f"{document_ref}-CHUNK-{chunk_index}"


# Timeline categories map onto event types that read like the record they came
# from, so a citation says "monitoring alert" rather than "monitoring".
EVENT_TYPE_BY_CATEGORY = {
    "monitoring": "monitoring_alert",
    "administrative": "case_status_event",
    "investigative": "investigation_event",
    "statement": "applicant_statement_event",
    "financial": "financial_event",
    "employment": "employment_event",
    "travel": "travel_event",
    "residence": "residence_event",
    "legal": "legal_event",
}


def event_type_for(category: str) -> str:
    return EVENT_TYPE_BY_CATEGORY.get(category, f"{category or 'case'}_event")


def event_ref_for(event_date: str, ordinal: int) -> str:
    """Stable history identifier: EVT-2026-05-06-001."""
    return f"EVT-{event_date}-{ordinal:03d}"


@dataclass
class IngestionResult:
    case_number: str
    slug: str
    documents: int
    chunks: int


def ingest_case(
    loaded: LoadedCase, embedder: Optional[EmbeddingProvider] = None
) -> IngestionResult:
    """Ingest (or re-ingest) one case. Re-ingestion replaces documents/chunks."""
    embedder = embedder or get_embedding_provider()
    metadata = loaded.metadata

    with session_scope() as session:
        case = CaseRepository.upsert_by_slug(
            session,
            slug=metadata.slug,
            case_number=metadata.case_number,
            applicant_name=metadata.applicant_name,
            status=metadata.status.value,
            scenario=metadata.scenario,
            key_signal=metadata.key_signal,
            opened_on=metadata.opened_on,
            timeline=[event.model_dump() for event in metadata.timeline],
        )
        DocumentRepository.delete_for_case(session, case.id)
        HistoryRepository.delete_for_case(session, case.id)

        chunk_rows: List[Dict[str, Any]] = []
        texts: List[str] = []

        for position, loaded_doc in enumerate(loaded.documents, start=1):
            document_ref = f"DOC-{position}"
            document = DocumentRepository.create(
                session,
                case_id=case.id,
                document_name=loaded_doc.document_name,
                document_type=loaded_doc.document_type,
                document_ref=document_ref,
                raw_text=loaded_doc.raw_text,
            )
            for chunk in chunk_text(clean_text(loaded_doc.raw_text)):
                chunk_rows.append(
                    {
                        "document_id": document.id,
                        "case_id": case.id,
                        "source_id": source_id_for(document_ref, chunk.index),
                        "chunk_index": chunk.index,
                        "content": chunk.content,
                        "source_type": SourceType.DOCUMENT.value,
                        "chunk_metadata": {
                            "source_type": SourceType.DOCUMENT.value,
                            "document_name": loaded_doc.document_name,
                            "document_type": loaded_doc.document_type,
                            "document_ref": document_ref,
                            "document_date": document_date(loaded_doc.raw_text),
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                        },
                    }
                )
                texts.append(chunk.content)

        # History events are indexed alongside documents so that a monitoring
        # alert or an investigative entry can be cited, scored and navigated to
        # exactly like a document passage.
        per_date: Dict[str, int] = {}
        for position, event in enumerate(metadata.timeline):
            per_date[event.date] = per_date.get(event.date, 0) + 1
            event_ref = event_ref_for(event.date, per_date[event.date])
            row = HistoryRepository.create(
                session,
                case_id=case.id,
                event_ref=event_ref,
                event_date=event.date,
                event_type=event_type_for(event.category),
                category=event.category,
                label=event.label,
                detail=event.detail,
                ordinal=position,
            )
            content = f"{event.date} — {event.label}. {event.detail}".strip()
            chunk_rows.append(
                {
                    "history_event_id": row.id,
                    "case_id": case.id,
                    "source_id": event_ref,
                    "source_type": SourceType.CASE_HISTORY.value,
                    "chunk_index": 0,
                    "content": content,
                    "chunk_metadata": {
                        "source_type": SourceType.CASE_HISTORY.value,
                        "document_name": event.label,
                        "document_type": event_type_for(event.category),
                        "event_ref": event_ref,
                        "event_date": event.date,
                        "event_type": event_type_for(event.category),
                        "category": event.category,
                    },
                }
            )
            texts.append(content)

        vectors = embedder.embed(texts) if texts else []
        for row, vector in zip(chunk_rows, vectors):
            row["embedding"] = vector

        ChunkRepository.bulk_create(session, chunk_rows)

        log_event(
            EventType.CASE_INGESTED,
            f"Ingested {len(loaded.documents)} documents and "
            f"{len(metadata.timeline)} history events into {len(chunk_rows)} passages",
            case_id=case.id,
            metadata={
                "documents": len(loaded.documents),
                "history_events": len(metadata.timeline),
                "chunks": len(chunk_rows),
                "embedding_provider": embedder.name,
                "embedding_dim": embedder.dim,
            },
            session=session,
        )

        return IngestionResult(
            case_number=case.case_number,
            slug=case.slug,
            documents=len(loaded.documents),
            chunks=len(chunk_rows),
        )


def ingest_all_cases() -> List[IngestionResult]:
    embedder = get_embedding_provider()
    results = []
    for loaded in load_all_cases():
        results.append(ingest_case(loaded, embedder))
    return results


def reingest_slug(slug: str) -> IngestionResult:
    return ingest_case(load_case(slug))


# ---------------------------------------------------------------------------
# Read helpers (return plain dicts so Streamlit never holds ORM identities)
# ---------------------------------------------------------------------------
def list_cases() -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = []
        for case in CaseRepository.list_all(session):
            analysis = AnalysisRepository.latest_for_case(session, case.id)
            metrics = (
                AnalysisRepository.metrics_for_analysis(session, analysis.id) if analysis else None
            )
            review = (
                ReviewRepository.latest_for_analysis(session, analysis.id) if analysis else None
            )
            action = (
                AdjudicatorActionRepository.latest_for_analysis(session, analysis.id)
                if analysis
                else None
            )
            rows.append(
                {
                    "case_id": case.id,
                    "case_number": case.case_number,
                    "applicant_name": case.applicant_name,
                    "slug": case.slug,
                    "status": case.status,
                    "key_signal": case.key_signal,
                    "scenario": case.scenario,
                    "opened_on": case.opened_on,
                    "updated_at": case.updated_at,
                    "documents": len(case.documents),
                    "analysis_id": analysis.id if analysis else None,
                    "analysed": analysis is not None,
                    "model_name": analysis.model_name if analysis else None,
                    "groundedness": metrics.groundedness if metrics else None,
                    "evidence_coverage": metrics.evidence_coverage if metrics else None,
                    "unsupported_claims": metrics.unsupported_claims if metrics else None,
                    "contradictions": metrics.contradicted_claims if metrics else None,
                    "contradiction_flags": len(analysis.contradictions) if analysis else 0,
                    "review_decision": review.decision if review else None,
                    "reviewer": review.reviewer_name if review else None,
                    "recommendation": analysis.recommendation if analysis else None,
                    "recommendation_confidence": (
                        analysis.recommendation_confidence if analysis else None
                    ),
                    "concern_level": analysis.concern_level if analysis else None,
                    "material_unresolved_issues": (
                        analysis.material_unresolved_issues if analysis else None
                    ),
                    "adjudicator_action": action.action if action else None,
                    "agreed_with_ai": action.agreed_with_ai if action else None,
                }
            )
        return rows


def get_case_detail(case_id: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        case = CaseRepository.get(session, case_id)
        if case is None:
            return None
        documents = DocumentRepository.list_for_case(session, case.id)
        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "applicant_name": case.applicant_name,
            "slug": case.slug,
            "status": case.status,
            "key_signal": case.key_signal,
            "scenario": case.scenario,
            "opened_on": case.opened_on,
            "timeline": case.timeline or [],
            "chunk_count": ChunkRepository.count_for_case(session, case.id),
            "documents": [
                {
                    "document_id": document.id,
                    "document_ref": document.document_ref,
                    "document_name": document.document_name,
                    "document_type": document.document_type,
                    "raw_text": document.raw_text,
                    "document_date": document_date(document.raw_text),
                    "characters": len(document.raw_text),
                }
                for document in documents
            ],
        }


def get_case_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        case = CaseRepository.get_by_slug(session, slug)
        return get_case_detail(case.id) if case else None
