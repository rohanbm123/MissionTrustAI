"""AI assurance dashboard — aggregate quality and human-oversight statistics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

import json  # noqa: E402

from src.config.settings import PROJECT_ROOT  # noqa: E402
from src.database.db import session_scope  # noqa: E402
from src.database.repositories import AnalysisRepository, CaseRepository  # noqa: E402
from src.services.bootstrap import ensure_ready  # noqa: E402
from src.services.review_service import (  # noqa: E402
    ACTION_LABELS,
    DECISION_LABELS,
    adjudicator_summary,
)
from src.ui.components import (  # noqa: E402
    header,
    metric_row,
    page_footer,
    page_setup,
    pct,
    sidebar_context,
)
from src.ui.theme import LINE, MUTED, NAVY, RECOMMENDATION_STYLES  # noqa: E402

page_setup("AI Assurance")
header(
    "AI Assurance Dashboard",
    "Recommendation quality and AI assurance across the demonstration caseload — "
    "supporting information for the adjudication workflow, not the workflow itself",
)
sidebar_context()
status = ensure_ready()
if not status.ready:
    st.error(status.message)
    st.stop()

PALETTE = ["#1F3A5F", "#3D7A9E", "#7A5600", "#96201F", "#12603C", "#6B2278"]
LAYOUT = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="-apple-system, Segoe UI, Roboto, sans-serif", size=12, color="#16202E"),
    margin=dict(l=10, r=10, t=40, b=10),
    xaxis=dict(gridcolor=LINE, zeroline=False),
    yaxis=dict(gridcolor=LINE, zeroline=False),
)


EVAL_RESULTS_DIR = PROJECT_ROOT / "evals" / "results"


@st.cache_data(ttl=5)
def load_latest_eval() -> dict:
    """Most recent evaluation run, when the suite has been executed."""
    if not EVAL_RESULTS_DIR.exists():
        return {}
    runs = sorted(EVAL_RESULTS_DIR.glob("run_*.json"))
    if not runs:
        return {}
    try:
        return json.loads(runs[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@st.cache_data(ttl=5)
def load_frame() -> pd.DataFrame:
    with session_scope() as session:
        cases = {case.id: case for case in CaseRepository.list_all(session)}
        rows = []
        for analysis in AnalysisRepository.list_all(session):
            metrics = AnalysisRepository.metrics_for_analysis(session, analysis.id)
            if metrics is None:
                continue
            case = cases.get(analysis.case_id)
            reviews = AnalysisRepository.get(session, analysis.id).reviews
            latest = max(reviews, key=lambda r: r.created_at) if reviews else None
            rows.append(
                {
                    "analysis_id": analysis.id,
                    "case_number": case.case_number if case else "unknown",
                    "applicant": case.applicant_name if case else "unknown",
                    "scenario": case.scenario if case else "unknown",
                    "model": analysis.model_name,
                    "prompt_version": analysis.prompt_version,
                    "generated_at": analysis.generated_at,
                    "latency_ms": analysis.latency_ms,
                    "groundedness": metrics.groundedness,
                    "evidence_coverage": metrics.evidence_coverage,
                    "unsupported_claim_rate": metrics.unsupported_claim_rate,
                    "contradiction_rate": metrics.contradiction_rate,
                    "source_diversity": metrics.source_diversity,
                    "total_claims": metrics.total_claims,
                    "supported_claims": metrics.supported_claims,
                    "weak_claims": metrics.weak_claims,
                    "unsupported_claims": metrics.unsupported_claims,
                    "contradicted_claims": metrics.contradicted_claims,
                    "contradiction_flags": len(analysis.contradictions),
                    "decision": latest.decision if latest else None,
                    "recommendation": analysis.recommendation or "NOT_BRIEFED",
                    "recommendation_confidence": analysis.recommendation_confidence,
                    "concern_level": analysis.concern_level,
                    "material_unresolved_issues": analysis.material_unresolved_issues,
                    "reasons": len(
                        (analysis.assessment or {}).get("why_this_recommendation", [])
                    ),
                    "reason_sources": sum(
                        len(reason.get("source_ids", []))
                        for reason in (analysis.assessment or {}).get(
                            "why_this_recommendation", []
                        )
                    ),
                }
            )
        return pd.DataFrame(rows)


all_analyses = load_frame()

if not all_analyses.empty:
    latest_only = st.toggle(
        "Latest analysis per case",
        value=True,
        help="Off shows every analysis run, including re-runs of the same case.",
    )
    frame = (
        all_analyses.sort_values("generated_at")
        .groupby("case_number", as_index=False)
        .last()
        if latest_only
        else all_analyses
    )
else:
    frame = all_analyses

if frame.empty:
    st.info(
        "No analyses have been generated yet. Open the **Case Review** page and run an analysis, "
        "or generate one for every case below."
    )
    if st.button("Run analysis for all cases", type="primary"):
        from src.services.analysis_service import AnalysisError, run_analysis

        with session_scope() as session:
            targets = [(c.id, c.case_number) for c in CaseRepository.list_all(session)]
        progress = st.progress(0.0, text="Analysing caseload…")
        for index, (case_id, case_number) in enumerate(targets, start=1):
            try:
                run_analysis(case_id)
            except AnalysisError as exc:
                st.warning(f"{case_number}: {exc}")
            progress.progress(index / len(targets), text=f"Analysed {case_number}")
        st.cache_data.clear()
        st.rerun()
    st.stop()

# =========================================================================
# Recommendation quality — the primary product metric set
# =========================================================================
evaluation = load_latest_eval()
adjudicators = adjudicator_summary()
briefed = frame[frame["recommendation"] != "NOT_BRIEFED"]

st.markdown("#### Recommendation quality")
if evaluation:
    summary = evaluation["summary"]
    st.caption(
        f"From evaluation run `{evaluation['run_id']}` "
        f"({summary['golden_cases']} golden cases, {summary['mutation_cases']} evidence "
        f"mutations, model `{evaluation.get('model')}`, prompt "
        f"`{evaluation.get('prompt_version')}`). Re-run with `python evals/run_evals.py`."
    )
    metric_row(
        [
            {
                "label": "Recommendation accuracy",
                "value": pct(summary["recommendation_accuracy"]),
                "detail": "Matches expected state on golden cases",
            },
            {
                "label": "Recommendation groundedness",
                "value": pct(summary["recommendation_groundedness"]),
                "detail": "Reasons backed by verified evidence",
            },
            {
                "label": "Critical evidence recall",
                "value": pct(summary["critical_evidence_recall"]),
                "detail": "Decisive documents actually reached",
            },
            {
                "label": "Unsupported recommendation rate",
                "value": pct(summary["unsupported_recommendation_rate"]),
                "detail": "Briefs without adequate support",
            },
        ]
    )
    st.write("")
    metric_row(
        [
            {
                "label": "Citation precision",
                "value": pct(summary["citation_precision"]),
                "detail": "Cited passages are relevant",
            },
            {
                "label": "Citation recall",
                "value": pct(summary["citation_recall"]),
                "detail": "Decisive facts appear in cited evidence",
            },
            {
                "label": "Reason coverage",
                "value": pct(summary["reason_coverage"]),
                "detail": "Expected topics addressed",
            },
        ]
    )
else:
    st.info(
        "No evaluation run has been recorded yet. Run `python evals/run_evals.py` to populate "
        "recommendation accuracy, stability and sensitivity metrics."
    )
    metric_row(
        [
            {
                "label": "Human agreement rate",
                "value": pct(adjudicators["agreement_rate"]) if adjudicators["actions"] else "—",
                "detail": f"{int(adjudicators['actions'])} adjudicator decision(s)",
            },
            {"label": "Proceed", "value": str(adjudicators["proceed"]), "detail": "Human actions"},
            {
                "label": "More information",
                "value": str(adjudicators["request_more_information"]),
                "detail": "Human actions",
            },
            {"label": "Escalate", "value": str(adjudicators["escalate"]), "detail": "Human actions"},
        ]
    )

st.write("")
dist_left, dist_right = st.columns(2)

with dist_left:
    st.markdown("##### Recommendation distribution")
    counts = briefed["recommendation"].value_counts()
    labels = [RECOMMENDATION_STYLES.get(k, {}).get("label", k) for k in counts.index]
    colours = [RECOMMENDATION_STYLES.get(k, {}).get("fg", NAVY) for k in counts.index]
    figure = go.Figure(
        go.Bar(
            x=labels, y=list(counts.values), marker_color=colours,
            hovertemplate="%{x}: %{y} case(s)<extra></extra>",
        )
    )
    figure.update_layout(**LAYOUT, height=330)
    st.plotly_chart(figure, use_container_width=True)

with dist_right:
    st.markdown("##### Evidence sources behind each recommendation")
    ordered = briefed.sort_values("reason_sources", ascending=False)
    figure = go.Figure(
        go.Bar(
            x=ordered["case_number"], y=ordered["reason_sources"], marker_color=NAVY,
            hovertemplate="%{x}: %{y} cited source(s)<extra></extra>",
        )
    )
    figure.update_layout(**LAYOUT, height=330)
    st.plotly_chart(figure, use_container_width=True)
    average = briefed["reason_sources"].mean() if not briefed.empty else 0
    st.caption(
        f"Average evidence sources per recommendation: {average:.1f} across "
        f"{len(briefed)} brief(s)."
    )

st.divider()
st.markdown("#### Evidence quality")
st.caption(
    "How well each brief is grounded in its case package. Supporting detail — the recommendation "
    "metrics above are the product measures."
)

left, right = st.columns(2)

with left:
    st.markdown("##### Groundedness by case")
    ordered = frame.sort_values("groundedness")
    figure = go.Figure(
        go.Bar(
            x=ordered["groundedness"],
            y=ordered["case_number"],
            orientation="h",
            marker_color=NAVY,
            hovertemplate="%{y}: %{x:.0%}<extra></extra>",
        )
    )
    figure.update_layout(**LAYOUT, height=360, xaxis_tickformat=".0%", xaxis_range=[0, 1])
    st.plotly_chart(figure, use_container_width=True)

with right:
    st.markdown("##### Evidence coverage vs groundedness")
    scatter = frame.assign(scenario=frame["scenario"].str.replace("_", " ").str.title())
    figure = px.scatter(
        scatter,
        x="evidence_coverage",
        y="groundedness",
        size="total_claims",
        color="scenario",
        hover_name="case_number",
        color_discrete_sequence=PALETTE,
    )
    figure.update_layout(
        **LAYOUT, height=360, xaxis_tickformat=".0%", yaxis_tickformat=".0%",
        legend=dict(font=dict(size=10), orientation="h", y=-0.3),
    )
    st.plotly_chart(figure, use_container_width=True)

st.markdown("##### Contradiction flags by case")
ordered = frame.sort_values("contradiction_flags", ascending=False)
figure = go.Figure(
    go.Bar(
        x=ordered["case_number"],
        y=ordered["contradiction_flags"],
        marker_color="#6B2278",
        hovertemplate="%{x}: %{y} flag(s)<extra></extra>",
    )
)
figure.update_layout(**LAYOUT, height=320)
st.plotly_chart(figure, use_container_width=True)

st.markdown("##### Per-analysis detail")
display = all_analyses.sort_values("generated_at", ascending=False)[
    [
        "case_number", "applicant", "model", "prompt_version", "total_claims",
        "groundedness", "evidence_coverage", "unsupported_claims", "contradiction_flags",
        "source_diversity", "latency_ms", "decision",
    ]
].rename(
    columns={
        "case_number": "Case ID", "applicant": "Applicant", "model": "Model",
        "prompt_version": "Prompt", "total_claims": "Claims", "groundedness": "Groundedness",
        "evidence_coverage": "Coverage", "unsupported_claims": "Unsupported",
        "contradiction_flags": "Contradictions", "source_diversity": "Source diversity",
        "latency_ms": "Latency (ms)", "decision": "Human decision",
    }
)
display["Human decision"] = display["Human decision"].map(
    lambda d: DECISION_LABELS.get(d, "Not reviewed")
)
# ProgressColumn renders the raw value, so percentages are supplied on a 0-100 scale.
display["Groundedness"] = (display["Groundedness"] * 100).round(0)
display["Coverage"] = (display["Coverage"] * 100).round(0)
st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Groundedness": st.column_config.ProgressColumn(
            "Groundedness", min_value=0, max_value=100, format="%d%%"
        ),
        "Coverage": st.column_config.ProgressColumn(
            "Coverage", min_value=0, max_value=100, format="%d%%"
        ),
    },
)

st.html(
    f"<div class='mt-note' style='color:{MUTED}'>Adjudicator actions recorded: "
    f"{int(adjudicators['actions'])} "
    f"({adjudicators['proceed']} {ACTION_LABELS['proceed'].lower()}, "
    f"{adjudicators['request_more_information']} "
    f"{ACTION_LABELS['request_more_information'].lower()}, "
    f"{adjudicators['escalate']} {ACTION_LABELS['escalate'].lower()}).</div>")
st.html(
    f"<div class='mt-note' style='color:{MUTED}'>These are <b>prototype AI assurance "
    "metrics</b> for a demonstration system. They are not regulatory, safety or compliance "
    "measures, and they have not been validated against human-labelled ground truth. The "
    "calculation methodology for every metric is documented in the README.</div>")

page_footer()
