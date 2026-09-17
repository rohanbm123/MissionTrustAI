"""Claim-level evidence validation — the core of CaseBrief.

Every claim is scored by a hybrid of independent signals rather than by an LLM
judging its own work:

    semantic    (default 0.40)  calibrated cosine between claim and best passage
    retrieval   (default 0.20)  rank of that passage + whether the model cited it
    entailment  (default 0.40)  does the passage actually assert the claim?

The entailment signal is a lexical-containment proxy offline — deliberately
weighted towards the numbers, dates and amounts that carry the factual load of
an adjudication claim — and an LLM verifier when a live provider is configured.
The weighted total maps onto SUPPORTED / WEAK_SUPPORT / UNSUPPORTED, with
CONTRADICTED taking precedence when the best evidence asserts a different value
for a field the claim states.

These weights and thresholds are a prototype heuristic, not a formal metric.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Sequence, Tuple

from src.config.settings import get_settings
from src.ingestion.embedding_service import (
    EmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
    tokenize,
)
from src.llm.prompts import get_prompt
from src.llm.provider import LLMError, LLMProvider
from src.models.schemas import (
    AssuranceStatus,
    EvidenceLink,
    GeneratedClaim,
    RetrievedChunk,
    ValidatedClaim,
)
from src.assurance.contradiction_detector import claim_conflicts_with_evidence, split_sentences
from src.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

_NUMERIC = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")

# Below this combined score a passage is noise rather than evidence, and showing
# it to a reviewer costs more attention than it returns.
EVIDENCE_DISPLAY_FLOOR = 0.30
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "by", "with", "that",
    "was", "were", "is", "are", "has", "have", "had", "at", "as", "from", "this", "it",
    "be", "been", "his", "her", "their", "its", "no", "not", "any", "all", "which",
    "applicant", "subject", "case", "file", "record", "records", "reported", "states",
}

VERDICT_SCORES = {
    "SUPPORTED": 1.0,
    "PARTIAL": 0.6,
    "NOT_SUPPORTED": 0.1,
    "CONTRADICTED": 0.0,
}


# ---------------------------------------------------------------------------
# Individual signals
# ---------------------------------------------------------------------------
def calibrate_semantic(cosine: float) -> float:
    """Map raw cosine onto [0, 1] across the configured calibration band."""
    settings = get_settings()
    floor, ceiling = settings.semantic_floor, settings.semantic_ceiling
    if ceiling <= floor:
        return max(0.0, min(1.0, cosine))
    return max(0.0, min(1.0, (cosine - floor) / (ceiling - floor)))


def content_tokens(text: str) -> List[str]:
    return [t for t in tokenize(text) if t not in _STOPWORDS and len(t) > 2]


def numeric_tokens(text: str) -> List[str]:
    return [m.group(0).replace("$", "").replace(",", "").rstrip(".") for m in _NUMERIC.finditer(text)]


def lexical_entailment(claim: str, evidence: str) -> float:
    """Offline entailment proxy: how much of the claim is actually asserted?

    Numbers, dates and amounts are weighted heavily because a fabricated
    adjudication claim almost always invents or alters one of them, while a
    faithful paraphrase preserves them exactly.
    """
    claim_terms = content_tokens(claim)
    if not claim_terms:
        return 0.0
    evidence_terms = set(content_tokens(evidence))
    lexical = sum(1 for term in claim_terms if term in evidence_terms) / len(claim_terms)

    claim_numbers = numeric_tokens(claim)
    if not claim_numbers:
        return round(lexical, 4)

    evidence_numbers = set(numeric_tokens(evidence))
    numeric_hit = sum(1 for n in claim_numbers if n in evidence_numbers) / len(claim_numbers)
    return round(0.55 * lexical + 0.45 * numeric_hit, 4)


def candidate_spans(text: str, max_window: int = 3) -> List[str]:
    """Sliding sentence windows over a passage.

    A claim is one assertion; a 700-character chunk is a dozen. Scoring the
    claim against the whole chunk dilutes the signal and, worse, gives the
    reviewer a wall of text instead of the line that actually settles it.
    """
    sentences = [s for s in split_sentences(text) if len(s) > 15]
    if not sentences:
        return [text]
    spans: List[str] = []
    for size in range(1, max_window + 1):
        for start in range(0, max(1, len(sentences) - size + 1)):
            window = " ".join(sentences[start : start + size])
            if window and window not in spans:
                spans.append(window)
    return spans or [text]


def retrieval_signal(rank: int, cited_by_model: bool, pool_size: int) -> float:
    """Rank decay over the claim's own evidence pool, plus a citation bonus."""
    if pool_size <= 0:
        return 0.0
    decay = max(0.0, 1.0 - (rank / max(pool_size, 4)))
    return round(min(1.0, 0.75 * decay + (0.25 if cited_by_model else 0.0)), 4)


