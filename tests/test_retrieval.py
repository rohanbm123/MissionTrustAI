"""Ingestion, chunking and vector retrieval."""
from __future__ import annotations

import pytest

from src.ingestion.chunker import chunk_text, clean_text
from src.ingestion.document_loader import CaseLoadError, list_case_slugs, load_case
from src.ingestion.embedding_service import (
    LocalHashingEmbedder,
    cosine_similarity,
    get_embedding_provider,
)
from src.models.schemas import SourceType
from src.retrieval.retriever import Retriever, format_evidence_block


# -- corpus ----------------------------------------------------------------
def test_active_corpus_is_loadable_and_covers_the_decision_space():
    """The active caseload is configurable; every case in it must still load."""
    slugs = list_case_slugs()
    assert slugs, "no synthetic cases are generated"
    for slug in slugs:
        case = load_case(slug)
        assert case.documents
        assert case.metadata.case_number.startswith("PS-")
        assert case.metadata.timeline


def test_load_case_returns_documents_and_timeline():
    case = load_case("alex_morgan")
    assert case.metadata.case_number == "PS-2026-00182"
    assert len(case.documents) == 8
    assert len(case.metadata.timeline) >= 5
    assert all(doc.raw_text.strip() for doc in case.documents)


def test_unknown_case_raises():
    with pytest.raises(CaseLoadError):
        load_case("no_such_applicant")


# -- chunking --------------------------------------------------------------
def test_clean_text_normalises_whitespace():
    assert clean_text("a  b\r\n\r\n\r\n\r\nc") == "a b\n\nc"


def test_chunking_respects_size_and_produces_indices():
    text = "\n\n".join(f"Paragraph {i}. " + ("word " * 40) for i in range(12))
    chunks = chunk_text(text, chunk_size=400, chunk_overlap=60)
    assert len(chunks) > 1
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(len(c.content) <= 500 for c in chunks)


def test_chunking_empty_text_returns_nothing():
    assert chunk_text("   ") == []


def test_oversized_paragraph_is_split():
    chunks = chunk_text("Sentence one. " * 200, chunk_size=300, chunk_overlap=50)
    assert len(chunks) > 1


# -- embeddings ------------------------------------------------------------
def test_local_embedder_is_deterministic_and_normalised():
    embedder = LocalHashingEmbedder(128)
    a, b = embedder.embed_one("repayment plan effective March 2026"), embedder.embed_one(
        "repayment plan effective March 2026"
    )
    assert a == b
    assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-6)


def test_related_text_scores_above_unrelated_text():
    embedder = get_embedding_provider()
    claim = embedder.embed_one("The applicant entered a repayment plan in March 2026.")
    related = embedder.embed_one("Plan effective date: March 14, 2026. Monthly payment $325.")
    unrelated = embedder.embed_one("Foreign travel to Germany and Singapore was disclosed.")
    assert cosine_similarity(claim, related) > cosine_similarity(claim, unrelated)


def test_empty_text_embeds_to_zero_vector():
    assert set(LocalHashingEmbedder(64).embed_one("")) == {0.0}


# -- retrieval -------------------------------------------------------------
def test_ingestion_creates_chunks_with_source_ids(alex_case):
    chunks = Retriever().all_chunks(alex_case["case_id"])
    document_chunks = [c for c in chunks if c.source_type == SourceType.DOCUMENT]
    assert document_chunks
    assert all(
        c.source_id.startswith("DOC-") and "-CHUNK-" in c.source_id for c in document_chunks
    )
    assert all(c.content.strip() for c in chunks)
    assert len({c.document_id for c in document_chunks}) == 8


def test_history_events_are_indexed_as_retrievable_passages(alex_case):
    """Evidence is not only documents: history events share the index."""
    chunks = Retriever().all_chunks(alex_case["case_id"])
    events = [c for c in chunks if c.source_type == SourceType.CASE_HISTORY]
    assert events
    assert all(c.source_id.startswith("EVT-") for c in events)
    assert all(c.event_date and c.event_type for c in events)
    assert all(not c.document_id for c in events)


def test_every_passage_carries_its_navigation_metadata(alex_case):
    """Navigation must never need to parse an identifier string."""
    for chunk in Retriever().all_chunks(alex_case["case_id"]):
        assert chunk.case_id == alex_case["case_id"]
        if chunk.source_type == SourceType.DOCUMENT:
            assert chunk.document_ref and chunk.document_name
        else:
            assert chunk.event_id == chunk.source_id


def test_retrieval_is_case_scoped_and_ranked(alex_case):
    chunks = Retriever().retrieve(alex_case["case_id"], top_k=8)
    assert 0 < len(chunks) <= 8
    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True)


def test_claim_targeted_retrieval_finds_the_right_document(alex_case):
    chunks = Retriever().retrieve_for_claim(
        alex_case["case_id"], "The applicant entered a repayment plan in March 2026."
    )
    assert any("Payment Plan" in c.document_name or "Case Notes" in c.document_name for c in chunks)


def test_evidence_block_carries_source_ids(alex_case):
    chunks = Retriever().retrieve(alex_case["case_id"], top_k=3)
    block = format_evidence_block(chunks)
    for chunk in chunks:
        assert f"[{chunk.source_id}]" in block


def test_retrieval_for_unknown_case_is_empty():
    assert Retriever().retrieve("00000000-0000-0000-0000-000000000000") == []
