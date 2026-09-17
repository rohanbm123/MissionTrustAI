"""RAG summarisation: retrieve evidence, prompt the model, validate the output.

The model is never allowed to summarise from anything but the retrieved
passages, and its response is validated against `CaseAnalysisOutput` before it
reaches the rest of the system. Structural failures are repaired with one
feedback retry; anything still invalid raises rather than silently degrading.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from src.llm.prompts import get_prompt
from src.llm.provider import LLMError, LLMProvider, Timer, get_llm_provider
from src.models.schemas import CaseAnalysisOutput, RetrievedChunk
from src.retrieval.retriever import Retriever, format_evidence_block

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    output: CaseAnalysisOutput
    retrieved_chunks: List[RetrievedChunk]
    model_name: str
    provider_name: str
    prompt_version: str
    system_prompt_version: str
    latency_ms: int
    demo_mode: bool
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def retrieved_source_ids(self) -> List[str]:
        return [chunk.source_id for chunk in self.retrieved_chunks]


def drop_invented_source_ids(
    output: CaseAnalysisOutput, chunks: List[RetrievedChunk], valid: Optional[set] = None
) -> CaseAnalysisOutput:
    """Strip citations that point at no passage in the case file.

    A fabricated citation is itself a grounding failure; removing it here means
    the claim is scored on real evidence only and shows up as unsupported if
    nothing genuine backs it. `valid` defaults to the retrieved set; callers pass
    the case's full source-ID set so that a citation to a real passage which
    simply fell outside top-k is kept rather than silently erased.
    """
    valid = valid if valid is not None else {chunk.source_id for chunk in chunks}
    for claim in output.claims:
        claim.source_ids = [sid for sid in claim.source_ids if sid in valid]
    for finding in output.key_findings:
        finding.source_ids = [sid for sid in finding.source_ids if sid in valid]
    for conflict in output.potential_conflicts:
        conflict.source_ids = [sid for sid in conflict.source_ids if sid in valid]
    return output


def generate_case_analysis(
    case_id: str,
    case_number: str,
    applicant_name: str,
    case_slug: str,
    *,
    retriever: Optional[Retriever] = None,
    provider: Optional[LLMProvider] = None,
    top_k: Optional[int] = None,
    prompt_name: str = "final_case_assessment",
) -> GenerationResult:
    retriever = retriever or Retriever()
    provider = provider or get_llm_provider()

    chunks = retriever.retrieve(case_id, top_k=top_k)
    if not chunks:
        raise LLMError(
            "No evidence was retrieved for this case. Run scripts/ingest_documents.py first."
        )

    system_spec = get_prompt("system")
    analysis_spec = get_prompt(prompt_name)
    user_prompt = analysis_spec.template.format(
        case_number=case_number,
        applicant_name=applicant_name,
        document_count=len({chunk.document_id for chunk in chunks}),
        evidence=format_evidence_block(chunks),
    )
    context = {"case_slug": case_slug, "case_id": case_id, "task": prompt_name}

    with Timer() as timer:
        payload = provider.complete_json(system_spec.template, user_prompt, context=context)
        output = _validate_with_retry(provider, system_spec.template, user_prompt, context, payload)

    corpus_source_ids = {chunk.source_id for chunk in retriever.all_chunks(case_id)}
    output = drop_invented_source_ids(output, chunks, corpus_source_ids or None)

    return GenerationResult(
        output=output,
        retrieved_chunks=chunks,
        model_name=provider.model,
        provider_name=provider.name,
        prompt_version=analysis_spec.version,
        system_prompt_version=system_spec.version,
        latency_ms=timer.elapsed_ms,
        demo_mode=provider.is_demo,
        raw_response=payload,
    )


def _validate_with_retry(
    provider: LLMProvider,
    system: str,
    user: str,
    context: Dict[str, Any],
    payload: Dict[str, Any],
) -> CaseAnalysisOutput:
    try:
        return CaseAnalysisOutput.model_validate(payload)
    except ValidationError as exc:
        logger.warning("Structured output failed validation, retrying once: %s", exc)
        repair = (
            f"{user}\n\nYour previous response did not satisfy the required schema. "
            f"Validation errors:\n{exc}\n\nReturn ONLY a corrected JSON object."
        )
        retry_payload = provider.complete_json(system, repair, context=context)
        try:
            return CaseAnalysisOutput.model_validate(retry_payload)
        except ValidationError as retry_exc:
            raise LLMError(
                f"Model output failed schema validation after one retry: {retry_exc}"
            ) from retry_exc
