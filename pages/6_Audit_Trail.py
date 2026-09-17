"""Audit trail — chronological record of every AI and human action."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.audit.logger import get_case_trail, get_recent_trail  # noqa: E402
from src.services.bootstrap import ensure_ready  # noqa: E402
from src.services.case_service import list_cases  # noqa: E402
from src.ui.components import (  # noqa: E402
    esc_raw,
    header,
    page_footer,
    page_setup,
    sidebar_context,
)

page_setup("Audit Trail")
header(
    "Audit Trail",
    "Append-only record of AI and human actions — nothing here is ever updated or deleted",
)
sidebar_context()
status = ensure_ready()
if not status.ready:
    st.error(status.message)
    st.stop()

ACTOR_LABELS = {"ai": "AI", "human": "Human", "system": "System"}

cases = list_cases()
scope_options = {"All cases": None}
scope_options.update(
    {f"{c['case_number']} — {c['applicant_name']}": c["case_id"] for c in cases}
)

st.caption(
    "Every action taken on a case, newest first — what the AI did and what a human did. "
    "Each row is tagged AI, Human or System."
)

controls = st.columns([2, 1])
with controls[0]:
    scope = st.selectbox(
        "Which case?",
        list(scope_options),
        help="Pick one case to see only its history, or leave on 'All cases' to see everything.",
    )
with controls[1]:
    limit = st.number_input(
        "How many rows?",
        min_value=25, max_value=1000, value=200, step=25,
        help="Newest events are kept. Raise it to look further back in time.",
    )

case_id = scope_options[scope]
events = get_case_trail(case_id, int(limit)) if case_id else get_recent_trail(int(limit))

if not events:
    st.info("No audit events match this filter yet. Open a case and run an analysis.")
    st.stop()

case_lookup = {c["case_id"]: c["case_number"] for c in cases}

st.write("")
tab_timeline, tab_table = st.tabs(["Chronological", "Table"])

with tab_timeline:
    for event in events:
        columns = st.columns([1.1, 0.7, 4.6])
        with columns[0]:
            st.html(
                f"<div class='mt-note'><b>{event.timestamp:%Y-%m-%d}</b><br>"
                f"{event.timestamp:%H:%M:%S}</div>")
        with columns[1]:
            st.html(
                f"<span class='mt-tag'>{ACTOR_LABELS.get(event.actor_type, event.actor_type)}</span>")
        with columns[2]:
            case_number = case_lookup.get(event.case_id, "—")
            st.html(
                f"<div class='mt-event-action'>{esc_raw(event.action)}</div>"
                f"<span class='mt-note'><code>{esc_raw(event.event_type)}</code> · "
                f"{esc_raw(event.actor_name)} · case {esc_raw(case_number)}</span>")
            if event.event_metadata:
                with st.expander("Event metadata"):
                    st.json(event.event_metadata)
        st.html(
            "<hr style='margin:.35rem 0;border:none;border-top:1px solid #EDF0F4'>")

with tab_table:
    frame = pd.DataFrame(
        [
            {
                "Timestamp": event.timestamp,
                "Case": case_lookup.get(event.case_id, "—"),
                "Actor": ACTOR_LABELS.get(event.actor_type, event.actor_type),
                "Actor name": event.actor_name,
                "Event": event.event_type,
                "Action": event.action,
                "Metadata": json.dumps(event.event_metadata or {})[:200],
            }
            for event in events
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Timestamp": st.column_config.DatetimeColumn(
                "Timestamp", format="YYYY-MM-DD HH:mm:ss"
            )
        },
    )
    st.download_button(
        "Export this view as CSV",
        frame.to_csv(index=False).encode("utf-8"),
        file_name="missiontrust_audit_trail.csv",
        mime="text/csv",
    )

st.html(
    "<div class='mt-note'>Audit events are written append-only by the application: the "
    "repository layer exposes no update or delete path. A production system would additionally "
    "need tamper-evident storage (write-once media, hash chaining or an external log service), "
    "which this prototype does not implement.</div>")

page_footer()
