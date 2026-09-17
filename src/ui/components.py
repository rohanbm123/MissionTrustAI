"""Reusable Streamlit fragments.

Pages compose these; none of them touch the database or the LLM directly.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Sequence

import streamlit as st

from src.config.settings import get_settings
from src.models.schemas import AssuranceStatus, ContradictionFlag, ValidatedClaim
from dataclasses import asdict

from src.assurance.recommendation_engine import CATEGORY_LABELS
from src.services.evidence_service import navigation_for
from src.ui.theme import (
    CLAIM_TYPE_LABELS,
    CONCERN_STYLES,
    CSS,
    SEVERITY_STYLES,
    STATUS_STYLES,
    recommendation_style,
    severity_pill,
    status_pill,
)

DISCLAIMER = (
    "Fictional demonstration data. CaseBrief is an independent educational prototype and is "
    "not affiliated with, endorsed by, or integrated with any government agency or commercial "
    "personnel-security platform. It does not make determinations."
)


def page_setup(title: str) -> None:
    """Per-page setup: inject the stylesheet, and configure the page if needed.

    Under `st.navigation` the entry script has already called
    `set_page_config`, and a second call raises. Pages are still runnable on
    their own (`streamlit run pages/2_Case_Review.py`) during development, so
    the call is attempted and the duplicate is ignored.
    """
    try:
        st.set_page_config(
            page_title=f"CaseBrief — {title}",
            page_icon="◈",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:  # noqa: BLE001 - StreamlitAPIException on a second call
        pass
    st.html(CSS)


def header(title: str, subtitle: str = "") -> None:
    """Page header, with the product name always above the page title.

    The sidebar can be collapsed and each page names only itself, so without
    this there is no point on screen that says what the application is.
    """
    settings = get_settings()
    st.html(
        f"<div class='mt-header'><div class='brand'>{esc_raw(settings.app_name)}</div>"
        f"<h1>{esc_raw(title)}</h1>"
        f"<div class='sub'>{esc_raw(subtitle)}</div></div>")


def page_footer() -> None:
    """The standing fictional-data statement, kept out of the navigation."""
    st.html(f"<div class='mt-footer'>{DISCLAIMER}</div>")



def sidebar_context(active_case: Optional[Dict[str, Any]] = None) -> None:
    """Sidebar content beneath the navigation.

    Deliberately minimal: the runtime panel and the full disclaimer used to live
    here and dominated the rail. The model and store in use are already stated
    on each brief's provenance line, and the disclaimer now runs as a page
    footer, so the standing "this is fictional" statement survives without
    occupying the navigation.
    """
    with st.sidebar:
        if active_case:
            st.html(
                "<div class='mt-side-case'><span class='k'>Active case</span>"
                f"<span class='v'>{esc_raw(active_case['case_number'])}</span>"
                f"<span class='n'>{esc_raw(active_case['applicant_name'])}</span></div>"
            )


def metric_card(label: str, value: str, detail: str = "") -> str:
    return (
        f"<div class='mt-metric'><div class='k'>{esc_raw(label)}</div>"
        f"<div class='v'>{esc_raw(value)}</div>"
        f"<div class='d'>{esc_raw(detail)}</div></div>"
    )


def metric_row(cards: Sequence[Dict[str, str]]) -> None:
    columns = st.columns(len(cards))
    for column, card in zip(columns, cards):
        with column:
            st.html(
                metric_card(card["label"], card["value"], card.get("detail", "")))


def esc(text: Any) -> str:
    """Escape text for Streamlit markdown.

    `html.escape` alone is not enough: Streamlit treats `$...$` as LaTeX, which
    silently italicises everything between two dollar amounts — ruinous in a
    domain where the evidence is full of them.
    """
    return html.escape(str(text)).replace("$", "\\$")


def esc_raw(text: Any) -> str:
    """Escape text bound for `st.html`, which does not run the markdown parser.

    The `$` escaping in `esc()` is a markdown workaround; applied here it would
    render literal backslashes in front of every dollar amount.
    """
    return html.escape(str(text))


def pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def timeline(events: Sequence[Dict[str, Any]]) -> None:
    if not events:
        st.caption("No timeline events recorded for this case.")
        return
    rows = []
    for event in sorted(events, key=lambda e: e.get("date", "")):
        rows.append(
            "<div class='ev'>"
            f"<div class='dt'>{esc_raw(str(event.get('date', '')))}</div>"
            f"<div class='lb'>{esc_raw(str(event.get('label', '')))}</div>"
            f"<div class='de'>{esc_raw(str(event.get('detail', '')))}</div>"
            "</div>"
        )
    st.html(f"<div class='mt-tl'>{''.join(rows)}</div>")


def evidence_quote(
    document_name: str,
    source_id: str,
    text: str,
    score: float,
    cited: bool,
    score_label: str = "relevance",
) -> str:
    marker = " · cited by model" if cited else ""
    return (
        "<div class='mt-quote'>"
        f"<span class='src'>{esc_raw(document_name)} · {esc_raw(source_id)} · "
        f"{score_label} {score:.2f}{marker}</span>"
        f"{esc_raw(text)}</div>"
    )


def claim_block(claim: ValidatedClaim, index: int) -> None:
    """One claim with its status, scores and expandable evidence."""
    style = STATUS_STYLES.get(
        claim.assurance_status.value, STATUS_STYLES[AssuranceStatus.UNSUPPORTED.value]
    )
    claim_type = CLAIM_TYPE_LABELS.get(claim.claim_type.value, claim.claim_type.value)
    st.html(
        f"<div class='mt-claim' style='border-left-color:{style['fg']}'>"
        f"<div class='txt'>{esc_raw(claim.claim_text)}</div>"
        f"<div class='meta'>{status_pill(claim.assurance_status.value)} "
        f"<span class='mt-tag'>{esc_raw(claim_type)}</span>"
        f"<span class='mt-tag'>assurance {claim.confidence_score:.2f}</span>"
        f"<span class='mt-tag'>{len(claim.evidence)} source(s)</span></div></div>")

    if claim.assurance_status == AssuranceStatus.UNSUPPORTED:
        st.warning("Unsupported claim — human verification required.", icon="⚠")
    elif claim.assurance_status == AssuranceStatus.CONTRADICTED:
        st.error("Evidence conflict — potential contradiction requiring human review.", icon="⚠")

    with st.expander(f"View evidence — claim {index + 1}", expanded=False):
        if not claim.evidence:
            st.caption("No supporting passage cleared the relevance threshold.")
        for link in claim.evidence:
            st.html(
                evidence_quote(
                    link.document_name,
                    link.source_id,
                    link.evidence_text,
                    link.relevance_score,
                    link.cited_by_model,
                ))
        st.html(
            f"<div class='mt-note'><b>Score breakdown</b> — semantic {claim.semantic_score:.2f}, "
            f"retrieval {claim.retrieval_score:.2f}, entailment {claim.entailment_score:.2f}, "
            f"model self-reported confidence {claim.model_confidence:.2f}.<br>"
            f"{esc_raw(claim.rationale)}</div>")


def contradiction_block(flag: ContradictionFlag) -> None:
    st.html(
        f"<div class='mt-card'><h4>Potential contradiction — "
        f"{esc_raw(flag.conflicting_field.replace('_', ' '))}</h4>"
        f"<div class='mt-note' style='margin-bottom:.5rem'>{esc_raw(flag.description)}</div>"
        f"{evidence_quote(flag.source_a_document, flag.source_a_id or 'source A', flag.source_a_text, flag.confidence, False, 'confidence')}"
        f"{evidence_quote(flag.source_b_document, flag.source_b_id or 'source B', flag.source_b_text, flag.confidence, False, 'confidence')}"
        f"<div class='mt-note'>Detector: <code>{esc_raw(flag.detector)}</code> · "
        f"confidence {flag.confidence:.2f}. This is a prototype heuristic, not a determination.</div>"
        "</div>")


def finding_block(findings: List[Any]) -> None:
    if not findings:
        st.caption("No key findings were returned for this case.")
        return
    for finding in findings:
        sources = " ".join(
            f"<span class='mt-tag'>{esc_raw(s)}</span>" for s in finding.source_ids
        ) or "<span class='mt-tag'>no citation</span>"
        st.html(
            f"<div class='mt-claim'><div class='txt'>{esc_raw(finding.finding)}</div>"
            f"<div class='meta'>{severity_pill(finding.severity.value)} "
            f"<span class='mt-tag'>{esc_raw(finding.category)}</span> {sources}</div></div>")


def bullet_card(title: str, items: Sequence[str], empty: str) -> None:
    body = (
        "".join(f"<li>{esc_raw(item)}</li>" for item in items)
        if items
        else f"<li class='mt-note'>{esc_raw(empty)}</li>"
    )
    st.html(
        f"<div class='mt-card'><h4>{esc_raw(title)}</h4>"
        f"<ul style='margin:0;padding-left:1.1rem;font-size:.86rem;line-height:1.55'>{body}</ul></div>")


def error_panel(title: str, detail: str, hint: str = "") -> None:
    st.error(f"**{title}**\n\n{detail}" + (f"\n\n{hint}" if hint else ""))


# ---------------------------------------------------------------------------
# Decision-ready brief
# ---------------------------------------------------------------------------
def recommendation_banner(assessment: Any) -> None:
    """The first thing the adjudicator sees."""
    style = recommendation_style(assessment.overall_recommendation.value)
    st.html(
        f"<div class='mt-rec' style='background:{style['bg']};border-color:{style['bd']};"
        f"color:{style['fg']}'>"
        f"<div class='eyebrow'>Overall recommendation</div>"
        f"<div class='headline'>{style['dot']} {esc_raw(style['label'])}</div>"
        f"<div class='support'>Decision support only — the adjudicator makes the final "
        f"determination. This system does not grant or deny clearance, eligibility, employment "
        f"or legal status.</div></div>")


def recommendation_stats(assessment: Any) -> None:
    concern = assessment.overall_concern_level.value
    concern_style = CONCERN_STYLES.get(concern, CONCERN_STYLES["MODERATE"])
    material = assessment.material_unresolved_issues
    material_style = CONCERN_STYLES["HIGH"] if material else CONCERN_STYLES["NONE"]
    columns = st.columns(4)
    cards = [
        (
            "Overall concern level",
            f"<span style='color:{concern_style['fg']}'>"
            f"{'No concern identified' if concern == 'NONE' else concern.title()}</span>",
        ),
        ("Recommendation confidence", f"{assessment.recommendation_confidence * 100:.0f}%"),
        (
            "Material unresolved issues",
            f"<span style='color:{material_style['fg']}'>{material}</span>",
        ),
        ("Evidence-backed reasons", str(len(assessment.why_this_recommendation))),
    ]
    for column, (label, value) in zip(columns, cards):
        with column:
            st.html(
                f"<div class='mt-stat'><div class='k'>{esc_raw(label)}</div>"
                f"<div class='v'>{value}</div></div>")


def executive_assessment(text: str) -> None:
    st.html(
        f"<div class='mt-assess'>{esc_raw(text)}</div>")


def evidence_detail(link: Any, documents: Dict[str, Dict[str, Any]], status: str) -> str:
    """Full provenance for one passage: source, date, type, ID, score, status."""
    document = documents.get(link.document_name, {})
    meta_bits = [link.source_id]
    date = link.display_date or document.get("document_date", "")
    if date:
        meta_bits.append(date)
    kind = link.event_type if link.is_history else document.get("document_type", "")
    if kind:
        meta_bits.append(kind.replace("_", " "))
    meta_bits.append(f"relevance {link.relevance_score:.2f}")
    if link.cited_by_model:
        meta_bits.append("cited by model")
    if link.is_history:
        meta_bits.append("case history")
    return (
        "<div class='mt-quote'>"
        f"<span class='src'>{esc_raw(link.display_name)} · "
        f"{esc_raw(' · '.join(meta_bits))}</span>"
        f"{esc_raw(link.evidence_text)}</div>"
    )


def open_source_button(
    link: Any,
    *,
    case_id: str,
    case_number: str,
    reason_id: str = "",
    key: str,
    label: str = "Open in full case record →",
) -> None:
    """Hand a citation to the Case Details page as structured navigation state.

    The destination is carried on the evidence link itself, so nothing here has
    to interpret what `DOC-4-CHUNK-0` or `EVT-2026-05-06-001` means.
    """
    if st.button(label, key=key, use_container_width=True):
        navigation = navigation_for(link, case_id, case_number, reason_id)
        st.session_state["evidence_nav"] = asdict(navigation)
        st.session_state["active_case_id"] = case_id
        st.switch_page("pages/3_Case_Details.py")


def evidence_item(
    link: Any,
    documents: Dict[str, Dict[str, Any]],
    status: str,
    *,
    case_id: str,
    case_number: str,
    reason_id: str = "",
    key: str,
) -> None:
    """Inline preview plus a way into the full record — the spec asks for both."""
    preview, action = st.columns([4, 1])
    with preview:
        st.html(evidence_detail(link, documents, status))
    with action:
        open_source_button(
            link,
            case_id=case_id,
            case_number=case_number,
            reason_id=reason_id,
            key=key,
            label="Open source →",
        )


def reason_block(
    index: int,
    reason: Any,
    documents: Dict[str, Dict[str, Any]],
    *,
    case_id: str = "",
    case_number: str = "",
    expanded: bool = False,
) -> None:
    """One reason with a drill-down to the passages behind it."""
    reason_id = reason.reason_id or f"reason-{index}"
    if expanded:
        st.html(
            "<div class='mt-note' style='color:#7A5600'>Returned from the case record to this "
            "reason.</div>")
    st.html(
        f"<div class='mt-reason'>"
        f"<div class='n'>REASON {index}</div>"
        f"<div class='t'>{esc_raw(reason.reason)}</div>"
        f"<div class='meta'>{status_pill(reason.evidence_status.value)}"
        f"<span class='mt-tag'>{esc_raw(reason.category.value.replace('_', ' '))}</span>"
        f"<span class='mt-tag'>{esc_raw(reason.importance.value)} importance</span>"
        f"<span class='mt-tag'>{len(reason.evidence)} source(s)</span></div></div>")
    with st.expander(f"View evidence — reason {index}", expanded=expanded):
        if not reason.evidence:
            st.caption(
                "No passage in the package cleared the relevance threshold for this reason. "
                "Verify it directly against the investigation file."
            )
        for position, link in enumerate(reason.evidence):
            evidence_item(
                link,
                documents,
                reason.evidence_status.value,
                case_id=case_id,
                case_number=case_number,
                reason_id=reason_id,
                key=f"ev::{reason_id}::{position}::{link.source_id}",
            )
        st.html(
            f"<div class='mt-note'>Verification status: "
            f"<b>{esc_raw(reason.evidence_status.value.replace('_', ' ').title())}</b> · "
            f"assurance score {reason.verification_score:.2f}. Scores come from the claim-level "
            f"validation pipeline, not from the model's own self-report.</div>")


def concern_block(
    concern: Any,
    documents: Dict[str, Dict[str, Any]],
    *,
    case_id: str = "",
    case_number: str = "",
    key_prefix: str = "0",
) -> None:
    style = SEVERITY_STYLES.get(concern.severity.value, SEVERITY_STYLES["informational"])
    flag = (
        "<span class='mt-pill' style='color:#96201F;background:#FAE9E8;border-color:#EFC3C1'>"
        "Material</span>"
        if concern.is_material
        else ""
    )
    st.html(
        f"<div class='mt-claim' style='border-left-color:{style['fg']}'>"
        f"<div class='txt'>{esc_raw(concern.concern)}</div>"
        f"<div class='meta'>{severity_pill(concern.severity.value)}{flag}"
        f"<span class='mt-tag'>{esc_raw(concern.category.value.replace('_', ' '))}</span>"
        f"</div></div>")
    detail = []
    if concern.mitigation:
        detail.append(f"<b>Mitigation:</b> {esc_raw(concern.mitigation)}")
    if concern.human_review_consideration:
        detail.append(
            f"<b>Human review consideration:</b> "
            f"{esc_raw(concern.human_review_consideration)}"
        )
    if detail:
        st.html(
            "<div class='mt-note' style='margin:-.35rem 0 .6rem .1rem'>"
            + "<br>".join(detail)
            + "</div>")
    if concern.evidence:
        with st.expander("View evidence", expanded=False):
            for position, link in enumerate(concern.evidence):
                evidence_item(
                    link,
                    documents,
                    "concern",
                    case_id=case_id,
                    case_number=case_number,
                    key=f"cn::{key_prefix}::{position}::{link.source_id}",
                )


def factor_block(
    factor: Any,
    documents: Dict[str, Dict[str, Any]],
    *,
    case_id: str = "",
    case_number: str = "",
    key_prefix: str = "0",
) -> None:
    st.html(
        f"<div class='mt-claim' style='border-left-color:#12603C'>"
        f"<div class='txt'>{esc_raw(factor.factor)}</div>"
        f"<div class='meta'>{status_pill(factor.evidence_status.value)}"
        f"<span class='mt-tag'>{esc_raw(factor.category.value.replace('_', ' '))}</span>"
        f"<span class='mt-tag'>{len(factor.evidence)} source(s)</span></div></div>")
    if factor.evidence:
        with st.expander("View evidence", expanded=False):
            for position, link in enumerate(factor.evidence):
                evidence_item(
                    link,
                    documents,
                    factor.evidence_status.value,
                    case_id=case_id,
                    case_number=case_number,
                    key=f"mf::{key_prefix}::{position}::{link.source_id}",
                )


def category_block(assessment: Any) -> None:
    style = CONCERN_STYLES.get(assessment.concern_level.value, CONCERN_STYLES["MODERATE"])
    st.html(
        f"<div class='mt-cat'>"
        f"<div class='name'>{esc_raw(CATEGORY_LABELS.get(assessment.category, assessment.category.value))}"
        f" &nbsp;<span class='mt-pill' style='color:{style['fg']};background:{style['bg']};"
        f"border-color:{style['bd']}'>{esc_raw(assessment.label)}</span></div>"
        f"<div class='concl'>{esc_raw(assessment.conclusion)}</div>"
        f"<div class='concl'>{assessment.supporting_claims} statement(s) · "
        f"{assessment.evidence_count} evidence link(s) · "
        f"{len(assessment.mitigating_factors)} mitigating · "
        f"{len(assessment.unresolved_concerns)} unresolved · "
        f"completeness {assessment.evidence_completeness * 100:.0f}%</div></div>")


def sensitivity_list(items: Sequence[str]) -> None:
    if not items:
        st.caption("No material evidence dependencies were identified for this recommendation.")
        return
    body = "".join(f"<li>{esc_raw(item)}</li>" for item in items)
    st.html(
        f"<div class='mt-card'><h4>What could change this recommendation</h4>"
        f"<ul class='mt-change' style='margin:0;padding-left:1.1rem;font-size:.86rem;"
        f"line-height:1.55'>{body}</ul></div>")
