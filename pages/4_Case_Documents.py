"""Case Documents — the source documents, as filed.

A reading surface, deliberately plain. Case Details shows a document broken into
the addressable passages the retrieval index uses, with AI citations highlighted;
that view answers "what did the AI rely on". This one answers "what does the
document actually say", so it shows the filed text and nothing else.

Same underlying records either way — there is one copy of the case file.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src.services.bootstrap import ensure_ready  # noqa: E402
from src.services.case_service import get_case_detail, list_cases  # noqa: E402
from src.services.evidence_service import cited_source_ids  # noqa: E402
from src.ui.components import (  # noqa: E402
    page_footer,
    esc_raw,
    header,
    page_setup,
    sidebar_context,
)

page_setup("Case Documents")

status = ensure_ready()
if not status.ready:
    header("Case Documents", "")
    st.error(status.message)
    st.stop()

cases = list_cases()
if not cases:
    st.error("No cases are loaded.")
    st.stop()

# ---------------------------------------------------------------------------
# Case selection, shared with the rest of the app and deep-linkable
# ---------------------------------------------------------------------------
by_number = {c["case_number"]: c for c in cases}
requested_case = st.query_params.get("case")
if requested_case in by_number:
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

documents = case["documents"]
if not documents:
    st.warning("This case package contains no documents.")
    st.stop()

sidebar_context(case)
header(
    f"Case Documents — {case['case_number']} · {case['applicant_name']}",
    f"The {len(documents)} source documents in the completed investigation package, as filed",
)
# ---------------------------------------------------------------------------
# Document selection (deep link: ?case=PS-2026-00182&document=DOC-4)
# ---------------------------------------------------------------------------
refs = [d["document_ref"] for d in documents]
requested_document = st.query_params.get("document")
if requested_document in refs:
    st.session_state["reader_document"] = requested_document

wanted = st.session_state.get("reader_document")
index = refs.index(wanted) if wanted in refs else 0

index_column, reader_column = st.columns([1, 2.4], gap="large")

with index_column:
    st.markdown("##### Documents in this package")
    chosen_ref = st.radio(
        "Document",
        refs,
        index=index,
        format_func=lambda ref: (
            f"{ref} · {next(d for d in documents if d['document_ref'] == ref)['document_name']}"
        ),
        captions=[
            (d["document_date"] or d["document_type"].replace("_", " ")) for d in documents
        ],
        key="document_reader_picker",
        label_visibility="collapsed",
    )
    st.session_state["reader_document"] = chosen_ref

document = next(d for d in documents if d["document_ref"] == chosen_ref)
if st.query_params.get("document") != chosen_ref:
    st.query_params["document"] = chosen_ref
    st.query_params["case"] = case["case_number"]

# How much of this document the current brief leans on — one quiet line, so the
# reading view stays a reading view.
cited = cited_source_ids(case_id)
cited_here = sum(1 for source_id in cited if source_id.startswith(f"{chosen_ref}-CHUNK-"))

with reader_column:
    meta_bits = [document["document_type"].replace("_", " ")]
    if document["document_date"]:
        meta_bits.append(document["document_date"])
    meta_bits.append(f"{document['characters']:,} characters")

    st.html(
        f"<div class='mt-doc-head'>"
        f"<span class='name'>{esc_raw(document['document_name'])}</span>"
        f"<span class='ref'>{esc_raw(document['document_ref'])}</span></div>"
        f"<div class='mt-note' style='margin-top:-.35rem'>{esc_raw(' · '.join(meta_bits))}"
        + (
            f" · cited {cited_here} time(s) by the current AI brief"
            if cited_here
            else " · not cited by the current AI brief"
        )
        + "</div>"
    )

    # st.html, not st.markdown: the document must render exactly as filed, and a
    # markdown pass would treat the documents' own "=====" underlines as headings.
    st.html(f"<div class='mt-doc'>{esc_raw(document['raw_text'])}</div>")

    st.write("")
    provenance, download, brief = st.columns(3)
    with provenance:
        if st.button("Open in the full case record →", use_container_width=True):
            st.session_state["active_case_id"] = case_id
            st.session_state["details_section"] = "Documents"
            st.session_state["details_document"] = chosen_ref
            st.switch_page("pages/3_Case_Details.py")
    with download:
        st.download_button(
            "Download as .txt",
            data=document["raw_text"],
            file_name=f"{case['case_number']}_{chosen_ref}_{document['document_name'].replace(' ', '_')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with brief:
        if st.button("Open the AI case brief", use_container_width=True):
            st.session_state["active_case_id"] = case_id
            st.switch_page("pages/2_Case_Review.py")

    st.caption(
        "The full case record view shows this document split into the addressable passages the "
        "retrieval index uses, with AI citations highlighted. Both views read the same stored "
        "document — the case file is not duplicated."
    )

page_footer()
