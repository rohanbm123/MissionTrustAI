"""Pluggable embedding providers.

`local`  - deterministic signed-hashing embedder over word, bigram and character
           n-grams. No network, no API key, reproducible across runs, which is
           what makes DEMO_MODE trustworthy for a live demo.
`openai` - OpenAI (or any OpenAI-compatible) embeddings endpoint.

Both return unit-norm vectors of `EMBEDDING_DIM` dimensions so the vector store
and every score downstream are provider-agnostic.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from abc import ABC, abstractmethod
from typing import List, Sequence

import numpy as np

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9\.\,/$%-]*")


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider cannot produce vectors."""


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


class EmbeddingProvider(ABC):
    name = "abstract"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        ...

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class LocalHashingEmbedder(EmbeddingProvider):
    """Signed feature hashing with sub-linear term weighting.

    Deterministic and dependency-free. Character 4-grams make it robust to the
    morphological variation typical of paraphrased claims ("delinquent" vs
    "delinquency") while word bigrams preserve short phrases.
    """

    name = "local-hashing-v1"

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_single(t) for t in texts]

    def _embed_single(self, text: str) -> List[float]:
        vector = np.zeros(self.dim, dtype=np.float64)
        tokens = tokenize(text)
        if not tokens:
            return vector.tolist()

        features: List[str] = []
        features.extend(f"w:{t}" for t in tokens)
        features.extend(f"b:{a}_{b}" for a, b in zip(tokens, tokens[1:]))
        compact = " ".join(tokens)
        features.extend(f"c:{compact[i:i + 4]}" for i in range(max(0, len(compact) - 3)))

        counts = {}
        for feature in features:
            counts[feature] = counts.get(feature, 0) + 1

        for feature, count in counts.items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            raw = int.from_bytes(digest, "big")
            bucket = raw % self.dim
            sign = 1.0 if (raw >> 63) & 1 else -1.0
            weight = 1.0 + math.log(count)
            if feature.startswith("c:"):
                weight *= 0.35  # character grams inform, they should not dominate
            vector[bucket] += sign * weight

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector.tolist()


class OpenAIEmbedder(EmbeddingProvider):
    """OpenAI-compatible embeddings, truncated/padded to EMBEDDING_DIM."""

    name = "openai"

    def __init__(self, dim: int, model: str, api_key: str, base_url: str = "") -> None:
        super().__init__(dim)
        self.model = model
        self.name = f"openai:{model}"
        try:
            from openai import OpenAI  # imported lazily; optional dependency
        except ImportError as exc:  # pragma: no cover - optional path
            raise EmbeddingError(
                "The `openai` package is required for EMBEDDING_PROVIDER=openai."
            ) from exc
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:  # pragma: no cover - network
        try:
            response = self._client.embeddings.create(
                model=self.model, input=list(texts), dimensions=self.dim
            )
        except Exception as exc:  # noqa: BLE001 - surface any provider failure uniformly
            raise EmbeddingError(f"Embedding request failed: {exc}") from exc
        return [list(item.embedding) for item in response.data]


def get_embedding_provider() -> EmbeddingProvider:
    """Resolve the configured provider, falling back to local on any problem."""
    settings = get_settings()
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        try:  # pragma: no cover - network path
            return OpenAIEmbedder(
                dim=settings.embedding_dim,
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        except EmbeddingError as exc:
            logger.warning("Falling back to the local embedder: %s", exc)
    return LocalHashingEmbedder(settings.embedding_dim)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
