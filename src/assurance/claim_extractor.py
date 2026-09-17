"""Turn a generated summary into atomic, individually checkable claims.

Primary path: the structured output already carries `claims`, because the
analysis prompt requires them. Fallback path: split the executive summary into
sentences so that a model which ignored the schema still gets claim-level
scrutiny rather than passing through unchecked.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from src.llm.prompts import get_prompt
from src.llm.provider import LLMError, LLMProvider
from src.models.schemas import CaseAnalysisOutput, ClaimType, GeneratedClaim

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9$])")
_MIN_CLAIM_CHARS = 25

# Sentences that describe the process rather than assert a case fact.
_NON_CLAIM_MARKERS = (
    "this summary is informational",
    "is not a determination",
    "requires human review",
    "all findings require human verification",
)


def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def is_assertable(sentence: str) -> bool:
    if len(sentence) < _MIN_CLAIM_CHARS:
        return False
    lowered = sentence.lower()
    return not any(marker in lowered for marker in _NON_CLAIM_MARKERS)


def claims_from_summary(summary: str) -> List[GeneratedClaim]:
    """Deterministic fallback extraction straight from the summary prose."""
    return [
        GeneratedClaim(claim_text=sentence, claim_type=ClaimType.FACT, confidence=0.5)
        for sentence in split_sentences(summary)
        if is_assertable(sentence)
    ]


def extract_claims(
    output: CaseAnalysisOutput, provider: Optional[LLMProvider] = None
) -> List[GeneratedClaim]:
    """Return the claim set to validate, with graceful degradation."""
    if output.claims:
        return list(output.claims)

    if provider is not None and not provider.is_demo:
        spec = get_prompt("claim_extraction")
        try:  # pragma: no cover - network path
            payload = provider.complete_json(
                get_prompt("system").template,
                spec.template.format(summary=output.executive_summary),
            )
            parsed = [GeneratedClaim.model_validate(c) for c in payload.get("claims", [])]
            if parsed:
                return parsed
        except (LLMError, ValueError) as exc:
            logger.warning("LLM claim extraction failed, using sentence split: %s", exc)

    return claims_from_summary(output.executive_summary)
