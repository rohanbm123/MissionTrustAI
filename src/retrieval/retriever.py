"""Evidence retrieval.

Case analysis is not a single-question task, so a single query embedding is a
poor probe. The retriever fans out over the standing adjudication facets
(financial, employment, travel, legal, residence, monitoring, mitigation,
missing information), merges by best score, and returns a de-duplicated,
rank-ordered evidence set. Every chunk carries the source ID that later appears
in citations, so the provenance chain is unbroken end to end.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from src.config.settings import get_settings
from src.ingestion.embedding_service import EmbeddingProvider, get_embedding_provider
from src.models.schemas import RetrievedChunk
from src.retrieval.vector_store import VectorStore, get_vector_store

FACET_QUERIES: List[str] = [
    "delinquent account balance credit report collection financial delinquency",
    "repayment plan payment agreement mitigation payments made",
    "employment history employer dates verification discrepancy separation",
    "foreign travel disclosure trips reported countries border crossing records",
    "criminal history legal citation court disposition arrest record",
    "residence address verification lease utility unverified period",
    "continuous monitoring alert generated adverse account activity",
    "applicant statement explanation provided by the subject",
    "investigator case notes analyst assessment unresolved outstanding",
    "missing documentation not received not verified requested records",
]


class Retriever:
    def __init__(
        self,
        store: Optional[VectorStore] = None,
        embedder: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.store = store or get_vector_store()
        self.embedder = embedder or get_embedding_provider()
        self.settings = get_settings()

    # -- public API --------------------------------------------------------
    def retrieve(
        self, case_id: str, queries: Optional[Sequence[str]] = None, top_k: Optional[int] = None
    ) -> List[RetrievedChunk]:
        """Multi-query retrieval over one case's evidence."""
        top_k = top_k or self.settings.retrieval_top_k
        queries = list(queries) if queries else FACET_QUERIES

        best: Dict[str, RetrievedChunk] = {}
        for query in queries:
            vector = self.embedder.embed_one(query)
            for chunk in self.store.search(case_id, vector, top_k=max(3, top_k // 2)):
                existing = best.get(chunk.source_id)
                if existing is None or chunk.score > existing.score:
                    best[chunk.source_id] = chunk

        ranked = sorted(best.values(), key=lambda c: c.score, reverse=True)[:top_k]
        return ranked

    def retrieve_for_claim(
        self, case_id: str, claim_text: str, top_k: Optional[int] = None
    ) -> List[RetrievedChunk]:
        """Targeted retrieval used by claim-level evidence validation."""
        top_k = top_k or self.settings.evidence_top_k
        vector = self.embedder.embed_one(claim_text)
        return self.store.search(case_id, vector, top_k=top_k)

    def all_chunks(self, case_id: str) -> List[RetrievedChunk]:
        return VectorStore.all_chunks(case_id)


def format_evidence_block(chunks: Sequence[RetrievedChunk]) -> str:
    """Render retrieved chunks as the evidence block handed to the model."""
    lines: List[str] = []
    for chunk in chunks:
        lines.append(
            f"[{chunk.source_id}] (document: {chunk.document_name}; "
            f"type: {chunk.document_type})\n{chunk.content}"
        )
    return "\n\n---\n\n".join(lines)
