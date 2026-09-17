"""Case Details — the complete fictional investigation record.

Two jobs:

1. Let the adjudicator navigate the whole case manually.
2. Be the landing target for a citation in the AI brief: open the right
   document or history event, highlight the exact passage, and offer the way
   back to the reason they came from.

The passages rendered here are the same `document_chunks` rows the retriever
searches. There is one source of truth for the case record.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from src.config.settings import get_settings  # noqa: E402
from src.services.analysis_service import load_latest_analysis  # noqa: E402
from src.services.bootstrap import ensure_ready  # noqa: E402
from src.services.case_service import get_case_detail, list_cases  # noqa: E402
from src.services.evidence_service import (  # noqa: E402
    SOURCE_NOT_FOUND,
    EvidenceNavigation,
    case_record_summary,
    cited_source_ids,
    document_sections,
    history_events,
    investigation_completeness,
    log_evidence_opened,
    resolve_source,
    usages_for_source,
)
from src.ui.components import (  # noqa: E402
    page_footer,
    esc,
    esc_raw,
    header,
    metric_row,
    page_setup,
    pct,
    sidebar_context,
    timeline,
)

SECTIONS = ["Overview", "Documents", "Case History", "Timeline", "Investigator Notes"]

page_setup("Case Details")
settings = get_settings()

status = ensure_ready()
if not status.ready:
    header("Case Details", "")
    st.error(status.message)
    st.stop()

cases = list_cases()
if not cases:
    st.error("No cases are loaded.")
    st.stop()


# ---------------------------------------------------------------------------
# Navigation state: session first, then query parameters (deep-linkable)
# ---------------------------------------------------------------------------
def _pop_navigation() -> EvidenceNavigation | None:
    """A pending jump handed over by the Case Review page."""
    payload = st.session_state.pop("evidence_nav", None)
    if not payload:
        return None
    return EvidenceNavigation(**payload)


navigation = _pop_navigation()

by_number = {c["case_number"]: c for c in cases}
requested_case = st.query_params.get("case")
if navigation:
    st.session_state["active_case_id"] = navigation.case_id
elif requested_case and requested_case in by_number:
    st.session_state["active_case_id"] = by_number[requested_case]["case_id"]

active_id = st.session_state.get("active_case_id", cases[0]["case_id"])
options = {f"{c['case_number']} — {c['applicant_name']}": c["case_id"] for c in cases}
try:
    default_index = list(options.values()).index(active_id)
except ValueError:
    default_index = 0

with st.sidebar:
    choice = st.selectbox("Case", list(options), index=default_index)
    st.session_state["active_case_id"] = options[choice]

case_id = st.session_state["active_case_id"]
case = get_case_detail(case_id)
if case is None:
    st.error("That case could not be loaded.")
    st.stop()

# A citation arriving either as session state or as a bare deep link.
target_source_id = navigation.source_id if navigation else st.query_params.get("source", "")
reason_id = navigation.reason_id if navigation else st.query_params.get("reason", "")
resolved = resolve_source(case_id, target_source_id) if target_source_id else None

if navigation and resolved is not None:
    log_evidence_opened(navigation, settings.reviewer_name, resolved)
    st.query_params.update(
        {k: v for k, v in navigation.query_params().items() if k != "case"}
    )
    st.query_params["case"] = case["case_number"]

# The resolved source decides which section opens — never a parsed identifier.
if resolved is not None and resolved.found:
    st.session_state["details_section"] = resolved.tab
    if resolved.document_ref:
        st.session_state["details_document"] = resolved.document_ref

sidebar_context(case)
header(
    f"Case Details — {case['case_number']} · {case['applicant_name']}",
    "The complete fictional investigation record: documents, history, timeline and notes",
)
# ---------------------------------------------------------------------------
# Return path to the brief
# ---------------------------------------------------------------------------
back_col, ref_col = st.columns([1, 3])
with back_col:
    if st.button("← Back to AI Case Brief", use_container_width=True):
        st.session_state["active_case_id"] = case_id
        if reason_id:
            st.session_state["focus_reason_id"] = reason_id
        st.switch_page("pages/2_Case_Review.py")
with ref_col:
    if resolved is not None and not resolved.found:
        st.warning(
            f"{SOURCE_NOT_FOUND} The citation `{esc(target_source_id)}` does not "
            "correspond to any passage in this case record. Browse the record below.",
            icon="⚠",
        )
    elif resolved is not None and resolved.found:
        origin = f" · arriving from {reason_id}" if reason_id else ""
        st.html(
            f"<div class='mt-note' style='padding-top:.55rem'>Showing "
            f"<code>{esc_raw(resolved.source_id)}</code> in "
            f"<b>{esc_raw(resolved.label)}</b>{esc_raw(origin)}</div>")

# ---------------------------------------------------------------------------
# Section selector (a radio, not st.tabs, because this must be steerable)
# ---------------------------------------------------------------------------
if st.session_state.get("details_section") not in SECTIONS:
    st.session_state["details_section"] = "Overview"

section = st.radio(
    "Section",
    SECTIONS,
    horizontal=True,
    key="details_section",
    label_visibility="collapsed",
)

summary = case_record_summary(case_id)
cited = cited_source_ids(case_id)
bundle = load_latest_analysis(case_id)


def scroll_to(anchor: str) -> None:
    """Bring an anchored passage into view.

    Best-effort: the highlighted passage is also surfaced in a callout at the
    top of the section, so the adjudicator sees it whether or not the browser
    allows the component to reach the parent document.
    """
    components.html(
        f"""
        <script>
        const target = "{anchor}";
        const doc = window.parent && window.parent.document;
        if (doc) {{
            const tries = [0, 250, 600, 1100];
            tries.forEach(function (delay) {{
                setTimeout(function () {{
                    const el = doc.getElementById(target);
                    if (el) {{ el.scrollIntoView({{behavior: "smooth", block: "center"}}); }}
                }}, delay);
            }});
        }}
        </script>
        """,
        height=0,
    )


def usage_panel(source_id: str) -> None:
    """Evidence → AI brief: which reasons rest on this passage."""
    usages = usages_for_source(case_id, source_id)
    if not usages:
        return
    st.markdown("###### Used in AI recommendation")
    for usage in usages:
        label = f"{usage.reason_id}: " if usage.reason_id else f"{usage.kind.title()}: "
        st.html(
            f"<div class='mt-note'><b>{esc_raw(label)}</b>"
            f"{esc_raw(usage.reason)}</div>")
    if st.button("Return to reason in the AI brief", key=f"return::{source_id}"):
        st.session_state["active_case_id"] = case_id
        first = next((u.reason_id for u in usages if u.reason_id), "")
        if first:
            st.session_state["focus_reason_id"] = first
        st.switch_page("pages/2_Case_Review.py")


# ===========================================================================
# Overview
# ===========================================================================
if section == "Overview":
    metric_row(
        [
            {"label": "Case ID", "value": case["case_number"], "detail": case["applicant_name"]},
            {
                "label": "Investigation status",
                "value": case["status"],
                "detail": f"Opened {case['opened_on']}",
            },
            {
                "label": "Documents",
                "value": str(summary.get("document_count", 0)),
                "detail": f"{summary.get('passage_count', 0)} addressable passages",
            },
            {
                "label": "History events",
                "value": str(summary.get("history_event_count", 0)),
                "detail": "Alerts, statements and status events",
            },
        ]
    )
    st.write("")
    completeness = investigation_completeness(case_id)
    metric_row(
        [
            {
                "label": "Investigation completeness",
                "value": pct(completeness["ratio"]),
                "detail": f"{len(completeness['present'])} of 5 standing record types present",
            },
            {
                "label": "Last updated",
                "value": f"{summary.get('updated_at'):%Y-%m-%d}" if summary.get("updated_at") else "—",
                "detail": "Most recent change to the record",
            },
            {
                "label": "Key signal",
                "value": case["key_signal"][:28] + ("…" if len(case["key_signal"]) > 28 else ""),
                "detail": f"Scenario: {case['scenario']}",
            },
            {
                "label": "Cited by the AI brief",
                "value": str(len(cited)),
                "detail": "Distinct passages behind the recommendation",
            },
        ]
    )

    st.write("")
    left, right = st.columns(2)
    with left:
        st.markdown("##### Record types present")
        for label in completeness["present"]:
            st.html(f"<div class='mt-note'>• {label}</div>")
        if completeness["absent"]:
            st.markdown("##### Not present in this package")
            for label in completeness["absent"]:
                st.html(
                    f"<div class='mt-note' style='color:#7A5600'>• {label}</div>")
        st.caption(
            "A coverage indicator only: it reports which categories of record the package "
            "contains, not whether the investigation was adequate."
        )
    with right:
        st.markdown("##### Document categories")
        for category in summary.get("categories", []):
            st.html(f"<div class='mt-note'>• {category}</div>")

    st.write("")
    if summary.get("has_brief"):
        st.html(
            "<div class='mt-note'>A decision-ready brief exists for this case. Open "
            "<b>Case Review</b> for the recommendation, or use the sections above to inspect "
            "the record directly.</div>")
    if st.button("Open the AI case brief"):
        st.session_state["active_case_id"] = case_id
        st.switch_page("pages/2_Case_Review.py")

# ===========================================================================
# Documents
# ===========================================================================
elif section == "Documents":
    documents = case["documents"]
    refs = [d["document_ref"] for d in documents]
    labels = {
        d["document_ref"]: (
            f"{d['document_ref']} · {d['document_name']}"
            + (f" · {d['document_date']}" if d["document_date"] else "")
        )
        for d in documents
    }

    wanted = st.session_state.get("details_document")
    index = refs.index(wanted) if wanted in refs else 0
    chosen_ref = st.selectbox(
        "Document",
        refs,
        index=index,
        format_func=lambda ref: labels[ref],
        key="document_picker",
    )
    st.session_state["details_document"] = chosen_ref
    document = next(d for d in documents if d["document_ref"] == chosen_ref)

    st.html(
        f"<div class='mt-note'>Type: {esc_raw(document['document_type'])} · "
        f"{document['characters']:,} characters"
        + (f" · dated {esc_raw(document['document_date'])}" if document["document_date"] else "")
        + "</div>")

    sections_for_doc = document_sections(case_id, chosen_ref)
    highlight = (
        resolved.source_id
        if resolved is not None and resolved.found and resolved.document_ref == chosen_ref
        else ""
    )

    if highlight:
        referenced = next((s for s in sections_for_doc if s["source_id"] == highlight), None)
        if referenced:
            st.html(
                "<div class='mt-refbar'><div class='eyebrow'>Referenced by AI recommendation"
                + (f" — {esc_raw(reason_id)}" if reason_id else "")
                + "</div><div style='font-family:ui-monospace,Menlo,monospace;font-size:.68rem;"
                f"letter-spacing:.05em;color:#7A5600'>{esc_raw(highlight)}</div>"
                f"<div style='font-size:.88rem;line-height:1.6;margin-top:.35rem;"
                f"white-space:pre-wrap'>{esc_raw(referenced['content'])}</div></div>"
            )
            usage_panel(highlight)
            scroll_to(highlight)

    st.markdown("##### Document content")
    st.caption(
        "The document is shown in the addressable passages the retrieval index uses. Passage "
        "identifiers here are the identifiers the AI cites."
    )
    for part in sections_for_doc:
        classes = "mt-passage"
        if part["source_id"] == highlight:
            classes += " is-referenced"
        elif part["source_id"] in cited:
            classes += " is-cited"
        badge = ""
        if part["source_id"] in cited and part["source_id"] != highlight:
            badge = " · cited by the AI brief"
        # Verbatim passage text: st.html so document formatting is not reinterpreted.
        st.html(
            f"<div class='{classes}' id='{esc_raw(part['source_id'])}'>"
            f"<span class='anchor'>{esc_raw(part['source_id'])}{esc_raw(badge)}</span>"
            f"{esc_raw(part['content'])}</div>"
        )

    if st.button("Read this document as filed →", key=f"read::{chosen_ref}"):
        st.session_state["active_case_id"] = case_id
        st.session_state["reader_document"] = chosen_ref
        st.switch_page("pages/4_Case_Documents.py")
    st.caption(
        "The reading view shows the filed document without passage identifiers or highlights."
    )

# ===========================================================================
# Case History
# ===========================================================================
elif section == "Case History":
    events = history_events(case_id)
    st.caption(
        f"{len(events)} recorded events. Monitoring alerts, applicant statements, status changes "
        "and investigative entries are citable evidence with their own stable identifiers."
    )
    highlight = (
        resolved.event_ref if resolved is not None and resolved.found and resolved.is_history else ""
    )

    if highlight:
        referenced = next((e for e in events if e.event_ref == highlight), None)
        if referenced:
            st.html(
                "<div class='mt-refbar'><div class='eyebrow'>Referenced by AI recommendation"
                + (f" — {esc_raw(reason_id)}" if reason_id else "")
                + "</div><div style='font-family:ui-monospace,Menlo,monospace;font-size:.68rem;"
                f"letter-spacing:.05em;color:#7A5600'>{esc_raw(referenced.event_ref)} · "
                f"{esc_raw(referenced.event_type.replace('_', ' '))}</div>"
                f"<div style='font-size:.88rem;line-height:1.6;margin-top:.35rem'>"
                f"<b>{esc_raw(referenced.event_date)} — {esc_raw(referenced.label)}</b><br>"
                f"{esc_raw(referenced.detail)}</div></div>")
            usage_panel(highlight)
            scroll_to(highlight)

    type_options = ["All"] + sorted({e.event_type.replace("_", " ").title() for e in events})
    chosen_type = st.radio(
        "Event type", type_options, horizontal=True, label_visibility="collapsed"
    )
    for event in events:
        pretty = event.event_type.replace("_", " ").title()
        if chosen_type != "All" and pretty != chosen_type:
            continue
        classes = "mt-event"
        if event.event_ref == highlight:
            classes += " is-referenced"
        badge = " · cited by the AI brief" if event.source_id in cited else ""
        st.html(
            f"<div class='{classes}' id='{esc_raw(event.event_ref)}'>"
            f"<div class='when'>{esc_raw(event.event_date)} · "
            f"{esc_raw(event.event_ref)} · {esc_raw(pretty)}"
            f"{esc_raw(badge)}</div>"
            f"<div class='what'>{esc_raw(event.label)}</div>"
            f"<div class='why'>{esc_raw(event.detail)}</div></div>")

# ===========================================================================
# Timeline
# ===========================================================================
elif section == "Timeline":
    st.caption(
        "The same events as Case History, read chronologically. Continuous context, so an event "
        "is interpreted against what preceded it rather than in isolation."
    )
    timeline(case["timeline"])

# ===========================================================================
# Investigator Notes
# ===========================================================================
else:
    note_types = {"case_notes", "investigation_summary", "reference_interview"}
    notes = [d for d in case["documents"] if d["document_type"] in note_types]
    if not notes:
        st.caption("This package contains no investigator notes or investigation summaries.")
    for document in notes:
        st.markdown(
            f"##### {document['document_ref']} · {document['document_name']}"
            + (f" · {document['document_date']}" if document["document_date"] else "")
        )
        for part in document_sections(case_id, document["document_ref"]):
            classes = "mt-passage" + (" is-cited" if part["source_id"] in cited else "")
            badge = " · cited by the AI brief" if part["source_id"] in cited else ""
            st.html(
                f"<div class='{classes}' id='{esc_raw(part['source_id'])}'>"
                f"<span class='anchor'>{esc_raw(part['source_id'])}"
                f"{esc_raw(badge)}</span>{esc_raw(part['content'])}</div>"
            )

if bundle is not None:
    st.divider()
    st.caption(
        f"Current brief {bundle.analysis_id[:8]} · "
        f"{bundle.assessment.overall_recommendation.display} · "
        f"{len(cited)} distinct passages cited across "
        f"{len(bundle.assessment.why_this_recommendation)} reasons."
    )

page_footer()
