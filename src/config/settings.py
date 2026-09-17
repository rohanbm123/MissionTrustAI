"""Central configuration for CaseBrief.

Values are read from environment variables, optionally seeded from a local
`.env` file. No credential is ever hard-coded or written to logs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SYNTHETIC_CASES_DIR = DATA_DIR / "synthetic_cases"
DEMO_ANALYSES_DIR = DATA_DIR / "demo_analyses"

_TRUE = {"1", "true", "yes", "on", "y"}


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency on python-dotenv being installed).

    Existing environment variables always win, so `DEMO_MODE=false streamlit ...`
    overrides the file.
    """
    if not path.exists():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:  # pragma: no cover - unreadable .env should never crash boot
        pass


_load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    return default if value is None or value == "" else value


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in _TRUE


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _default_sqlite_url() -> str:
    home = Path(os.path.expanduser("~")) / ".missiontrust"
    home.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{home / 'missiontrust.db'}"


@dataclass(frozen=True)
class Settings:
    # -- runtime -----------------------------------------------------------
    demo_mode: bool = field(default_factory=lambda: _env_bool("DEMO_MODE", True))
    app_name: str = "CaseBrief"
    app_tagline: str = "Evidence-Backed AI Case Briefs for Human Adjudicators"
    app_subtagline: str = "From completed investigation to decision-ready evidence."

    # -- database ----------------------------------------------------------
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "") or _default_sqlite_url()
    )

    # -- llm ---------------------------------------------------------------
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "demo").lower())
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-5"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL"))
    # Groq speaks the OpenAI chat-completions API, so it needs a key and a model,
    # not a new client. Kept as its own provider name purely for ergonomics.
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _env("GROQ_MODEL", "llama-3.3-70b-versatile"))
    groq_base_url: str = field(
        default_factory=lambda: _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    )
    llm_temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.0))
    llm_max_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 4000))

    # -- embeddings --------------------------------------------------------
    embedding_provider: str = field(
        default_factory=lambda: _env("EMBEDDING_PROVIDER", "local").lower()
    )
    embedding_model: str = field(
        default_factory=lambda: _env("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    embedding_dim: int = field(default_factory=lambda: _env_int("EMBEDDING_DIM", 512))

    # -- retrieval ---------------------------------------------------------
    chunk_size: int = field(default_factory=lambda: _env_int("CHUNK_SIZE", 700))
    chunk_overlap: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP", 120))
    retrieval_top_k: int = field(default_factory=lambda: _env_int("RETRIEVAL_TOP_K", 16))
    evidence_top_k: int = field(default_factory=lambda: _env_int("EVIDENCE_TOP_K", 4))

    # -- assurance ---------------------------------------------------------
    weight_semantic: float = field(default_factory=lambda: _env_float("WEIGHT_SEMANTIC", 0.40))
    weight_retrieval: float = field(default_factory=lambda: _env_float("WEIGHT_RETRIEVAL", 0.20))
    weight_entailment: float = field(default_factory=lambda: _env_float("WEIGHT_ENTAILMENT", 0.40))
    threshold_supported: float = field(
        default_factory=lambda: _env_float("THRESHOLD_SUPPORTED", 0.75)
    )
    threshold_weak: float = field(default_factory=lambda: _env_float("THRESHOLD_WEAK", 0.55))
    # Raw cosine similarity is compressed; these calibrate it onto [0, 1] before
    # it is combined with the other assurance signals. See README methodology.
    semantic_floor: float = field(default_factory=lambda: _env_float("SEMANTIC_FLOOR", 0.08))
    semantic_ceiling: float = field(default_factory=lambda: _env_float("SEMANTIC_CEILING", 0.45))

    # -- reviewer ----------------------------------------------------------
    reviewer_name: str = field(default_factory=lambda: _env("REVIEWER_NAME", "Demo Reviewer"))
    reviewer_role: str = field(
        default_factory=lambda: _env("REVIEWER_ROLE", "Adjudication Analyst")
    )

    # -- derived -----------------------------------------------------------
    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgres")

    @property
    def live_llm_available(self) -> bool:
        """True when a real provider is configured with a credential."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider in {"openai", "openai-compatible"}:
            return bool(self.openai_api_key)
        if self.llm_provider == "groq":
            return bool(self.groq_api_key)
        return False

    @property
    def effective_demo_mode(self) -> bool:
        """Demo mode is forced on whenever no usable live provider exists."""
        return self.demo_mode or not self.live_llm_available

    @property
    def database_flavor(self) -> str:
        return "PostgreSQL + pgvector" if self.is_postgres else "SQLite + NumPy cosine index"

    def redacted(self) -> dict:
        """Configuration snapshot safe to render in the UI or write to logs."""

        def mask(value: Optional[str]) -> str:
            return "configured" if value else "not set"

        return {
            "demo_mode": self.effective_demo_mode,
            "llm_provider": self.llm_provider,
            "llm_model": self.active_model_name,
            "anthropic_api_key": mask(self.anthropic_api_key),
            "openai_api_key": mask(self.openai_api_key),
            "groq_api_key": mask(self.groq_api_key),
            "embedding_provider": self.embedding_provider,
            "embedding_dim": self.embedding_dim,
            "database": self.database_flavor,
            "retrieval_top_k": self.retrieval_top_k,
        }

    @property
    def configured_model_name(self) -> str:
        """The live model that *would* be used, regardless of DEMO_MODE.

        `active_model_name` reports what is actually running; this reports what
        the live option would switch to, so the UI can label the choice.
        """
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        if self.llm_provider in {"openai", "openai-compatible"}:
            return self.openai_model
        if self.llm_provider == "groq":
            return self.groq_model
        return "demo-fixture-v1"

    @property
    def active_model_name(self) -> str:
        if self.effective_demo_mode:
            return "demo-fixture-v1"
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        if self.llm_provider in {"openai", "openai-compatible"}:
            return self.openai_model
        if self.llm_provider == "groq":
            return self.groq_model
        return "demo-fixture-v1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Force re-read of the environment (used by tests)."""
    get_settings.cache_clear()
    return get_settings()
