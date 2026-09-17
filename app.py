"""CaseBrief entry point.

Navigation is declared explicitly with `st.navigation` rather than left to
Streamlit's filename discovery. Discovery would add a sidebar entry for this
script itself — an "app" item above the workflow that means nothing to an
adjudicator. Declaring the pages also lets the case queue be the landing page,
so opening the tool shows work waiting rather than an introduction.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="CaseBrief",
    page_icon="\u25c8",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Order here is the sidebar order; the numeric filename prefixes are kept only
# so existing `st.switch_page` paths keep working.
PAGES = [
    st.Page("pages/1_Case_Dashboard.py", title="Case Dashboard", default=True),
    st.Page("pages/2_Case_Review.py", title="Case Review"),
    st.Page("pages/3_Case_Details.py", title="Case Details"),
    st.Page("pages/4_Case_Documents.py", title="Case Documents"),
    st.Page("pages/5_AI_Assurance.py", title="AI Assurance"),
    st.Page("pages/6_Audit_Trail.py", title="Audit Trail"),
]

st.navigation(PAGES).run()
