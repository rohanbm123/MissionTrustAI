"""Load synthetic case folders from disk into validated DTOs."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from src.config.settings import SYNTHETIC_CASES_DIR
from src.models.schemas import CaseMetadata

logger = logging.getLogger(__name__)


class CaseLoadError(RuntimeError):
    """Raised when a case folder is missing or malformed."""


@dataclass
class LoadedDocument:
    document_name: str
    document_type: str
    file_name: str
    raw_text: str


@dataclass
class LoadedCase:
    metadata: CaseMetadata
    documents: List[LoadedDocument]


def list_case_slugs(root: Optional[Path] = None) -> List[str]:
    root = root or SYNTHETIC_CASES_DIR
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "case_metadata.json").exists())


def load_case(slug: str, root: Optional[Path] = None) -> LoadedCase:
    root = root or SYNTHETIC_CASES_DIR
    case_dir = root / slug
    metadata_path = case_dir / "case_metadata.json"
    if not metadata_path.exists():
        raise CaseLoadError(f"No case_metadata.json found for case '{slug}' in {root}")

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata = CaseMetadata.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise CaseLoadError(f"Invalid case metadata for '{slug}': {exc}") from exc

    documents: List[LoadedDocument] = []
    for spec in metadata.documents:
        path = case_dir / spec.file
        if not path.exists():
            logger.warning("Case %s references a missing document file: %s", slug, spec.file)
            continue
        documents.append(
            LoadedDocument(
                document_name=spec.document_name,
                document_type=spec.document_type,
                file_name=spec.file,
                raw_text=path.read_text(encoding="utf-8"),
            )
        )

    if not documents:
        raise CaseLoadError(f"Case '{slug}' contains no readable documents")

    return LoadedCase(metadata=metadata, documents=documents)


def load_all_cases(root: Optional[Path] = None) -> List[LoadedCase]:
    cases: List[LoadedCase] = []
    for slug in list_case_slugs(root):
        try:
            cases.append(load_case(slug, root))
        except CaseLoadError as exc:
            logger.error("Skipping case %s: %s", slug, exc)
    return cases
