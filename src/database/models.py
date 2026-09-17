"""SQLAlchemy ORM models.

The schema is deliberately dialect-agnostic: identifiers are string UUIDs and
the embedding column resolves to `pgvector.Vector` on PostgreSQL and to a JSON
text column on SQLite, so the same models back both deployment modes.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.config.settings import get_settings

_settings = get_settings()

try:  # pragma: no cover - exercised only in the PostgreSQL deployment
    from pgvector.sqlalchemy import Vector as _PGVector
except Exception:  # noqa: BLE001 - optional dependency
    _PGVector = None

PGVECTOR_AVAILABLE = _PGVector is not None and _settings.is_postgres


def new_uuid() -> str:
    return str(uuid.uuid4())


class JSONText(TypeDecorator):
    """Portable JSON column stored as text (works identically everywhere)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, default=str)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None or value == "":
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None


class EmbeddingColumn(TypeDecorator):
    """List[float] stored as JSON text on non-vector databases."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps([float(x) for x in value])

    def process_result_value(self, value: Any, dialect: Any) -> Optional[List[float]]:
        if not value:
            return None
        try:
            return [float(x) for x in json.loads(value)]
        except (TypeError, ValueError):
            return None


def embedding_type() -> Any:
    """pgvector on PostgreSQL, portable JSON text elsewhere."""
    if PGVECTOR_AVAILABLE:
        return _PGVector(_settings.embedding_dim)
    return EmbeddingColumn()


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.utcnow()


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    applicant_name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(64), default="Awaiting AI Analysis")
    scenario: Mapped[str] = mapped_column(Text, default="")
    key_signal: Mapped[str] = mapped_column(String(200), default="")
    opened_on: Mapped[str] = mapped_column(String(32), default="")
    timeline: Mapped[Any] = mapped_column(JSONText, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    documents: Mapped[List["Document"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    history_events: Mapped[List["CaseHistoryEvent"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    analyses: Mapped[List["AIAnalysis"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    document_name: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(80))
    document_ref: Mapped[str] = mapped_column(String(32), default="")  # e.g. DOC-3
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class CaseHistoryEvent(Base):
    """A dated event in the investigation record.

    Evidence does not only come from documents: monitoring alerts, status
    changes and investigative entries are cited too. Events carry a stable
    `EVT-YYYY-MM-DD-NNN` reference used identically by the retrieval index, the
    AI citations, the navigation layer and the audit trail.
    """

    __tablename__ = "case_history_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    event_ref: Mapped[str] = mapped_column(String(48), index=True)  # EVT-2026-05-06-001
    event_date: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="case_event")
    category: Mapped[str] = mapped_column(String(48), default="general")
    label: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped["Case"] = relationship(back_populates="history_events")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="history_event", cascade="all, delete-orphan"
    )

    @property
    def content(self) -> str:
        return f"{self.event_date} — {self.label}. {self.detail}".strip()


class DocumentChunk(Base):
    """A retrievable passage: either a slice of a document or a history event.

    One table, because the retriever, the evidence validator and the assurance
    metrics must treat every citable passage identically. `source_type` says
    which kind it is, so navigation never has to parse an identifier string.
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True
    )
    history_event_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("case_history_events.id", ondelete="CASCADE"), index=True, nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(24), default="document", index=True)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)  # DOC-3-CHUNK-2 / EVT-...
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = mapped_column(embedding_type(), nullable=True)
    chunk_metadata: Mapped[Any] = mapped_column(JSONText, default=dict)

    document: Mapped[Optional[Document]] = relationship(back_populates="chunks")
    history_event: Mapped[Optional[CaseHistoryEvent]] = relationship(back_populates="chunks")


