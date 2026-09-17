"""Data-access layer.

All persistence goes through these repositories: the Streamlit pages and the
services never build SQL. Every query is parameterised by SQLAlchemy, and the
audit repository is append-only by construction (no update/delete methods).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.database.models import (
    AdjudicatorAction,
    AIAnalysis,
    CaseHistoryEvent,
    AssuranceMetricRow,
    AuditEvent,
    Case,
    Claim,
    ClaimEvidence,
    Contradiction,
    Document,
    DocumentChunk,
    HumanReview,
)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
class CaseRepository:
    @staticmethod
    def create(session: Session, **kwargs: Any) -> Case:
        case = Case(**kwargs)
        session.add(case)
        session.flush()
        return case

    @staticmethod
    def upsert_by_slug(session: Session, slug: str, **kwargs: Any) -> Case:
        case = CaseRepository.get_by_slug(session, slug)
        if case is None:
            return CaseRepository.create(session, slug=slug, **kwargs)
        for key, value in kwargs.items():
            setattr(case, key, value)
        session.flush()
        return case

    @staticmethod
    def get(session: Session, case_id: str) -> Optional[Case]:
        return session.get(Case, case_id)

    @staticmethod
    def get_by_slug(session: Session, slug: str) -> Optional[Case]:
        return session.scalar(select(Case).where(Case.slug == slug))

    @staticmethod
    def get_by_number(session: Session, case_number: str) -> Optional[Case]:
        return session.scalar(select(Case).where(Case.case_number == case_number))

    @staticmethod
    def list_all(session: Session) -> List[Case]:
        return list(session.scalars(select(Case).order_by(Case.case_number)))

    @staticmethod
    def set_status(session: Session, case_id: str, status: str) -> None:
        case = session.get(Case, case_id)
        if case is not None:
            case.status = status
            case.updated_at = datetime.utcnow()
            session.flush()

    @staticmethod
    def count(session: Session) -> int:
        return int(session.scalar(select(func.count(Case.id))) or 0)


# ---------------------------------------------------------------------------
# Documents and chunks
# ---------------------------------------------------------------------------
class DocumentRepository:
    @staticmethod
    def create(session: Session, **kwargs: Any) -> Document:
        document = Document(**kwargs)
        session.add(document)
        session.flush()
        return document

    @staticmethod
    def list_for_case(session: Session, case_id: str) -> List[Document]:
        return list(
            session.scalars(
                select(Document)
                .where(Document.case_id == case_id)
                .order_by(Document.document_ref)
            )
        )

    @staticmethod
    def get(session: Session, document_id: str) -> Optional[Document]:
        return session.get(Document, document_id)

    @staticmethod
    def delete_for_case(session: Session, case_id: str) -> None:
        for document in DocumentRepository.list_for_case(session, case_id):
            session.delete(document)
        session.flush()


class HistoryRepository:
    """Case-history events — the non-document half of the evidence record."""

    @staticmethod
    def create(session: Session, **kwargs: Any) -> CaseHistoryEvent:
        event = CaseHistoryEvent(**kwargs)
        session.add(event)
        session.flush()
        return event

    @staticmethod
    def list_for_case(session: Session, case_id: str) -> List[CaseHistoryEvent]:
        return list(
            session.scalars(
                select(CaseHistoryEvent)
                .where(CaseHistoryEvent.case_id == case_id)
                .order_by(CaseHistoryEvent.event_date, CaseHistoryEvent.ordinal)
            )
        )

    @staticmethod
    def get_by_ref(session: Session, case_id: str, event_ref: str) -> Optional[CaseHistoryEvent]:
        return session.scalar(
            select(CaseHistoryEvent).where(
                CaseHistoryEvent.case_id == case_id, CaseHistoryEvent.event_ref == event_ref
            )
        )

    @staticmethod
    def delete_for_case(session: Session, case_id: str) -> None:
        for event in HistoryRepository.list_for_case(session, case_id):
            session.delete(event)
        session.flush()

    @staticmethod
    def count_for_case(session: Session, case_id: str) -> int:
        return int(
            session.scalar(
                select(func.count(CaseHistoryEvent.id)).where(
                    CaseHistoryEvent.case_id == case_id
                )
            )
            or 0
        )


class ChunkRepository:
    @staticmethod
    def bulk_create(session: Session, chunks: Iterable[Dict[str, Any]]) -> List[DocumentChunk]:
        rows = [DocumentChunk(**chunk) for chunk in chunks]
        session.add_all(rows)
        session.flush()
        return rows

    @staticmethod
    def list_for_case(session: Session, case_id: str) -> List[DocumentChunk]:
        return list(
            session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.case_id == case_id)
                .order_by(DocumentChunk.source_id)
            )
        )

    @staticmethod
    def get_by_source_id(
        session: Session, case_id: str, source_id: str
    ) -> Optional[DocumentChunk]:
        return session.scalar(
            select(DocumentChunk).where(
                DocumentChunk.case_id == case_id, DocumentChunk.source_id == source_id
            )
        )

    @staticmethod
    def count_for_case(session: Session, case_id: str) -> int:
        return int(
            session.scalar(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.case_id == case_id)
            )
            or 0
        )


# ---------------------------------------------------------------------------
# Analyses, claims, evidence, contradictions, metrics
# ---------------------------------------------------------------------------
class AnalysisRepository:
    @staticmethod
    def create(session: Session, **kwargs: Any) -> AIAnalysis:
        analysis = AIAnalysis(**kwargs)
        session.add(analysis)
        session.flush()
        return analysis

    @staticmethod
    def get(session: Session, analysis_id: str) -> Optional[AIAnalysis]:
        return session.scalar(
            select(AIAnalysis)
            .where(AIAnalysis.id == analysis_id)
            .options(
                selectinload(AIAnalysis.claims).selectinload(Claim.evidence),
                selectinload(AIAnalysis.contradictions),
                selectinload(AIAnalysis.metrics),
                selectinload(AIAnalysis.reviews),
                selectinload(AIAnalysis.adjudicator_actions),
            )
        )

    @staticmethod
    def latest_for_case(session: Session, case_id: str) -> Optional[AIAnalysis]:
        analysis = session.scalar(
            select(AIAnalysis)
            .where(AIAnalysis.case_id == case_id)
            .order_by(AIAnalysis.generated_at.desc())
            .limit(1)
        )
        return AnalysisRepository.get(session, analysis.id) if analysis else None

    @staticmethod
    def list_for_case(session: Session, case_id: str) -> List[AIAnalysis]:
        return list(
            session.scalars(
                select(AIAnalysis)
                .where(AIAnalysis.case_id == case_id)
                .order_by(AIAnalysis.generated_at.desc())
            )
        )

    @staticmethod
    def list_all(session: Session) -> List[AIAnalysis]:
        return list(session.scalars(select(AIAnalysis).order_by(AIAnalysis.generated_at)))

    @staticmethod
    def add_claim(session: Session, **kwargs: Any) -> Claim:
        claim = Claim(**kwargs)
        session.add(claim)
        session.flush()
        return claim

    @staticmethod
    def add_evidence(session: Session, **kwargs: Any) -> ClaimEvidence:
        evidence = ClaimEvidence(**kwargs)
        session.add(evidence)
        session.flush()
        return evidence

    @staticmethod
    def add_contradiction(session: Session, **kwargs: Any) -> Contradiction:
        row = Contradiction(**kwargs)
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def add_metrics(session: Session, **kwargs: Any) -> AssuranceMetricRow:
        row = AssuranceMetricRow(**kwargs)
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def metrics_for_analysis(session: Session, analysis_id: str) -> Optional[AssuranceMetricRow]:
        return session.scalar(
            select(AssuranceMetricRow).where(AssuranceMetricRow.analysis_id == analysis_id)
        )

    @staticmethod
    def all_metrics(session: Session) -> List[AssuranceMetricRow]:
        return list(
            session.scalars(select(AssuranceMetricRow).order_by(AssuranceMetricRow.created_at))
        )


# ---------------------------------------------------------------------------
# Human review
# ---------------------------------------------------------------------------
class ReviewRepository:
    @staticmethod
    def create(session: Session, **kwargs: Any) -> HumanReview:
        review = HumanReview(**kwargs)
        session.add(review)
        session.flush()
        return review

    @staticmethod
    def list_for_analysis(session: Session, analysis_id: str) -> List[HumanReview]:
        return list(
            session.scalars(
                select(HumanReview)
                .where(HumanReview.analysis_id == analysis_id)
                .order_by(HumanReview.created_at.desc())
            )
        )

    @staticmethod
    def latest_for_analysis(session: Session, analysis_id: str) -> Optional[HumanReview]:
        rows = ReviewRepository.list_for_analysis(session, analysis_id)
        return rows[0] if rows else None

    @staticmethod
    def list_all(session: Session) -> List[HumanReview]:
        return list(session.scalars(select(HumanReview).order_by(HumanReview.created_at)))


class AdjudicatorActionRepository:
    """Human decisions taken against an AI recommendation."""

    @staticmethod
    def create(session: Session, **kwargs: Any) -> AdjudicatorAction:
        action = AdjudicatorAction(**kwargs)
        session.add(action)
        session.flush()
        return action

    @staticmethod
    def list_for_analysis(session: Session, analysis_id: str) -> List[AdjudicatorAction]:
        return list(
            session.scalars(
                select(AdjudicatorAction)
                .where(AdjudicatorAction.analysis_id == analysis_id)
                .order_by(AdjudicatorAction.created_at.desc())
            )
        )

    @staticmethod
    def latest_for_analysis(session: Session, analysis_id: str) -> Optional[AdjudicatorAction]:
        rows = AdjudicatorActionRepository.list_for_analysis(session, analysis_id)
        return rows[0] if rows else None

    @staticmethod
    def list_for_case(session: Session, case_id: str) -> List[AdjudicatorAction]:
        return list(
            session.scalars(
                select(AdjudicatorAction)
                .where(AdjudicatorAction.case_id == case_id)
                .order_by(AdjudicatorAction.created_at.desc())
            )
        )

    @staticmethod
    def list_all(session: Session) -> List[AdjudicatorAction]:
        return list(
            session.scalars(select(AdjudicatorAction).order_by(AdjudicatorAction.created_at))
        )


# ---------------------------------------------------------------------------
# Audit (append-only: no update or delete methods exist by design)
# ---------------------------------------------------------------------------
class AuditRepository:
    @staticmethod
    def append(session: Session, **kwargs: Any) -> AuditEvent:
        event = AuditEvent(**kwargs)
        session.add(event)
        session.flush()
        return event

    @staticmethod
    def list_for_case(session: Session, case_id: str, limit: int = 500) -> List[AuditEvent]:
        return list(
            session.scalars(
                select(AuditEvent)
                .where(AuditEvent.case_id == case_id)
                .order_by(AuditEvent.timestamp.desc())
                .limit(limit)
            )
        )

    @staticmethod
    def list_recent(session: Session, limit: int = 500) -> List[AuditEvent]:
        return list(
            session.scalars(
                select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
            )
        )

    @staticmethod
    def count(session: Session) -> int:
        return int(session.scalar(select(func.count(AuditEvent.id))) or 0)
