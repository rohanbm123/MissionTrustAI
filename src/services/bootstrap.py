"""First-run bootstrap: make sure the app has a schema and a corpus to show."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from src.config.settings import SYNTHETIC_CASES_DIR, get_settings
from src.database.db import DatabaseUnavailable, healthcheck, init_db, session_scope
from src.database.repositories import CaseRepository
from src.services.case_service import ingest_all_cases

logger = logging.getLogger(__name__)


@dataclass
class BootstrapStatus:
    ready: bool
    cases: int
    message: str
    database: str


def ensure_ready(auto_seed: bool = True) -> BootstrapStatus:
    settings = get_settings()
    try:
        init_db()
    except DatabaseUnavailable as exc:
        return BootstrapStatus(False, 0, str(exc), settings.database_flavor)

    if not healthcheck():
        return BootstrapStatus(
            False, 0, "The database did not respond to a health check.", settings.database_flavor
        )

    with session_scope() as session:
        count = CaseRepository.count(session)

    if count == 0 and auto_seed:
        if not SYNTHETIC_CASES_DIR.exists() or not any(SYNTHETIC_CASES_DIR.iterdir()):
            _generate_corpus()
        try:
            results = ingest_all_cases()
            count = len(results)
        except Exception as exc:  # noqa: BLE001 - report, never crash the UI
            logger.exception("Automatic ingestion failed")
            return BootstrapStatus(
                False, 0, f"Automatic ingestion failed: {exc}", settings.database_flavor
            )

    if count == 0:
        return BootstrapStatus(
            False,
            0,
            "No cases are loaded. Run `python scripts/seed_database.py`.",
            settings.database_flavor,
        )

    return BootstrapStatus(True, count, "Ready", settings.database_flavor)


def _generate_corpus() -> None:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from generate_synthetic_cases import generate  # noqa: PLC0415

    generate()
