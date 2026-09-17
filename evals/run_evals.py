"""Run the CaseBrief recommendation evaluation suite.

Two suites:

* **Golden cases** — every synthetic case is analysed and the shipped
  recommendation is compared with the expected one in
  `expected_recommendations.json`.
* **Evidence mutations** — controlled variants add or remove documents from a
  completed package. Material mutations must move the recommendation; immaterial
  ones must not. This is the test that distinguishes a system reacting to
  evidence from one producing generic answers.

Mutation variants are ingested as separate cases under
`<base_slug>__<mutation_id>` in a scratch corpus directory, so the demonstration
caseload is never modified. In DEMO_MODE the variant reuses the base case's
generated narrative on purpose: holding the prose fixed isolates the question of
whether the *recommendation* reacts to the evidence.

Usage:
    python evals/run_evals.py                 # both suites
    python evals/run_evals.py --golden-only
    python evals/run_evals.py --label baseline-v1
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

EVALS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVALS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EVALS_DIR))

import metrics as eval_metrics  # noqa: E402

from src.config.settings import SYNTHETIC_CASES_DIR, get_settings  # noqa: E402
from src.database.db import init_db, session_scope  # noqa: E402
from src.database.repositories import AdjudicatorActionRepository, CaseRepository  # noqa: E402
from src.ingestion.document_loader import load_case  # noqa: E402
from src.models.schemas import CaseMetadata  # noqa: E402
from src.services.analysis_service import AnalysisError, run_analysis  # noqa: E402
from src.services.case_service import ingest_case  # noqa: E402

RESULTS_DIR = EVALS_DIR / "results"


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------
def _brief_record(bundle, documents: Dict[str, str]) -> Dict[str, Any]:
    """Flatten a generated brief into the shape the metrics expect."""
    assessment = bundle.assessment
    reasons = []
    citations = []
    evidence_files = set()
    evidence_texts: List[str] = []

    carriers = (
        list(assessment.why_this_recommendation)
        + list(assessment.mitigating_factors)
        + list(assessment.remaining_concerns)
    )
    for item in carriers:
        for link in item.evidence:
            citations.append(
                {
                    "source_id": link.source_id,
                    "resolved": bool(link.chunk_id),
                    "relevance": link.relevance_score,
                    "document_name": link.document_name,
                }
            )
            evidence_texts.append(link.evidence_text)
            file_name = documents.get(link.document_name)
            if file_name:
                evidence_files.add(file_name)

    for reason in assessment.why_this_recommendation:
        reasons.append(
            {
                "reason": reason.reason,
                "category": reason.category.value,
                "importance": reason.importance.value,
                "evidence_status": reason.evidence_status.value,
                "source_ids": list(reason.source_ids),
                "verification_score": reason.verification_score,
            }
        )

    return {
        "actual_recommendation": assessment.overall_recommendation.value,
        "concern_level": assessment.overall_concern_level.value,
        "confidence": assessment.recommendation_confidence,
        "material_unresolved_issues": assessment.material_unresolved_issues,
        "model_proposed_recommendation": (
            assessment.model_proposed_recommendation.value
            if assessment.model_proposed_recommendation
            else None
        ),
        "reasons": reasons,
        "citations": citations,
        "evidence_files": sorted(evidence_files),
        "evidence_texts": evidence_texts,
        "engine_rationale": assessment.engine_rationale,
        "claims": len(bundle.claims),
        "contradiction_flags": len(bundle.contradictions),
    }


def _document_file_map(slug: str, root: Optional[Path] = None) -> Dict[str, str]:
    """document_name -> file name, so evidence links resolve back to files."""
    case = load_case(slug, root)
    return {d.document_name: d.file_name for d in case.documents}


# ---------------------------------------------------------------------------
# Golden suite
# ---------------------------------------------------------------------------
def run_golden(verbose: bool = True) -> List[Dict[str, Any]]:
    expected = json.loads((EVALS_DIR / "expected_recommendations.json").read_text())
    golden = json.loads((EVALS_DIR / "golden_cases.json").read_text())["cases"]

    records: List[Dict[str, Any]] = []
    with session_scope() as session:
        by_number = {c.case_number: c.id for c in CaseRepository.list_all(session)}

    for case in golden:
        case_id = by_number.get(case["case_id"])
        if case_id is None:
            if verbose:
                print(f"  ! {case['case_id']} is not ingested; run scripts/seed_database.py")
            continue
        truth = expected[case["case_id"]]
        try:
            bundle = run_analysis(case_id)
        except AnalysisError as exc:
            if verbose:
                print(f"  ! {case['case_id']} failed: {exc}")
            continue

        record = {
            "slug": case["slug"],
            "case_id": case["case_id"],
            "applicant_name": case["applicant_name"],
            "expected_recommendation": truth["expected_recommendation"],
            "expected_concern_level": truth.get("expected_concern_level"),
            "critical_evidence": truth.get("critical_evidence", []),
            "critical_evidence_terms": truth.get("critical_evidence_terms", []),
            "expected_reason_topics": truth.get("expected_reason_topics", []),
        }
        record.update(_brief_record(bundle, _document_file_map(case["slug"])))
        records.append(record)
        if verbose:
            mark = "ok " if record["actual_recommendation"] == record["expected_recommendation"] else "XX "
            print(
                f"  {mark}{case['case_id']} {case['applicant_name']:22}"
                f"{record['actual_recommendation']:32} (expected {record['expected_recommendation']})"
            )
    return records


# ---------------------------------------------------------------------------
# Mutation suite
# ---------------------------------------------------------------------------
def build_variant(mutation: Dict[str, Any], scratch: Path) -> str:
    """Materialise one mutated package in a scratch corpus and return its slug."""
    base_slug = mutation["base_slug"]
    variant_slug = f"{base_slug}__{mutation['id']}"
    source = SYNTHETIC_CASES_DIR / base_slug
    target = scratch / variant_slug
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    metadata = json.loads((target / "case_metadata.json").read_text())

    # History events are evidence too, so a mutation that removes a fact has to
    # be able to remove the timeline entry attesting it — otherwise "remove the
    # evidence" silently leaves half of it in place.
    event_removals = {label.lower() for label in mutation.get("remove_events", [])}
    if event_removals:
        metadata["timeline"] = [
            event
            for event in metadata["timeline"]
            if event["label"].lower() not in event_removals
        ]

    removals = set(mutation.get("remove", []))
    metadata["documents"] = [d for d in metadata["documents"] if d["file"] not in removals]
    for file_name in removals:
        (target / file_name).unlink(missing_ok=True)

    for addition in mutation.get("add", []):
        (target / addition["file"]).write_text(addition["text"], encoding="utf-8")
        metadata["documents"].append(
            {
                "file": addition["file"],
                "document_name": addition["document_name"],
                "document_type": addition["document_type"],
            }
        )

    metadata["slug"] = variant_slug
    metadata["case_number"] = f"{metadata['case_number']}-{mutation['id'][:14].upper()}"
    metadata["applicant_name"] = f"{metadata['applicant_name']} (eval variant)"
    CaseMetadata.model_validate(metadata)
    (target / "case_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return variant_slug


def run_mutations(
    base_records: List[Dict[str, Any]], verbose: bool = True
) -> List[Dict[str, Any]]:
    payload = json.loads((EVALS_DIR / "evidence_mutation_cases.json").read_text())
    base_by_slug = {r["slug"]: r for r in base_records}
    records: List[Dict[str, Any]] = []

    scratch = Path(tempfile.mkdtemp(prefix="casebrief_evals_"))
    try:
        for mutation in payload["mutations"]:
            base = base_by_slug.get(mutation["base_slug"])
            if base is None:
                if verbose:
                    print(f"  ! no base record for {mutation['base_slug']}; skipping")
                continue

            variant_slug = build_variant(mutation, scratch)
            loaded = load_case(variant_slug, scratch)
            ingest_case(loaded)
            with session_scope() as session:
                case = CaseRepository.get_by_slug(session, variant_slug)
                variant_case_id = case.id

            try:
                bundle = run_analysis(variant_case_id)
            except AnalysisError as exc:
                if verbose:
                    print(f"  ! {mutation['id']} failed: {exc}")
                continue

            record = {
                "id": mutation["id"],
                "base_slug": mutation["base_slug"],
                "label": mutation["label"],
                "kind": mutation["kind"],
                "hypothesis": mutation.get("hypothesis", ""),
                "removed": mutation.get("remove", []),
                "added": [a["file"] for a in mutation.get("add", [])],
                "base_recommendation": base["actual_recommendation"],
                "expected_recommendation": mutation["expected_recommendation"],
            }
            record.update(_brief_record(bundle, _document_file_map(variant_slug, scratch)))
            records.append(record)
            if verbose:
                mark = "ok " if record["actual_recommendation"] == record["expected_recommendation"] else "XX "
                print(
                    f"  {mark}{mutation['id']:44}{record['base_recommendation'][:8]:9}"
                    f"-> {record['actual_recommendation']:32}"
                    f"(expected {record['expected_recommendation']})"
                )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        _purge_variants()
    return records


def _purge_variants() -> None:
    """Remove eval variant cases so they never appear in the demonstration caseload."""
    with session_scope() as session:
        for case in CaseRepository.list_all(session):
            if "__" in case.slug:
                session.delete(case)


def collect_adjudicator_actions() -> List[Dict[str, Any]]:
    with session_scope() as session:
        return [
            {"analysis_id": row.analysis_id, "agreed_with_ai": row.agreed_with_ai}
            for row in AdjudicatorActionRepository.list_all(session)
        ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CaseBrief eval suite.")
    parser.add_argument("--golden-only", action="store_true", help="skip evidence mutations")
    parser.add_argument("--label", default="", help="label recorded on the results file")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    verbose = not args.quiet

    settings = get_settings()
    init_db()

    if verbose:
        print("CaseBrief evaluation suite")
        print(f"  mode      : {'DEMO_MODE' if settings.effective_demo_mode else 'live LLM'}")
        print(f"  model     : {settings.active_model_name}")
        print(f"  database  : {settings.database_flavor}\n")
        print("Golden cases")

    golden = run_golden(verbose)

    mutations: List[Dict[str, Any]] = []
    if not args.golden_only:
        if verbose:
            print("\nEvidence mutations")
        mutations = run_mutations(golden, verbose)

    summary = eval_metrics.summarise(golden, mutations, collect_adjudicator_actions())

    if verbose:
        print("\nMetrics")
        for key, value in summary.items():
            if isinstance(value, float):
                print(f"  {key:38} {value * 100:6.1f}%")
            else:
                print(f"  {key:38} {value:>6}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS_DIR / f"run_{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "run_id": stamp,
                "label": args.label,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "demo_mode": settings.effective_demo_mode,
                "model": settings.active_model_name,
                "prompt_version": "FINAL_CASE_ASSESSMENT_V1",
                "summary": summary,
                "golden": golden,
                "mutations": mutations,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    if verbose:
        print(f"\nResults written to {path}")

    failures = sum(
        1 for r in golden if r["actual_recommendation"] != r["expected_recommendation"]
    ) + sum(
        1 for r in mutations if r["actual_recommendation"] != r["expected_recommendation"]
    )
    if verbose:
        print(f"{'PASS' if failures == 0 else 'FAIL'}: {failures} case(s) off expectation")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
