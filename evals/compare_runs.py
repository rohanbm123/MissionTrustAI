"""Compare two evaluation runs.

Prompt and rule changes are supposed to be judged, not guessed at. This prints a
metric-by-metric delta between two result files and lists every case whose
recommendation moved between them.

Usage:
    python evals/compare_runs.py                       # two most recent runs
    python evals/compare_runs.py baseline.json new.json
    python evals/compare_runs.py --list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "results"
sys.path.insert(0, str(EVALS_DIR))

from metrics import METRIC_DIRECTION  # noqa: E402


def available_runs() -> List[Path]:
    if not RESULTS_DIR.exists():
        return []
    return sorted(RESULTS_DIR.glob("run_*.json"))


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verdict(metric: str, delta: float) -> str:
    if abs(delta) < 1e-9:
        return "="
    direction = METRIC_DIRECTION.get(metric, "higher")
    improved = delta > 0 if direction == "higher" else delta < 0
    return "improved" if improved else "regressed"


def compare_summaries(before: Dict[str, Any], after: Dict[str, Any]) -> List[Tuple[str, Any, Any, str]]:
    rows = []
    for metric in sorted(set(before) | set(after)):
        old, new = before.get(metric), after.get(metric)
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            rows.append((metric, old, new, _verdict(metric, float(new) - float(old))))
    return rows


def compare_cases(before: Dict[str, Any], after: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """Cases whose recommendation moved between the two runs."""
    id_field = "case_id" if key == "golden" else "id"
    old = {r[id_field]: r for r in before.get(key, [])}
    new = {r[id_field]: r for r in after.get(key, [])}
    moved = []
    for identifier, record in new.items():
        previous = old.get(identifier)
        if previous and previous["actual_recommendation"] != record["actual_recommendation"]:
            moved.append(
                {
                    "id": identifier,
                    "from": previous["actual_recommendation"],
                    "to": record["actual_recommendation"],
                    "expected": record.get("expected_recommendation"),
                    "now_correct": record["actual_recommendation"]
                    == record.get("expected_recommendation"),
                }
            )
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two CaseBrief eval runs.")
    parser.add_argument("baseline", nargs="?", help="baseline results file")
    parser.add_argument("candidate", nargs="?", help="candidate results file")
    parser.add_argument("--list", action="store_true", help="list available runs and exit")
    args = parser.parse_args()

    runs = available_runs()
    if args.list:
        for run in runs:
            payload = load(run)
            label = payload.get("label") or "(no label)"
            print(f"{run.name}  {label}  model={payload.get('model')}")
        return 0

    if args.baseline and args.candidate:
        baseline_path, candidate_path = Path(args.baseline), Path(args.candidate)
    elif len(runs) >= 2:
        baseline_path, candidate_path = runs[-2], runs[-1]
    else:
        print("Need two runs to compare. Run `python evals/run_evals.py` at least twice.")
        return 1

    before, after = load(baseline_path), load(candidate_path)
    print(f"baseline  {baseline_path.name}  {before.get('label') or '(no label)'}  model={before.get('model')}")
    print(f"candidate {candidate_path.name}  {after.get('label') or '(no label)'}  model={after.get('model')}\n")

    print(f"{'metric':40}{'baseline':>10}{'candidate':>11}{'delta':>9}  verdict")
    print("-" * 82)
    for metric, old, new, verdict in compare_summaries(before["summary"], after["summary"]):
        if isinstance(old, float) or isinstance(new, float):
            print(f"{metric:40}{old * 100:9.1f}%{new * 100:10.1f}%{(new - old) * 100:+8.1f}  {verdict}")
        else:
            print(f"{metric:40}{old:10}{new:11}{new - old:+9}  {verdict}")

    for key, title in (("golden", "Golden cases"), ("mutations", "Evidence mutations")):
        moved = compare_cases(before, after, key)
        print(f"\n{title}: {len(moved)} recommendation change(s)")
        for change in moved:
            flag = "now correct" if change["now_correct"] else "NOW WRONG"
            print(f"  {change['id']:44}{change['from']} -> {change['to']}  ({flag})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
