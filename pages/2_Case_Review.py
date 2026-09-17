"""Decision-ready adjudicator brief — the primary workspace.

Screen priority, deliberately: recommendation, why, remaining concerns,
evidence, human action, and only then AI assurance metrics.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src.audit.logger import EventType, log_human_event  # noqa: E402
from src.config.settings import get_settings  # noqa: E402
from src.models.schemas import AdjudicatorAction, AssuranceStatus, ReviewDecision  # noqa: E402
from src.llm.provider import get_llm_provider  # noqa: E402
from src.services.analysis_service import AnalysisError, load_latest_analysis, run_analysis  # noqa: E402
from src.services.bootstrap import ensure_ready  # noqa: E402
from src.services.case_service import get_case_detail, list_cases  # noqa: E402
from src.services.review_service import (  # noqa: E402
    DECISION_LABELS,
    ReviewError,
    get_adjudicator_actions,
    get_reviews,
    record_adjudicator_action,
    record_review,
)
from src.ui.components import (  # noqa: E402
    page_footer,
    claim_block,
    concern_block,
    contradiction_block,
    executive_assessment,
    factor_block,
    header,
    page_setup,
    pct,
    reason_block,
    recommendation_banner,
    recommendation_stats,
    sensitivity_list,
    sidebar_context,
    timeline,
)

page_setup("Case Review")
settings = get_settings()

status = ensure_ready()
if not status.ready:
    header("Decision-Ready Case Brief", "")
    st.error(status.message)
    st.stop()

cases = list_cases()
if not cases:
    st.error("No cases are loaded.")
    st.stop()

# ---------------------------------------------------------------------------
# Case selection (deep-linkable via ?case=PS-2026-00182)
# ---------------------------------------------------------------------------
options = {f"{c['case_number']} — {c['applicant_name']}": c["case_id"] for c in cases}
requested = st.query_params.get("case")
if requested:
    match = next((c for c in cases if c["case_number"].lower() == requested.lower()), None)
    if match:
        st.session_state["active_case_id"] = match["case_id"]

active_id = st.session_state.get("active_case_id", cases[0]["case_id"])
labels = list(options)
try:
    default_index = list(options.values()).index(active_id)
except ValueError:
    default_index = 0

with st.sidebar:
    choice = st.selectbox("Case", labels, index=default_index)
    st.session_state["active_case_id"] = options[choice]

case_id = st.session_state["active_case_id"]
selected_number = next(c["case_number"] for c in cases if c["case_id"] == case_id)
if st.query_params.get("case") != selected_number:
    st.query_params["case"] = selected_number

case = get_case_detail(case_id)
if case is None:
    st.error("That case could not be loaded.")
    st.stop()

documents_by_name = {d["document_name"]: d for d in case["documents"]}

sidebar_context(case)
header(
    f"{case['case_number']} — {case['applicant_name']}",
    f"Investigation status: {case['status']} · {len(case['documents'])} documents in the "
    f"completed package · {case['chunk_count']} indexed passages",
)
opened_key = f"opened::{case_id}"
if not st.session_state.get(opened_key):
    log_human_event(
        EventType.CASE_OPENED,
        f"Case {case['case_number']} opened for adjudication",
        settings.reviewer_name,
        case_id=case_id,
        metadata={"applicant": case["applicant_name"], "documents": len(case["documents"])},
    )
    st.session_state[opened_key] = True

bundle = load_latest_analysis(case_id)

# Generation source. The rest of the pipeline — retrieval, claim validation,
# contradiction detection, the rules — runs identically either way; only who
# writes the draft changes.
FIXTURE_CHOICE = "Curated fixture — instant"
LIVE_CHOICE = f"Live model — {settings.configured_model_name}"
source_choices = [FIXTURE_CHOICE] + ([LIVE_CHOICE] if settings.live_llm_available else [])

control_left, control_mid, control_right = st.columns([1, 1.3, 2])
with control_mid:
    if len(source_choices) > 1:
        source = st.radio(
            "Generation source",
            source_choices,
            index=0 if settings.effective_demo_mode else 1,
            horizontal=False,
            key=f"gen_source::{case_id}",
        )
    else:
        source = FIXTURE_CHOICE
        st.caption(
            "No live model credential is configured, so generation is served from the "
            "curated fixture. Set a provider key in `.env` to enable live generation."
        )

use_live = source == LIVE_CHOICE
if use_live:
    st.caption(
        f"Live generation calls {settings.configured_model_name} for real. On a rate-limited "
        "free tier a single case can take two to three minutes."
    )

with control_left:
    label = "Generate case brief" if bundle is None else "Re-generate case brief"
    if st.button(label, type="primary", use_container_width=True):
        spinner = (
            f"Calling {settings.configured_model_name}… this can take a few minutes on a "
            "rate-limited tier."
            if use_live
            else "Synthesizing the investigation package into a decision-ready brief…"
        )
        with st.spinner(spinner):
            try:
                provider = get_llm_provider(settings.llm_provider if use_live else "demo")
                bundle = run_analysis(case_id, provider=provider)
                st.session_state.pop(f"edit::{case_id}", None)
            except AnalysisError as exc:
                st.error(f"**The brief could not be produced** — {exc}")
                bundle = load_latest_analysis(case_id)
with control_right:
    if bundle is not None:
        st.html(
            f"<div class='mt-note' style='padding-top:.55rem'>Brief "
            f"<code>{bundle.analysis_id[:8]}</code> · model <code>{bundle.model_name}</code> · "
            f"prompt <code>{bundle.prompt_version}</code> · "
            f"{'demo fixture' if bundle.demo_mode else 'live model'} · "
            f"generated {bundle.generated_at:%Y-%m-%d %H:%M} UTC</div>")

if bundle is None:
    st.info(
        "No case brief exists yet. Select **Generate case brief** to synthesize the completed "
        "investigation package into a recommendation with evidence-backed reasoning."
    )
    st.stop()

assessment = bundle.assessment

# ===========================================================================
# 1. RECOMMENDATION
# ===========================================================================
recommendation_banner(assessment)
recommendation_stats(assessment)
st.write("")

if assessment.model_agreed_with_engine is False:
    st.info(
        f"**Recommendation reconciliation** — the model proposed "
        f"*{assessment.model_proposed_recommendation.display}*; the evidence rules produced a "
        f"different state. The more conservative outcome ships and both are recorded in the "
        f"audit trail."
    )

# ===========================================================================
# 2. EXECUTIVE CASE ASSESSMENT
# ===========================================================================
st.markdown("#### Executive case assessment")
executive_assessment(assessment.executive_case_assessment)

brief, investigation = st.columns([2.1, 1], gap="large")

with brief:
    # =======================================================================
    # 3. WHY THIS RECOMMENDATION
    # =======================================================================
    st.markdown("#### Why this recommendation?")
    st.caption(
        "Each reason traces to the passage behind it. Expand any reason to see the source "
        "document, its date, the exact supporting text and its verification status."
    )
    if not assessment.why_this_recommendation:
        st.caption("No evidence-backed reasons were produced for this brief.")
    focus_reason = st.session_state.pop("focus_reason_id", "")
    for index, reason in enumerate(assessment.why_this_recommendation, start=1):
        reason_block(
            index,
            reason,
            documents_by_name,
            case_id=case_id,
            case_number=case["case_number"],
            expanded=bool(focus_reason) and reason.reason_id == focus_reason,
        )

    # =======================================================================
    # 4. REMAINING CONCERNS
    # =======================================================================
    st.markdown("#### Remaining items requiring adjudicator attention")
    material = assessment.material_unresolved_issues
    if assessment.remaining_concerns:
        st.caption(
            f"{len(assessment.remaining_concerns)} item(s) identified · {material} material. "
            "Adverse information is listed here regardless of the recommendation."
        )
        for position, concern in enumerate(assessment.remaining_concerns):
            concern_block(
                concern,
                documents_by_name,
                case_id=case_id,
                case_number=case["case_number"],
                key_prefix=str(position),
            )
    else:
        st.caption("No outstanding items were identified in the completed package.")

    # =======================================================================
    # 5. MITIGATING FACTORS
    # =======================================================================
    st.markdown("#### Mitigating factors")
    if assessment.mitigating_factors:
        for position, factor in enumerate(assessment.mitigating_factors):
            factor_block(
                factor,
                documents_by_name,
                case_id=case_id,
                case_number=case["case_number"],
                key_prefix=str(position),
            )
    else:
        st.caption("No mitigating factors were identified in the completed package.")

    # =======================================================================
    # 6. WHAT COULD CHANGE THIS RECOMMENDATION
    # =======================================================================
    sensitivity_list(assessment.what_could_change_recommendation)

    if assessment.missing_information:
        st.markdown("#### Missing information")
        st.html(
            "<div class='mt-card'><ul style='margin:0;padding-left:1.1rem;font-size:.86rem;"
            "line-height:1.55'>"
            + "".join(f"<li>{item}</li>" for item in assessment.missing_information)
            + "</ul></div>")

    if bundle.contradictions:
        st.markdown("#### Potential contradictions")
        st.caption(
            "Flagged by a prototype heuristic. These are potential conflicts for a human to "
            "resolve, not established findings."
        )
        for flag in bundle.contradictions:
            contradiction_block(flag)

with investigation:
    st.markdown("#### Case timeline")
    timeline(case["timeline"])
    if st.button("Open the full case record", use_container_width=True, key="open_record_side"):
        st.session_state["active_case_id"] = case_id
        st.switch_page("pages/3_Case_Details.py")

# ===========================================================================
# 7. HUMAN ACTION CONTROLS
# ===========================================================================
st.divider()
st.markdown("#### Adjudicator decision")
st.caption(
    "The adjudicator is the decision-maker. The AI recommendation is preserved exactly as "
    "generated whatever is recorded here."
)

notes = st.text_area(
    "Decision notes (optional)", value="", height=80, key=f"action_notes::{case_id}"
)
proceed_col, info_col, escalate_col, view_col = st.columns(4)
chosen_action = None
with proceed_col:
    if st.button("Proceed", use_container_width=True):
        chosen_action = AdjudicatorAction.PROCEED.value
with info_col:
    if st.button("Request More Information", use_container_width=True):
        chosen_action = AdjudicatorAction.REQUEST_MORE_INFORMATION.value
with escalate_col:
    if st.button("Escalate", use_container_width=True):
        chosen_action = AdjudicatorAction.ESCALATE.value
with view_col:
    show_full = st.toggle("View Full Investigation", value=False, key=f"full::{case_id}")

if chosen_action:
    try:
        result = record_adjudicator_action(
            case_id=case_id,
            analysis_id=bundle.analysis_id,
            action=chosen_action,
            notes=notes,
        )
        agreement = (
            "matching the AI recommendation"
            if result["agreed_with_ai"]
            else "departing from the AI recommendation"
        )
        st.success(
            f"Recorded: **{result['action_label']}** by {settings.reviewer_name}, {agreement}. "
            "The original AI recommendation is preserved."
        )
        st.rerun()
    except ReviewError as exc:
        st.error(f"Could not record the decision — {exc}")

actions = get_adjudicator_actions(bundle.analysis_id)
if actions:
    st.markdown("###### Decision history")
    for entry in actions:
        marker = "agreed with AI" if entry["agreed_with_ai"] else "departed from AI"
        with st.expander(
            f"{entry['created_at']:%Y-%m-%d %H:%M} · {entry['action_label']} · "
            f"{entry['adjudicator_name']} · {marker}"
        ):
            st.html(
                f"<div class='mt-note'><b>AI recommendation at the time of decision:</b> "
                f"{entry['ai_recommendation_label']} "
                f"({entry['ai_confidence'] * 100:.0f}% confidence, "
                f"{entry['material_unresolved_issues']} material unresolved issue(s))<br>"
                f"<b>Adjudicator action:</b> {entry['action_label']}<br>"
                f"<b>Agreement:</b> {'yes' if entry['agreed_with_ai'] else 'no'}<br>"
                f"<b>Evidence behind the recommendation:</b> "
                f"{', '.join(entry['evidence_source_ids']) or 'none recorded'}</div>")
            if entry["notes"]:
                st.markdown(f"**Notes** — {entry['notes']}")

# ===========================================================================
# 8. FULL INVESTIGATION (on demand)
# ===========================================================================
if show_full:
    st.divider()
    st.markdown("#### Full investigation package")
    documents_tab, claims_tab, narrative_tab = st.tabs(
        ["Source documents", "Claim-level validation", "AI narrative and reviewer edits"]
    )

    with documents_tab:
        record_col, reader_col = st.columns(2)
        with record_col:
            if st.button("Open the full case record →", key="open_record", use_container_width=True):
                st.session_state["active_case_id"] = case_id
                st.switch_page("pages/3_Case_Details.py")
        with reader_col:
            if st.button("Read the source documents →", key="open_reader", use_container_width=True):
                st.session_state["active_case_id"] = case_id
                st.switch_page("pages/4_Case_Documents.py")
        for document in case["documents"]:
            with st.expander(
                f"{document['document_ref']} · {document['document_name']}"
                + (f" · {document['document_date']}" if document["document_date"] else "")
            ):
                st.caption(
                    f"Type: {document['document_type']} · "
                    f"{document['characters']:,} characters"
                )
                st.text(document["raw_text"])

    with claims_tab:
        problem_count = sum(1 for c in bundle.claims if c.is_problematic)
        st.caption(
            f"{len(bundle.claims)} claims extracted from the AI narrative · {problem_count} "
            f"{'requires' if problem_count == 1 else 'require'} verification. Claim validation "
            "is what the recommendation engine consumes."
        )
        claim_filter = st.radio(
            "Show",
            ["All claims", "Needs verification", "Supported only"],
            horizontal=True,
            label_visibility="collapsed",
        )
        visible = bundle.claims
        if claim_filter == "Needs verification":
            visible = [c for c in bundle.claims if c.assurance_status != AssuranceStatus.SUPPORTED]
        elif claim_filter == "Supported only":
            visible = [c for c in bundle.claims if c.assurance_status == AssuranceStatus.SUPPORTED]
        if not visible:
            st.caption("No claims match this filter.")
        for claim in visible:
            claim_block(claim, bundle.claims.index(claim))

    with narrative_tab:
        st.markdown("**Original AI narrative summary**")
        st.html(
            f"<div class='mt-card'>{bundle.output.executive_summary}</div>")
        st.caption(
            "The narrative can be edited and accepted separately from the adjudicator decision. "
            "The original is never overwritten."
        )
        edit_key = f"edit::{case_id}"
        edited_text = st.text_area(
            "Reviewer version of the narrative",
            value=st.session_state.get(edit_key, bundle.output.executive_summary),
            height=180,
            key=edit_key,
        )
        review_notes = st.text_area(
            "Review notes (optional)", value="", height=70, key=f"notes::{case_id}"
        )
        accept_col, edit_col, reject_col, evidence_col = st.columns(4)
        decision = None
        with accept_col:
            if st.button("Accept AI narrative", use_container_width=True):
                decision = ReviewDecision.ACCEPTED.value
        with edit_col:
            if st.button("Accept with edits", use_container_width=True):
                decision = ReviewDecision.EDITED_ACCEPTED.value
        with reject_col:
            if st.button("Reject AI narrative", use_container_width=True):
                decision = ReviewDecision.REJECTED.value
        with evidence_col:
            if st.button("Require additional evidence", use_container_width=True):
                decision = ReviewDecision.MORE_EVIDENCE_REQUESTED.value

        if decision:
            if decision == ReviewDecision.EDITED_ACCEPTED.value and (
                edited_text.strip() == bundle.output.executive_summary.strip()
            ):
                st.warning(
                    "The reviewer version is identical to the AI narrative. Use **Accept AI "
                    "narrative**, or edit the text before accepting with edits."
                )
            else:
                try:
                    record_review(
                        case_id=case_id,
                        analysis_id=bundle.analysis_id,
                        decision=decision,
                        edited_text=(
                            edited_text
                            if decision == ReviewDecision.EDITED_ACCEPTED.value
                            else ""
                        ),
                        review_notes=review_notes,
                    )
                    st.success(f"Recorded: {DECISION_LABELS[decision]}.")
                    st.rerun()
                except ReviewError as exc:
                    st.error(f"Could not record the decision — {exc}")

        history = get_reviews(bundle.analysis_id)
        if history:
            st.markdown("###### Narrative review history")
            for entry in history:
                with st.expander(
                    f"{entry['created_at']:%Y-%m-%d %H:%M} · {entry['decision_label']} · "
                    f"{entry['reviewer_name']}"
                ):
                    if entry["review_notes"]:
                        st.markdown(f"**Notes** — {entry['review_notes']}")
                    if entry["diff_text"]:
                        st.markdown("**Difference from the AI draft**")
                        st.code(entry["diff_text"], language="diff")
                    st.markdown("**Original AI draft (preserved)**")
                    st.html(
                        f"<div class='mt-note'>{entry['original_text']}</div>")

# ===========================================================================
# 9. AI ASSURANCE — supporting information, deliberately last
# ===========================================================================
st.divider()
with st.expander("AI assurance metrics for this brief", expanded=False):
    metrics = bundle.metrics
    columns = st.columns(5)
    figures = [
        ("Groundedness", pct(metrics.groundedness)),
        ("Evidence coverage", pct(metrics.evidence_coverage)),
        ("Unsupported claims", str(metrics.unsupported_claims)),
        ("Contradiction flags", str(len(bundle.contradictions))),
        ("Source diversity", f"{metrics.source_diversity:.2f}"),
    ]
    for column, (label, value) in zip(columns, figures):
        with column:
            st.html(
                f"<div class='mt-stat'><div class='k'>{label}</div>"
                f"<div class='v'>{value}</div></div>")
    st.html(
        "<div class='mt-note' style='margin-top:.7rem'>Prototype AI assurance metrics. They "
        "describe how well the narrative is grounded in the package, not whether the "
        "recommendation is correct. Methodology is documented in the README.</div>")

page_footer()
