"""Materialise the synthetic case corpus onto disk.

Writes, for every case:
  data/synthetic_cases/<slug>/case_metadata.json
  data/synthetic_cases/<slug>/<document>.txt
  data/demo_analyses/<slug>.json      (curated DEMO_MODE generation fixture)

Idempotent: re-running overwrites the generated files in place.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from case_corpus import ACTIVE_SLUGS, CASES, active_cases  # noqa: E402
from src.config.settings import DEMO_ANALYSES_DIR, PROJECT_ROOT, SYNTHETIC_CASES_DIR  # noqa: E402
from src.models.schemas import CaseAnalysisOutput, CaseMetadata  # noqa: E402

EVALS_DIR = PROJECT_ROOT / "evals"


def generate(include_all: bool = False) -> int:
    SYNTHETIC_CASES_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

    selected = active_cases(include_all)
    _prune_inactive({case["slug"] for case in selected})

    written = 0
    for case in selected:
        case_dir = SYNTHETIC_CASES_DIR / case["slug"]
        case_dir.mkdir(parents=True, exist_ok=True)

        for document in case["documents"]:
            (case_dir / document["file"]).write_text(document["text"], encoding="utf-8")
            written += 1

        metadata = {
            "case_number": case["case_number"],
            "applicant_name": case["applicant_name"],
            "slug": case["slug"],
            "status": case.get("status", "Awaiting AI Analysis"),
            "key_signal": case["key_signal"],
            "scenario": case["scenario"],
            "opened_on": case["opened_on"],
            "documents": [
                {
                    "file": d["file"],
                    "document_name": d["document_name"],
                    "document_type": d["document_type"],
                }
                for d in case["documents"]
            ],
            "timeline": case["timeline"],
            "known_contradictions": case.get("known_contradictions", []),
        }
        # Validate before writing so bad corpus edits fail loudly here, not in the app.
        CaseMetadata.model_validate(metadata)
        (case_dir / "case_metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        analysis = case["demo_analysis"]
        CaseAnalysisOutput.model_validate(analysis)
        (DEMO_ANALYSES_DIR / f"{case['slug']}.json").write_text(
            json.dumps(analysis, indent=2), encoding="utf-8"
        )

    _write_eval_ground_truth(selected)
    return written


def _prune_inactive(keep: set) -> None:
    """Remove generated folders for cases no longer in the active set.

    The corpus definition is the source of truth; anything on disk that it no
    longer produces would otherwise still be ingested by the directory scan.
    """
    for path in SYNTHETIC_CASES_DIR.iterdir():
        if path.is_dir() and path.name not in keep:
            shutil.rmtree(path, ignore_errors=True)
    for path in DEMO_ANALYSES_DIR.glob("*.json"):
        if path.stem not in keep:
            path.unlink(missing_ok=True)


def _write_eval_ground_truth(selected) -> None:
    """Ground truth lives in evals/ only — never in the case package itself.

    The inference pipeline reads `data/synthetic_cases/`; it has no path to this
    file, so an expected answer can never leak into a generated recommendation.
    """
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    expected = {}
    golden = []
    for case in selected:
        truth = case.get("ground_truth") or {}
        if not truth:
            continue
        expected[case["case_number"]] = truth
        golden.append(
            {
                "slug": case["slug"],
                "case_id": case["case_number"],
                "applicant_name": case["applicant_name"],
                "scenario": case["scenario"],
                "expected_recommendation": truth["expected_recommendation"],
                "expected_concern_level": truth.get("expected_concern_level"),
                "rationale": truth.get("rationale", ""),
                "critical_evidence": truth.get("critical_evidence", []),
                "critical_evidence_terms": truth.get("critical_evidence_terms", []),
                "expected_reason_topics": truth.get("expected_reason_topics", []),
            }
        )
    (EVALS_DIR / "expected_recommendations.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )
    (EVALS_DIR / "golden_cases.json").write_text(
        json.dumps({"cases": golden}, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the synthetic case corpus.")
    parser.add_argument(
        "--all", action="store_true", help="generate all defined cases, not just the active set"
    )
    args = parser.parse_args()
    count = generate(args.all)
    generated = len(CASES) if args.all else len(ACTIVE_SLUGS)
    print(f"Generated {count} documents across {generated} synthetic cases.")
    print(f"  case files    -> {SYNTHETIC_CASES_DIR}")
    print(f"  demo analyses -> {DEMO_ANALYSES_DIR}")
