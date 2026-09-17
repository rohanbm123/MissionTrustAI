"""LLM provider abstraction.

Three interchangeable providers behind one interface:

* `DemoProvider`      - deterministic curated fixtures; no key, no network.
* `AnthropicProvider` - Claude via the Anthropic Messages API.
* `OpenAIProvider`    - any OpenAI-compatible chat-completions endpoint.

Credentials come only from environment variables and are never logged. Every
provider returns parsed, schema-checked JSON: `complete_json` retries once with
a repair instruction before giving up, and a failure raises `LLMError` rather
than propagating a partially-parsed object into the assurance pipeline.
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.config.settings import DEMO_ANALYSES_DIR, get_settings

logger = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    """Raised when a provider cannot return usable structured output."""


def extract_json(raw: str) -> Dict[str, Any]:
    """Best-effort recovery of a JSON object from a model response."""
    if not raw or not raw.strip():
        raise LLMError("Model returned an empty response.")
    cleaned = _FENCE.sub("", raw.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model response was not valid JSON: {exc}") from exc
    raise LLMError("Model response contained no JSON object.")


class LLMProvider(ABC):
    name = "abstract"
    model = "abstract"
    is_demo = False

    @abstractmethod
    def complete(
        self, system: str, user: str, *, context: Optional[Dict[str, Any]] = None
    ) -> str:
        ...

    def complete_json(
        self, system: str, user: str, *, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return parsed JSON, retrying once with an explicit repair instruction."""
        try:
            return extract_json(self.complete(system, user, context=context))
        except LLMError as first_error:
            logger.warning("Malformed JSON from %s, retrying once: %s", self.name, first_error)
            repair = (
                f"{user}\n\nYour previous response could not be parsed as JSON "
                f"({first_error}). Return ONLY a single valid JSON object. "
                "No markdown fences, no commentary."
            )
            try:
                return extract_json(self.complete(system, repair, context=context))
            except LLMError as second_error:
                raise LLMError(
                    f"{self.name} did not return valid JSON after one retry: {second_error}"
                ) from second_error


class DemoProvider(LLMProvider):
    """Serves curated per-case fixtures so the demo never depends on a network.

    Only the *generation* step is fixed. Retrieval, claim validation,
    contradiction detection and metrics still run for real over the ingested
    documents, so what the assurance panel reports is genuinely computed.
    """

    name = "demo"
    model = "demo-fixture-v1"
    is_demo = True

    def __init__(self, fixture_dir=None) -> None:
        self.fixture_dir = fixture_dir or DEMO_ANALYSES_DIR

    def complete(
        self, system: str, user: str, *, context: Optional[Dict[str, Any]] = None
    ) -> str:
        return json.dumps(self.fixture(context))

    def fixture(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        slug = (context or {}).get("case_slug")
        if not slug:
            raise LLMError("Demo mode requires a case_slug in the request context.")
        path = self.fixture_dir / f"{slug}.json"
        if not path.exists() and "__" in slug:
            # Evidence-mutation variants (`alex_morgan__m1_remove_payment_plan`)
            # reuse the base case's narrative on purpose: the eval asks whether
            # the *recommendation* moves when documents change, holding the
            # generated prose fixed.
            path = self.fixture_dir / f"{slug.split('__', 1)[0]}.json"
        if not path.exists():
            raise LLMError(
                f"No demo fixture for case '{slug}'. Run scripts/generate_synthetic_cases.py."
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LLMError(f"Demo fixture for '{slug}' is unreadable: {exc}") from exc


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMError("The `anthropic` package is required for LLM_PROVIDER=anthropic.") from exc
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(
        self, system: str, user: str, *, context: Optional[Dict[str, Any]] = None
    ) -> str:  # pragma: no cover - network
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001 - normalise every provider failure
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )


class OpenAIProvider(LLMProvider):
    """Any OpenAI-compatible chat-completions endpoint: OpenAI, Groq, vLLM, LiteLLM."""

    name = "openai"

    def __init__(
        self, api_key: str, model: str, temperature: float, max_tokens: int, base_url: str = ""
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMError("The `openai` package is required for LLM_PROVIDER=openai.") from exc
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not set.")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        if "groq.com" in base_url:
            self.name = "groq"

    def complete(
        self, system: str, user: str, *, context: Optional[Dict[str, Any]] = None
    ) -> str:  # pragma: no cover - network
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"OpenAI request failed: {exc}") from exc
        return response.choices[0].message.content or ""


def get_llm_provider(force_provider: Optional[str] = None) -> LLMProvider:
    """Resolve the configured provider, degrading to demo rather than failing."""
    settings = get_settings()
    provider = (force_provider or settings.llm_provider).lower()

    if force_provider is None and settings.effective_demo_mode:
        return DemoProvider()

    try:
        if provider == "anthropic":
            return AnthropicProvider(
                settings.anthropic_api_key,
                settings.anthropic_model,
                settings.llm_temperature,
                settings.llm_max_tokens,
            )
        if provider in {"openai", "openai-compatible"}:
            return OpenAIProvider(
                settings.openai_api_key,
                settings.openai_model,
                settings.llm_temperature,
                settings.llm_max_tokens,
                settings.openai_base_url,
            )
        if provider == "groq":
            # Groq is OpenAI-compatible: same client, different base URL.
            return OpenAIProvider(
                settings.groq_api_key,
                settings.groq_model,
                settings.llm_temperature,
                settings.llm_max_tokens,
                settings.groq_base_url,
            )
    except LLMError as exc:
        logger.warning("Falling back to demo mode: %s", exc)
    return DemoProvider()


class Timer:
    """Millisecond latency measurement for provider comparison."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.elapsed_ms = 0
        return self

    def __exit__(self, *exc: Any) -> None:
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)
