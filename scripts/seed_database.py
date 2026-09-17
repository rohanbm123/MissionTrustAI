"""Create the schema, generate the synthetic corpus, and ingest everything.

Usage:
    python scripts/seed_database.py            # create + ingest
    python scripts/seed_database.py --reset    # drop all tables first
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_synthetic_cases import generate  # noqa: E402
from src.config.settings import get_settings  # noqa: E402
from src.database.db import init_db  # noqa: E402
from src.services.analysis_service import AnalysisError, run_analysis  # noqa: E402
from src.services.case_service import ingest_all_cases, list_cases  # noqa: E402
from src.services.review_service import record_adjudicator_action, record_review  # noqa: E402

# A spread of synthetic adjudicator decisions so the dashboards carry human
# oversight statistics on first open. Includes one deliberate departure from the
# AI recommendation so the agreement metric is not trivially 100%.
# Entries naming a case that is not in the active caseload are skipped, so this
# list can safely cover the reserve cases too.
SAMPLE_ACTIONS = [
    ("PS-2026-00256", "proceed", "No adverse information in any category."),
    ("PS-2026-00182", "proceed", "Servicer confirmed the plan is still current."),
    ("PS-2026-00194", "request_more_information", "Chasing the January 2021 payroll record."),
    ("PS-2026-00217", "escalate", "Two collection accounts with nothing mitigating them."),
    # A deliberate departure from the AI, so human agreement is never trivially 100%.
    ("PS-2026-00225", "request_more_information", "Departing from the brief: asking for the separation letter before escalating."),
    ("PS-2026-00240", "proceed", "Court record confirms the matter is closed."),
    ("PS-2026-00231", "escalate", "Delinquency and judgment both unmitigated."),
]

# A spread of synthetic reviewer decisions so the assurance dashboard has human
# oversight statistics on first open. Opt-in via --with-sample-reviews.
SAMPLE_REVIEWS = [
    ("PS-2026-00256", "accepted", "", "No adverse information; summary is accurate."),
    ("PS-2026-00182", "edited_accepted", "APPEND", "Flagged the unsupported insurer sentence."),
    ("PS-2026-00194", "more_evidence_requested", "", "January 2021 payroll record still outstanding."),
    ("PS-2026-00225", "accepted", "", "Conflict is stated fairly; both records are quoted."),
    ("PS-2026-00217", "rejected", "", "Draft understates that neither account has an arrangement."),
    ("PS-2026-00240", "accepted", "", "Draft matches the court record; no changes needed."),
    ("PS-2026-00231", "rejected", "", "Summary asserts a counselling enrollment the file does not contain."),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the CaseBrief database.")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    parser.add_argument(
        "--skip-generate", action="store_true", help="do not regenerate the synthetic files"
    )
    parser.add_argument(
        "--all-cases", action="store_true", help="load every defined case, not just the active set"
    )
    parser.add_argument(
        "--analyse", action="store_true", help="run an AI analysis for every case after ingestion"
    )
    parser.add_argument(
        "--with-sample-reviews",
        action="store_true",
        help="record a spread of synthetic reviewer decisions (implies --analyse)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="full demo state: --reset --analyse --with-sample-reviews",
    )
    args = parser.parse_args()
    if args.demo:
        args.reset = args.analyse = args.with_sample_reviews = True
    if args.with_sample_reviews:
        args.analyse = True

    settings = get_settings()
    print(f"CaseBrief seed — {settings.database_flavor}")

    if not args.skip_generate:
        written = generate(getattr(args, "all_cases", False))
        print(f"  synthetic corpus: {written} documents written")

    init_db(drop=args.reset)
    print(f"  schema: {'recreated' if args.reset else 'ensured'}")

    results = ingest_all_cases()
    print(
        f"  ingested: {len(results)} cases, "
        f"{sum(r.documents for r in results)} documents, "
        f"{sum(r.chunks for r in results)} chunks"
    )
    if args.analyse:
        analysed = 0
        for case in list_cases():
            try:
                run_analysis(case["case_id"])
                analysed += 1
            except AnalysisError as exc:
                print(f"  ! analysis failed for {case['case_number']}: {exc}")
        print(f"  analysed: {analysed} cases")

    if args.with_sample_reviews:
        by_number = {c["case_number"]: c for c in list_cases()}
        recorded = 0
        for case_number, decision, edit_marker, notes in SAMPLE_REVIEWS:
            case = by_number.get(case_number)
            if not case or not case["analysis_id"]:
                continue
            edited = ""
            if edit_marker == "APPEND":
                from src.services.analysis_service import load_latest_analysis

                bundle = load_latest_analysis(case["case_id"])
                edited = (
                    bundle.output.executive_summary
                    + " Reviewer addition: the amended disclosure was filed before any further "
                    "record check was completed."
                )
            record_review(
                case_id=case["case_id"],
                analysis_id=case["analysis_id"],
                decision=decision,
                reviewer_name="Demo Reviewer",
                edited_text=edited,
                review_notes=notes,
            )
            recorded += 1
        print(f"  sample reviews: {recorded} recorded (synthetic)")

        decided = 0
        for case_number, action, notes in SAMPLE_ACTIONS:
            case = by_number.get(case_number)
            if not case or not case["analysis_id"]:
                continue
            record_adjudicator_action(
                case_id=case["case_id"],
                analysis_id=case["analysis_id"],
                action=action,
                adjudicator_name="Demo Adjudicator",
                notes=notes,
            )
            decided += 1
        print(f"  adjudicator decisions: {decided} recorded (synthetic)")

    print("Seed complete.")


if __name__ == "__main__":
    main()