class AIAnalysis(Base):
    __tablename__ = "ai_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(64))
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    generated_summary: Mapped[str] = mapped_column(Text)
    raw_output: Mapped[Any] = mapped_column(JSONText, default=dict)
    retrieved_source_ids: Mapped[Any] = mapped_column(JSONText, default=list)
    # The decision-ready brief: the full FinalCaseAssessment plus the fields the
    # dashboards and eval harness filter and aggregate on.
    assessment: Mapped[Any] = mapped_column(JSONText, default=dict)
    recommendation: Mapped[str] = mapped_column(String(48), default="", index=True)
    recommendation_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    concern_level: Mapped[str] = mapped_column(String(16), default="")
    material_unresolved_issues: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="analyses")
    claims: Mapped[List["Claim"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    contradictions: Mapped[List["Contradiction"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    metrics: Mapped[List["AssuranceMetricRow"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    reviews: Mapped[List["HumanReview"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    adjudicator_actions: Mapped[List["AdjudicatorAction"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis.id", ondelete="CASCADE"), index=True
    )
    claim_index: Mapped[int] = mapped_column(Integer, default=0)
    claim_text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(48), default="fact")
    assurance_status: Mapped[str] = mapped_column(String(32), default="UNSUPPORTED")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    retrieval_score: Mapped[float] = mapped_column(Float, default=0.0)
    entailment_score: Mapped[float] = mapped_column(Float, default=0.0)
    model_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")

    analysis: Mapped[AIAnalysis] = relationship(back_populates="claims")
    evidence: Mapped[List["ClaimEvidence"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(String(36), default="")
    chunk_id: Mapped[str] = mapped_column(String(36), default="")
    source_id: Mapped[str] = mapped_column(String(64), default="")
    source_type: Mapped[str] = mapped_column(String(24), default="document")
    document_ref: Mapped[str] = mapped_column(String(32), default="")
    document_date: Mapped[str] = mapped_column(String(48), default="")
    event_id: Mapped[str] = mapped_column(String(48), default="")
    event_date: Mapped[str] = mapped_column(String(32), default="")
    event_type: Mapped[str] = mapped_column(String(64), default="")
    document_name: Mapped[str] = mapped_column(String(200), default="")
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    cited_by_model: Mapped[bool] = mapped_column(Boolean, default=False)

    claim: Mapped[Claim] = relationship(back_populates="evidence")


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    conflicting_field: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    source_a_id: Mapped[str] = mapped_column(String(64), default="")
    source_a_document: Mapped[str] = mapped_column(String(200), default="")
    source_a_text: Mapped[str] = mapped_column(Text, default="")
    source_b_id: Mapped[str] = mapped_column(String(64), default="")
    source_b_document: Mapped[str] = mapped_column(String(200), default="")
    source_b_text: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    detector: Mapped[str] = mapped_column(String(48), default="heuristic")

    analysis: Mapped[AIAnalysis] = relationship(back_populates="contradictions")


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis.id", ondelete="CASCADE"), index=True
    )
    reviewer_name: Mapped[str] = mapped_column(String(120))
    reviewer_role: Mapped[str] = mapped_column(String(120), default="")
    decision: Mapped[str] = mapped_column(String(48))
    original_text: Mapped[str] = mapped_column(Text, default="")
    edited_text: Mapped[str] = mapped_column(Text, default="")
    diff_text: Mapped[str] = mapped_column(Text, default="")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    analysis: Mapped[AIAnalysis] = relationship(back_populates="reviews")


class AdjudicatorAction(Base):
    """A human decision recorded against the AI recommendation it responded to.

    The AI recommendation is copied onto the row rather than referenced, so the
    record of what the human saw survives any later re-analysis of the case.
    """

    __tablename__ = "adjudicator_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis.id", ondelete="CASCADE"), index=True
    )
    adjudicator_name: Mapped[str] = mapped_column(String(120))
    adjudicator_role: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(48), index=True)
    ai_recommendation: Mapped[str] = mapped_column(String(48), default="")
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    agreed_with_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    material_unresolved_issues: Mapped[int] = mapped_column(Integer, default=0)
    evidence_source_ids: Mapped[Any] = mapped_column(JSONText, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    analysis: Mapped["AIAnalysis"] = relationship(back_populates="adjudicator_actions")


class AuditEvent(Base):
    """Append-only application audit log. Repositories never update or delete."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    analysis_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_type: Mapped[str] = mapped_column(String(16), default="system")
    actor_name: Mapped[str] = mapped_column(String(120), default="system")
    action: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[Any] = mapped_column(JSONText, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class AssuranceMetricRow(Base):
    __tablename__ = "assurance_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("ai_analysis.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    groundedness: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    unsupported_claim_rate: Mapped[float] = mapped_column(Float, default=0.0)
    contradiction_rate: Mapped[float] = mapped_column(Float, default=0.0)
    source_diversity: Mapped[float] = mapped_column(Float, default=0.0)
    total_claims: Mapped[int] = mapped_column(Integer, default=0)
    supported_claims: Mapped[int] = mapped_column(Integer, default=0)
    weak_claims: Mapped[int] = mapped_column(Integer, default=0)
    unsupported_claims: Mapped[int] = mapped_column(Integer, default=0)
    contradicted_claims: Mapped[int] = mapped_column(Integer, default=0)
    reviewer_acceptance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    analysis: Mapped[AIAnalysis] = relationship(back_populates="metrics")
