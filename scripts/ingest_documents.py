"""Chunk + embed every synthetic case into the configured database."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.settings import get_settings  # noqa: E402
from src.database.db import init_db  # noqa: E402
from src.ingestion.embedding_service import get_embedding_provider  # noqa: E402
from src.services.case_service import ingest_all_cases  # noqa: E402


def main() -> None:
    settings = get_settings()
    init_db()
    embedder = get_embedding_provider()
    print(f"Database : {settings.database_flavor}")
    print(f"Embedder : {embedder.name} ({embedder.dim} dims)")
    results = ingest_all_cases()
    total_docs = sum(r.documents for r in results)
    total_chunks = sum(r.chunks for r in results)
    for result in results:
        print(f"  {result.case_number:16} {result.slug:22} {result.documents:2} docs  {result.chunks:3} chunks")
    print(f"Ingested {total_docs} documents / {total_chunks} chunks across {len(results)} cases.")


if __name__ == "__main__":
    main()
