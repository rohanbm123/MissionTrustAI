"""Case dashboard — the adjudicator's queue, ordered by what needs attention."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.models.schemas import RecommendationState  # noqa: E402
from src.services.bootstrap import ensure_ready  # noqa: E402
from src.services.case_service import list_cases  # noqa: E402
from src.services.review_service import ACTION_LABELS, adjudicator_summary  # noqa: E402
from src.ui.components import (  # noqa: E402
    header,
    page_footer,
    page_setup,
    pct,
    sidebar_context,
)
from src.ui.theme import RECOMMENDATION_STYLES  # noqa: E402

page_setup("Case Dashboard")
header(
    "Case Dashboard",
    "Completed fictional investigation packages awaiting an adjudicator decision",
)
sidebar_context()

status = ensure_ready()
if not status.ready:
    st.error(status.message)
    st.stop()

cases = list_cases()
briefed = [c for c in cases if c["recommendation"]]
actions = adjudicator_summary()


def count(state: RecommendationState) -> int:
    return sum(1 for c in briefed if c["recommendation"] == state.value)


escalate = count(RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW)
request = count(RecommendationState.REQUEST_ADDITIONAL_INFORMATION)
proceed = count(RecommendationState.PROCEED_TO_STANDARD_REVIEW)
material = sum(c["material_unresolved_issues"] or 0 for c in briefed)

st.markdown("#### Queue")
st.caption(
    "Sorted so the cases needing attention come first. Click a row's case, then open its brief."
)

RANK = {
    RecommendationState.ESCALATE_FOR_ENHANCED_REVIEW.value: 0,
    RecommendationState.REQUEST_ADDITIONAL_INFORMATION.value: 1,
    RecommendationState.PROCEED_TO_STANDARD_REVIEW.value: 2,
}


def recommendation_label(value) -> str:
    if not value:
        return "— not yet briefed"
    style = RECOMMENDATION_STYLES.get(value)
    return f"{style['dot']} {style['label']}" if style else value


rows = []
for case in cases:
    rows.append(
        {
            "_rank": RANK.get(case["recommendation"], 3),
            "Case ID": case["case_number"],
            "Applicant": case["applicant_name"],
            "Recommendation": recommendation_label(case["recommendation"]),
            "Concern": (case["concern_level"] or "—").title(),
            "Confidence": case["recommendation_confidence"],
            "Material issues": case["material_unresolved_issues"],
            "Key signal": case["key_signal"],
            "Adjudicator action": ACTION_LABELS.get(
                case["adjudicator_action"], "Not yet decided"
            ),
            "Groundedness": case["groundedness"],
            "Last updated": case["updated_at"],
        }
    )
frame = pd.DataFrame(rows).sort_values(["_rank", "Case ID"]).drop(columns="_rank")
# ProgressColumn renders the raw value, so percentages are supplied on a 0-100 scale.
for column in ("Confidence", "Groundedness"):
    frame[column] = (frame[column].astype(float) * 100).round(0)

filter_col, flag_col = st.columns([2, 1])
with filter_col:
    query = (
        st.text_input(
            "Filter by applicant, case number or signal", "", placeholder="e.g. Morgan, financial"
        )
        .strip()
        .lower()
    )
with flag_col:
    only_open = st.checkbox("Only cases needing attention", value=False)

view = frame
if query:
    mask = (
        view["Applicant"].str.lower().str.contains(query)
        | view["Case ID"].str.lower().str.contains(query)
        | view["Key signal"].str.lower().str.contains(query)
    )
    view = view[mask]
if only_open:
    view = view[
        view["Recommendation"].str.contains("Escalate|Request", regex=True)
        | (view["Material issues"].fillna(0) > 0)
    ]

st.dataframe(
    view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Confidence": st.column_config.ProgressColumn(
            "Confidence", min_value=0, max_value=100, format="%d%%"
        ),
        "Groundedness": st.column_config.ProgressColumn(
            "Groundedness", min_value=0, max_value=100, format="%d%%"
        ),
        "Material issues": st.column_config.NumberColumn("Material issues", format="%d"),
        "Last updated": st.column_config.DatetimeColumn("Last updated", format="YYYY-MM-DD HH:mm"),
    },
)

st.html(
    "<div class='mt-strip'>"
    f"<span>\U0001F534 <b>{escalate}</b> escalate</span><span class='sep'>|</span>"
    f"<span>\U0001F7E1 <b>{request}</b> request information</span><span class='sep'>|</span>"
    f"<span>\U0001F7E2 <b>{proceed}</b> proceed</span><span class='sep'>|</span>"
    f"<span><b>{material}</b> material unresolved issue{'' if material == 1 else 's'}</span>"
    "<span class='sep'>|</span>"
    f"<span><b>{len(briefed)}/{len(cases)}</b> briefed</span><span class='sep'>|</span>"
    f"<span><b>{int(actions['actions'])}</b> decision{'' if actions['actions'] == 1 else 's'} recorded"
    + (f", <b>{pct(actions['agreement_rate'])}</b> matched the AI" if actions["actions"] else "")
    + "</span></div>"
)

st.markdown("#### Open a case brief")
options = {f"{c['case_number']} — {c['applicant_name']}": c for c in cases}
choice = st.selectbox("Select a case", list(options), index=0, label_visibility="collapsed")
selected = options[choice]

open_col, info_col = st.columns([1, 4])
with open_col:
    if st.button("Open decision-ready brief", type="primary", use_container_width=True):
        st.session_state["active_case_id"] = selected["case_id"]
        st.switch_page("pages/2_Case_Review.py")
with info_col:
    st.html(
        f"<div class='mt-note'>{recommendation_label(selected['recommendation'])} · "
        f"{selected['key_signal']} · {selected['documents']} documents · "
        f"scenario <code>{selected['scenario']}</code></div>")

page_footer()