def llm_entailment(
    provider: LLMProvider, claim: str, evidence_block: str
) -> Optional[Tuple[float, str]]:  # pragma: no cover - network path
    """Ask a live model to adjudicate entailment. Returns None on any failure."""
    try:
        payload = provider.complete_json(
            get_prompt("system").template,
            get_prompt("evidence_verification").template.format(
                claim=claim, evidence=evidence_block
            ),
        )
    except LLMError as exc:
        logger.warning("LLM evidence verification failed, using lexical signal: %s", exc)
        return None
    verdict = str(payload.get("verdict", "")).upper()
    if verdict not in VERDICT_SCORES:
        return None
    return VERDICT_SCORES[verdict], str(payload.get("reason", ""))[:400]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class EvidenceValidator:
    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        embedder: Optional[EmbeddingProvider] = None,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        self.settings = get_settings()
        self.retriever = retriever or Retriever()
        self.embedder = embedder or get_embedding_provider()
        self.provider = provider
        self.use_llm_verifier = provider is not None and not provider.is_demo

    def validate_claim(
        self,
        claim: GeneratedClaim,
        case_id: str,
        retrieved: Sequence[RetrievedChunk],
    ) -> ValidatedClaim:
        pool = self._candidate_pool(claim, case_id, retrieved)
        if not pool:
            return ValidatedClaim(
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                assurance_status=AssuranceStatus.UNSUPPORTED,
                confidence_score=0.0,
                model_confidence=claim.confidence,
                rationale="No evidence passage could be retrieved for this claim.",
            )

        claim_vector = self.embedder.embed_one(claim.claim_text)
        cited = set(claim.source_ids)

        scored: List[Tuple[float, float, float, RetrievedChunk, str]] = []
        for rank, chunk in enumerate(pool):
            retrieval = retrieval_signal(rank, chunk.source_id in cited, len(pool))
            semantic, entailment, span = self._best_span(claim.claim_text, claim_vector, chunk)
            scored.append((semantic, retrieval, entailment, chunk, span))

        scored.sort(key=lambda row: self._combine(row[0], row[1], row[2]), reverse=True)
        best_semantic, best_retrieval, best_entailment, best_chunk, best_span = scored[0]
        rationale_parts: List[str] = []

        if self.use_llm_verifier:  # pragma: no cover - network path
            # Each row is (semantic, retrieval, entailment, chunk, span); name the
            # two trailing members explicitly rather than star-unpacking, which
            # silently bound `chunk` to the span string.
            block = "\n\n".join(
                f"[{chunk.source_id}] {chunk.content}"
                for _s, _r, _e, chunk, _span in scored[: self.settings.evidence_top_k]
            )
            verdict = llm_entailment(self.provider, claim.claim_text, block)
            if verdict is not None:
                best_entailment, reason = verdict
                rationale_parts.append(f"Model verifier: {reason}")

        total = self._combine(best_semantic, best_retrieval, best_entailment)
        status = self._status(total)

        conflict_field = claim_conflicts_with_evidence(claim.claim_text, best_span)
        if conflict_field and best_entailment < 0.9:
            status = AssuranceStatus.CONTRADICTED
            rationale_parts.append(
                f"Best evidence asserts a different value for '{conflict_field.replace('_', ' ')}'."
            )

        rationale_parts.append(
            f"semantic {best_semantic:.2f} x{self.settings.weight_semantic:g} + "
            f"retrieval {best_retrieval:.2f} x{self.settings.weight_retrieval:g} + "
            f"entailment {best_entailment:.2f} x{self.settings.weight_entailment:g} "
            f"= {total:.2f}"
        )

        evidence = [
            EvidenceLink(
                source_id=chunk.source_id,
                chunk_id=chunk.chunk_id,
                case_id=chunk.case_id,
                source_type=chunk.source_type,
                document_id=chunk.document_id,
                document_ref=chunk.document_ref,
                document_name=chunk.display_name,
                document_date=chunk.document_date,
                event_id=chunk.event_id,
                event_date=chunk.event_date,
                event_type=chunk.event_type,
                evidence_text=span,
                relevance_score=round(self._combine(semantic, retrieval, entailment), 4),
                cited_by_model=chunk.source_id in cited,
            )
            for semantic, retrieval, entailment, chunk, span in scored[
                : self.settings.evidence_top_k
            ]
            if self._combine(semantic, retrieval, entailment) >= EVIDENCE_DISPLAY_FLOOR
        ]

        return ValidatedClaim(
            claim_text=claim.claim_text,
            claim_type=claim.claim_type,
            assurance_status=status,
            confidence_score=round(total, 4),
            semantic_score=round(best_semantic, 4),
            retrieval_score=round(best_retrieval, 4),
            entailment_score=round(best_entailment, 4),
            model_confidence=claim.confidence,
            evidence=evidence,
            rationale=" | ".join(rationale_parts),
        )

    def validate_all(
        self,
        claims: Sequence[GeneratedClaim],
        case_id: str,
        retrieved: Sequence[RetrievedChunk],
    ) -> List[ValidatedClaim]:
        return [self.validate_claim(claim, case_id, retrieved) for claim in claims]

    # -- internals ---------------------------------------------------------
    def _candidate_pool(
        self, claim: GeneratedClaim, case_id: str, retrieved: Sequence[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Claim-targeted retrieval, unioned with the passages the model cited."""
        pool: Dict[str, RetrievedChunk] = {}
        for chunk in self.retriever.retrieve_for_claim(case_id, claim.claim_text):
            pool[chunk.source_id] = chunk
        by_source = {chunk.source_id: chunk for chunk in retrieved}
        for source_id in claim.source_ids:
            if source_id in by_source:
                pool.setdefault(source_id, by_source[source_id])
        return list(pool.values())

    def _best_span(
        self, claim_text: str, claim_vector: Sequence[float], chunk: RetrievedChunk
    ) -> Tuple[float, float, str]:
        """Best-matching span within one chunk, with its two signals.

        The span is what the reviewer is shown, so it stays the tightest line
        that matches. Entailment, though, is also measured against the whole
        passage and the better of the two is kept: a claim may faithfully
        summarise several sentences of one record — "no delinquent accounts,
        collections, judgments or liens" covers two separate sentences of a
        financial report — and no single span can then entail it. Scoring only
        the best span marked such claims unsupported.
        """
        best = (0.0, 0.0, chunk.content[:400])
        best_score = -1.0
        for span in candidate_spans(chunk.content):
            semantic = calibrate_semantic(
                cosine_similarity(claim_vector, self.embedder.embed_one(span))
            )
            entailment = lexical_entailment(claim_text, span)
            score = self.settings.weight_semantic * semantic + (
                self.settings.weight_entailment * entailment
            )
            if score > best_score:
                best_score = score
                best = (semantic, entailment, span)

        semantic, entailment, span = best
        passage_entailment = lexical_entailment(claim_text, chunk.content)
        return (semantic, max(entailment, passage_entailment), span)

    def _combine(self, semantic: float, retrieval: float, entailment: float) -> float:
        s = self.settings
        total_weight = s.weight_semantic + s.weight_retrieval + s.weight_entailment
        if total_weight <= 0:
            return 0.0
        raw = (
            s.weight_semantic * semantic
            + s.weight_retrieval * retrieval
            + s.weight_entailment * entailment
        )
        return raw / total_weight

    def _status(self, total: float) -> AssuranceStatus:
        if total >= self.settings.threshold_supported:
            return AssuranceStatus.SUPPORTED
        if total >= self.settings.threshold_weak:
            return AssuranceStatus.WEAK_SUPPORT
        return AssuranceStatus.UNSUPPORTED
