"""Vector search over document chunks.

Two interchangeable back ends behind one interface:

* `PgVectorStore`  - ORDER BY embedding <=> :query in PostgreSQL (pgvector).
* `NumpyVectorStore` - in-process cosine over the case's chunks, used by the
  zero-setup SQLite demo. Case-scoped working sets are small (tens of chunks),
  so an exact scan is both fast and exactly reproducible.

Selection is automatic from DATABASE_URL; nothing upstream needs to care.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

import numpy as np
from sqlalchemy import text

from src.config.settings import get_settings
from src.database.db import session_scope
from src.database.models import PGVECTOR_AVAILABLE
from src.database.repositories import ChunkRepository
from src.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


class VectorStore(ABC):
    name = "abstract"

    @abstractmethod
    def search(
        self, case_id: str, query_vector: Sequence[float], top_k: int = 10
    ) -> List[RetrievedChunk]:
        ...

    @staticmethod
    def all_chunks(case_id: str) -> List[RetrievedChunk]:
        with session_scope() as session:
            return [_to_dto(row, 0.0) for row in ChunkRepository.list_for_case(session, case_id)]


def _to_dto(row, score: float) -> RetrievedChunk:
    """Build the DTO from stored metadata, never from parsing the source ID."""
    meta = row.chunk_metadata or {}
    return RetrievedChunk(
        source_id=row.source_id,
        chunk_id=row.id,
        case_id=row.case_id,
        source_type=meta.get("source_type", getattr(row, "source_type", "document")),
        document_id=row.document_id or "",
        document_ref=meta.get("document_ref", ""),
        document_name=meta.get("document_name", "Unknown source"),
        document_type=meta.get("document_type", "unknown"),
        document_date=meta.get("document_date", ""),
        event_id=meta.get("event_ref", ""),
        event_date=meta.get("event_date", ""),
        event_type=meta.get("event_type", ""),
        chunk_index=row.chunk_index,
        content=row.content,
        score=round(float(score), 4),
    )


class NumpyVectorStore(VectorStore):
    name = "numpy-cosine"

    def search(
        self, case_id: str, query_vector: Sequence[float], top_k: int = 10
    ) -> List[RetrievedChunk]:
        query = np.asarray(query_vector, dtype=np.float64)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []

        with session_scope() as session:
            rows = ChunkRepository.list_for_case(session, case_id)
            scored = []
            for row in rows:
                if not row.embedding:
                    continue
                vector = np.asarray(row.embedding, dtype=np.float64)
                denom = np.linalg.norm(vector) * query_norm
                if denom == 0:
                    continue
                scored.append((float(np.dot(vector, query) / denom), row))

            scored.sort(key=lambda pair: pair[0], reverse=True)
            return [_to_dto(row, score) for score, row in scored[:top_k]]


class PgVectorStore(VectorStore):
    """Cosine nearest-neighbour search executed inside PostgreSQL."""

    name = "pgvector"

    def search(
        self, case_id: str, query_vector: Sequence[float], top_k: int = 10
    ) -> List[RetrievedChunk]:  # pragma: no cover - requires PostgreSQL
        literal = "[" + ",".join(f"{float(v):.6f}" for v in query_vector) + "]"
        statement = text(
            """
            SELECT id, document_id, case_id, source_type, source_id, chunk_index,
                   content, chunk_metadata,
                   1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM document_chunks
            WHERE case_id = :case_id AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        )
        with session_scope() as session:
            result = session.execute(
                statement, {"vec": literal, "case_id": case_id, "k": top_k}
            )
            chunks: List[RetrievedChunk] = []
            for row in result:
                meta = row.chunk_metadata or {}
                if isinstance(meta, str):
                    import json

                    try:
                        meta = json.loads(meta)
                    except ValueError:
                        meta = {}
                chunks.append(
                    RetrievedChunk(
                        source_id=row.source_id,
                        chunk_id=row.id,
                        case_id=row.case_id,
                        source_type=meta.get("source_type", row.source_type or "document"),
                        document_id=row.document_id or "",
                        document_ref=meta.get("document_ref", ""),
                        document_name=meta.get("document_name", "Unknown source"),
                        document_type=meta.get("document_type", "unknown"),
                        document_date=meta.get("document_date", ""),
                        event_id=meta.get("event_ref", ""),
                        event_date=meta.get("event_date", ""),
                        event_type=meta.get("event_type", ""),
                        chunk_index=row.chunk_index,
                        content=row.content,
                        score=round(float(row.similarity), 4),
                    )
                )
            return chunks


_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the vector store matching the configured database."""
    global _store
    if _store is not None:
        return _store
    settings = get_settings()
    if settings.is_postgres and PGVECTOR_AVAILABLE:
        _store = PgVectorStore()
    else:
        if settings.is_postgres:
            logger.warning("pgvector unavailable; falling back to the in-process cosine index.")
        _store = NumpyVectorStore()
    return _store


def reset_vector_store() -> None:
    global _store
    _store = None
