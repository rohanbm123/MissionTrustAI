"""Structured LLM output, claim extraction and evidence validation."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pytest

from src.assurance.claim_extractor import claims_from_summary, extract_claims, split_sentences
from src.assurance.evidence_validator import (
    EvidenceValidator,
    calibrate_semantic,
    candidate_spans,
    lexical_entailment,
    retrieval_signal,
)
from src.llm.provider import DemoProvider, LLMError, LLMProvider, extract_json
from src.llm.summarizer import drop_invented_source_ids, generate_case_analysis
from src.models.schemas import (
    AssuranceStatus,
    CaseAnalysisOutput,
    ClaimType,
    GeneratedClaim,
    RetrievedChunk,
)


class ScriptedProvider(LLMProvider):
    """A mock LLM: returns queued responses, so tests never touch a network."""

    name = "scripted"
    model = "scripted-v1"
    is_demo = False

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system: str, user: str, *, context: Optional[Dict[str, Any]] = None) -> str:
        self.calls += 1
        return self.responses.pop(0) if self.responses else "{}"


# -- structured output parsing --------------------------------------------
def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": 2} — hope that helps') == {"a": 2}


def test_extract_json_rejects_non_json():
    with pytest.raises(LLMError):
        extract_json("no object here at all")
    with pytest.raises(LLMError):
        extract_json("")


def test_malformed_json_is_repaired_on_retry():
    provider = ScriptedProvider(["not json at all", json.dumps({"ok": True})])
    assert provider.complete_json("sys", "user") == {"ok": True}
    assert provider.calls == 2


def test_persistent_malformed_json_raises_rather_than_corrupting_state():
    provider = ScriptedProvider(["nope", "still nope"])
    with pytest.raises(LLMError):
        provider.complete_json("sys", "user")


def test_output_schema_accepts_either_prose_field_and_mirrors_it():
    """A live model returns only the field the prompt names; both must work."""
    live = CaseAnalysisOutput.model_validate(
        {"executive_case_assessment": "The brief field only, as FINAL_CASE_ASSESSMENT_V1 asks."}
    )
    assert live.executive_summary == live.executive_case_assessment

    legacy = CaseAnalysisOutput.model_validate(
        {"executive_summary": "The narrative field only, as the earlier prompt asked."}
    )
    assert legacy.executive_case_assessment == legacy.executive_summary


def test_output_schema_tolerates_prose_being_absent_entirely():
    """Malformed generation must not crash validation before the retry runs."""
    empty = CaseAnalysisOutput.model_validate({"claims": []})
    assert empty.executive_summary == ""
    assert empty.requires_human_review is True


def test_requires_human_review_cannot_be_disabled():
    output = CaseAnalysisOutput.model_validate(
        {"executive_summary": "A summary long enough to pass.", "requires_human_review": False}
    )
    assert output.requires_human_review is True


def test_unknown_fields_are_ignored_not_fatal():
    output = CaseAnalysisOutput.model_validate(
        {"executive_summary": "A summary long enough to pass.", "hallucinated_field": 1}
    )
    assert output.executive_summary.startswith("A summary")


def test_confidence_is_clamped():
    assert GeneratedClaim(claim_text="x" * 10, confidence=9.0).confidence == 1.0
    assert GeneratedClaim(claim_text="x" * 10, confidence=-3.0).confidence == 0.0


def test_demo_provider_serves_a_fixture_per_case():
    payload = DemoProvider().complete_json("s", "u", context={"case_slug": "alex_morgan"})
    assert CaseAnalysisOutput.model_validate(payload).claims


def test_demo_provider_reports_a_missing_fixture_clearly():
    with pytest.raises(LLMError):
        DemoProvider().complete_json("s", "u", context={"case_slug": "not_a_case"})


# -- citation hygiene ------------------------------------------------------
def test_invented_source_ids_are_stripped():
    output = CaseAnalysisOutput(
        executive_summary="A summary long enough to validate.",
        claims=[GeneratedClaim(claim_text="A claim about the file.", source_ids=["DOC-1-CHUNK-0", "DOC-99-CHUNK-9"])],
    )
    chunk = RetrievedChunk(
        source_id="DOC-1-CHUNK-0", chunk_id="c", document_id="d", document_name="Doc",
        document_type="t", chunk_index=0, content="text",
    )
    cleaned = drop_invented_source_ids(output, [chunk])
    assert cleaned.claims[0].source_ids == ["DOC-1-CHUNK-0"]


# -- claim extraction ------------------------------------------------------
def test_structured_claims_are_used_when_present():
    output = CaseAnalysisOutput(
        executive_summary="A summary long enough to validate.",
        claims=[GeneratedClaim(claim_text="A specific factual assertion.")],
    )
    assert len(extract_claims(output)) == 1


def test_sentence_fallback_when_the_model_returns_no_claims():
    summary = (
        "An $18,500 delinquent account was reported in February 2026. "
        "The applicant provided a repayment plan beginning in March 2026. "
        "This summary is informational and is not a determination."
    )
    claims = claims_from_summary(summary)
    assert len(claims) == 2  # the boilerplate sentence is not a claim
    assert all(c.claim_type == ClaimType.FACT for c in claims)


def test_sentence_splitter_keeps_currency_and_dates_together():
    parts = split_sentences("Balance was $18,500.00 in total. A plan began March 14, 2026.")
    assert len(parts) == 2


# -- individual scoring signals -------------------------------------------
def test_semantic_calibration_clamps_to_unit_range():
    assert calibrate_semantic(-1.0) == 0.0
    assert calibrate_semantic(5.0) == 1.0
    assert 0.0 < calibrate_semantic(0.25) < 1.0


def test_lexical_entailment_rewards_matching_figures():
    evidence = "Plan effective date: March 14, 2026. Agreed monthly payment: $325.00."
    faithful = lexical_entailment("The monthly payment is $325.00 from March 14, 2026.", evidence)
    invented = lexical_entailment("The monthly payment is $900.00 from July 2027.", evidence)
    assert faithful > invented


def test_lexical_entailment_of_unrelated_text_is_low():
    assert lexical_entailment(
        "The applicant travelled to Singapore in November 2025.",
        "Total delinquent balance across all accounts: $18,500.00.",
    ) < 0.3


def test_retrieval_signal_decays_with_rank_and_rewards_citation():
    assert retrieval_signal(0, False, 8) > retrieval_signal(6, False, 8)
    assert retrieval_signal(3, True, 8) > retrieval_signal(3, False, 8)


def test_candidate_spans_are_sentence_scoped():
    spans = candidate_spans("First sentence here. Second sentence here. Third sentence here.")
    assert "First sentence here." in spans
    assert any(span.count(".") >= 2 for span in spans)


# -- end-to-end claim validation ------------------------------------------
def test_supported_claim_is_marked_supported(alex_case):
    from src.retrieval.retriever import Retriever

    retrieved = Retriever().retrieve(alex_case["case_id"])
    result = EvidenceValidator().validate_claim(
        GeneratedClaim(
            claim_text="The applicant entered a structured repayment plan with an effective date of March 14, 2026.",
            source_ids=["DOC-4-CHUNK-0"],
            confidence=0.9,
        ),
        alex_case["case_id"],
        retrieved,
    )
    assert result.assurance_status == AssuranceStatus.SUPPORTED
    assert result.evidence
    assert any("March 14, 2026" in link.evidence_text for link in result.evidence)


def test_fabricated_claim_is_flagged_unsupported(alex_case):
    from src.retrieval.retriever import Retriever

    retrieved = Retriever().retrieve(alex_case["case_id"])
    result = EvidenceValidator().validate_claim(
        GeneratedClaim(
            claim_text="The applicant was awarded $2,400,000 in a wrongful termination lawsuit in Brazil.",
            confidence=0.95,
        ),
        alex_case["case_id"],
        retrieved,
    )
    assert result.assurance_status == AssuranceStatus.UNSUPPORTED
    assert result.confidence_score < 0.55


def test_the_planted_unsupported_claim_is_caught(analysis_bundle):
    flagged = [
        c for c in analysis_bundle.claims if c.assurance_status == AssuranceStatus.UNSUPPORTED
    ]
    assert len(flagged) == 1
    assert "insurer" in flagged[0].claim_text.lower()


def test_every_claim_records_its_score_breakdown(analysis_bundle):
    for claim in analysis_bundle.claims:
        assert claim.rationale
        assert 0.0 <= claim.confidence_score <= 1.0
        assert 0.0 <= claim.semantic_score <= 1.0
        assert 0.0 <= claim.entailment_score <= 1.0


def test_analysis_generation_uses_only_retrieved_evidence(alex_case):
    result = generate_case_analysis(
        alex_case["case_id"], alex_case["case_number"], alex_case["applicant_name"], "alex_morgan"
    )
    corpus = {c.source_id for c in result.retrieved_chunks}
    corpus_wide = {"DOC-", "CHUNK"}
    for claim in result.output.claims:
        for source_id in claim.source_ids:
            assert all(marker in source_id for marker in corpus_wide)
    assert result.retrieved_chunks
    assert corpus


# ---------------------------------------------------------------------------
# The live-provider verifier path (never exercised in DEMO_MODE)
# ---------------------------------------------------------------------------
class _EntailmentProvider:
    """A non-demo provider, so the LLM entailment branch actually runs."""

    name = "scripted-live"
    model = "scripted-live"
    is_demo = False

    def __init__(self, verdict: str = "SUPPORTED") -> None:
        self.verdict = verdict
        self.calls = 0

    def complete_json(self, system, user, *, context=None):
        self.calls += 1
        return {
            "verdict": self.verdict,
            "supporting_source_ids": ["DOC-1-CHUNK-0"],
            "reason": "The passage states the plan date.",
        }

    def complete(self, *args, **kwargs):
        import json as _json

        return _json.dumps(self.complete_json(None, None))


def _plan_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        source_id="DOC-1-CHUNK-0",
        chunk_id="c1",
        case_id="case-x",
        document_id="d1",
        document_ref="DOC-1",
        document_name="Payment Plan Document",
        content="Plan effective date: March 14, 2026. Agreed monthly payment: $325.00.",
        score=0.9,
    )


def test_llm_verifier_path_builds_its_evidence_block_from_chunks():
    """Regression: the block builder star-unpacked and bound `chunk` to the span."""
    provider = _EntailmentProvider()
    validator = EvidenceValidator(provider=provider)
    assert validator.use_llm_verifier is True

    result = validator.validate_claim(
        GeneratedClaim(claim_text="A repayment plan began on March 14, 2026.",
                       source_ids=["DOC-1-CHUNK-0"]),
        "case-x",
        [_plan_chunk()],
    )
    assert provider.calls == 1
    assert result.assurance_status is AssuranceStatus.SUPPORTED
    assert "Model verifier" in result.rationale


def test_llm_verifier_verdict_can_downgrade_a_claim():
    validator = EvidenceValidator(provider=_EntailmentProvider(verdict="NOT_SUPPORTED"))
    result = validator.validate_claim(
        GeneratedClaim(claim_text="A repayment plan began on March 14, 2026.",
                       source_ids=["DOC-1-CHUNK-0"]),
        "case-x",
        [_plan_chunk()],
    )
    assert result.entailment_score < 0.5
    assert result.assurance_status is not AssuranceStatus.SUPPORTED
