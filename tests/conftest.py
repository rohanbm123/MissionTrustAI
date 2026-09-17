"""Test configuration.

The environment is pinned *before* any application module is imported so that
tests always run against a throwaway SQLite database, the deterministic local
embedder and demo-mode generation — never a developer's real configuration and
never a live API.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_TEST_DB = Path(tempfile.gettempdir()) / "missiontrust_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["DEMO_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""

import pytest  # noqa: E402

from src.config.settings import reload_settings  # noqa: E402
from src.database.db import init_db, reset_engine  # noqa: E402
from src.ingestion.document_loader import load_case  # noqa: E402
from src.retrieval.vector_store import reset_vector_store  # noqa: E402
from src.services.case_service import ingest_case  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    reload_settings()
    reset_engine()
    reset_vector_store()
    init_db(drop=True)
    yield
    reset_engine()
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest.fixture(scope="session")
def alex_case(_database):
    """The flagship case, ingested once for the whole session."""
    from src.database.db import session_scope
    from src.database.repositories import CaseRepository

    ingest_case(load_case("alex_morgan"))
    with session_scope() as session:
        case = CaseRepository.get_by_slug(session, "alex_morgan")
        return {"case_id": case.id, "case_number": case.case_number, "slug": case.slug,
                "applicant_name": case.applicant_name}


@pytest.fixture(scope="session")
def elena_case(_database):
    """A case with a planted, documented contradiction."""
    from src.database.db import session_scope
    from src.database.repositories import CaseRepository

    ingest_case(load_case("elena_vasquez"))
    with session_scope() as session:
        case = CaseRepository.get_by_slug(session, "elena_vasquez")
        return {"case_id": case.id, "case_number": case.case_number, "slug": case.slug,
                "applicant_name": case.applicant_name}


@pytest.fixture(scope="session")
def all_cases(_database):
    """Every synthetic case ingested once, keyed by slug."""
    from src.database.db import session_scope
    from src.database.repositories import CaseRepository
    from src.ingestion.document_loader import list_case_slugs

    for slug in list_case_slugs():
        ingest_case(load_case(slug))
    with session_scope() as session:
        return {c.slug: c.id for c in CaseRepository.list_all(session)}


@pytest.fixture(scope="session")
def golden_expectations():
    import json

    path = PROJECT_ROOT / "evals" / "expected_recommendations.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def analysis_bundle(alex_case):
    from src.services.analysis_service import run_analysis

    return run_analysis(alex_case["case_id"])
