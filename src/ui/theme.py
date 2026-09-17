"""Shared visual language: neutral, dense, enterprise.

Kept in one place so the four pages stay consistent and the page files hold
layout rather than styling.
"""
from __future__ import annotations

from src.models.schemas import AssuranceStatus

INK = "#16202E"
MUTED = "#5B6B7F"
LINE = "#DFE4EB"
NAVY = "#1F3A5F"
SURFACE = "#FFFFFF"
CANVAS = "#F4F6F9"
MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace'

STATUS_STYLES = {
    AssuranceStatus.SUPPORTED.value: {"label": "Supported", "fg": "#12603C", "bg": "#E6F3EC", "bd": "#B7DDC8"},
    AssuranceStatus.WEAK_SUPPORT.value: {"label": "Weak support", "fg": "#7A5600", "bg": "#FBF1DC", "bd": "#EBD5A3"},
    AssuranceStatus.UNSUPPORTED.value: {"label": "Unsupported", "fg": "#96201F", "bg": "#FAE9E8", "bd": "#EFC3C1"},
    AssuranceStatus.CONTRADICTED.value: {"label": "Contradicted", "fg": "#6B2278", "bg": "#F5EAF7", "bd": "#DFC3E6"},
}

# Muted, print-safe status colours: a decision surface, not a traffic light.
RECOMMENDATION_STYLES = {
    "PROCEED_TO_STANDARD_REVIEW": {
        "label": "Proceed to Standard Review", "dot": "\U0001F7E2",
        "fg": "#12603C", "bg": "#EDF7F1", "bd": "#B7DDC8",
    },
    "REQUEST_ADDITIONAL_INFORMATION": {
        "label": "Request Additional Information", "dot": "\U0001F7E1",
        "fg": "#7A5600", "bg": "#FDF7EA", "bd": "#EBD5A3",
    },
    "ESCALATE_FOR_ENHANCED_REVIEW": {
        "label": "Escalate for Enhanced Review", "dot": "\U0001F534",
        "fg": "#96201F", "bg": "#FCF0EF", "bd": "#EFC3C1",
    },
}

CONCERN_STYLES = {
    "NONE": {"fg": "#12603C", "bg": "#E6F3EC", "bd": "#B7DDC8"},
    "LOW": {"fg": "#12603C", "bg": "#E6F3EC", "bd": "#B7DDC8"},
    "MODERATE": {"fg": "#7A5600", "bg": "#FBF1DC", "bd": "#EBD5A3"},
    "HIGH": {"fg": "#96201F", "bg": "#FAE9E8", "bd": "#EFC3C1"},
}

SEVERITY_STYLES = {
    "high": {"fg": "#96201F", "bg": "#FAE9E8", "bd": "#EFC3C1"},
    "moderate": {"fg": "#7A5600", "bg": "#FBF1DC", "bd": "#EBD5A3"},
    "low": {"fg": "#12603C", "bg": "#E6F3EC", "bd": "#B7DDC8"},
    "informational": {"fg": "#3A4C63", "bg": "#EEF1F6", "bd": "#D3DAE5"},
}

CLAIM_TYPE_LABELS = {
    "fact": "Fact",
    "potential_concern": "Potential concern",
    "mitigation": "Mitigation",
    "missing_evidence": "Missing evidence",
}

CSS = f"""
<style>
  html, body, [class*="css"] {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: {INK};
  }}
  .block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1500px; }}
  #MainMenu, footer {{ visibility: hidden; }}
  [data-testid="stAppDeployButton"], [data-testid="stToolbar"] {{ display: none !important; }}

  .mt-header {{
      border-bottom: 1px solid {LINE}; padding-bottom: .9rem; margin-bottom: 1.4rem;
  }}
  .mt-header h1 {{
      font-size: 1.45rem; font-weight: 650; letter-spacing: -.01em; margin: 0; color: {INK};
  }}
  .mt-header .sub {{ color: {MUTED}; font-size: .86rem; margin-top: .25rem; }}

  .mt-card {{
      background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px;
      padding: 1rem 1.1rem; margin-bottom: .8rem;
  }}
  .mt-card h4 {{
      margin: 0 0 .55rem 0; font-size: .74rem; font-weight: 650;
      text-transform: uppercase; letter-spacing: .07em; color: {MUTED};
  }}

  .mt-metric {{
      background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px;
      padding: .85rem .95rem; height: 100%;
  }}
  .mt-metric .k {{
      font-size: .7rem; text-transform: uppercase; letter-spacing: .07em;
      color: {MUTED}; font-weight: 600; margin-bottom: .35rem;
  }}
  .mt-metric .v {{ font-size: 1.55rem; font-weight: 640; line-height: 1.1; color: {INK}; }}
  .mt-metric .d {{ font-size: .74rem; color: {MUTED}; margin-top: .3rem; }}

  .mt-pill {{
      display: inline-block; padding: .12rem .5rem; border-radius: 999px;
      font-size: .7rem; font-weight: 640; letter-spacing: .02em; border: 1px solid transparent;
      white-space: nowrap; margin-right: .35rem;
  }}
  .mt-tag {{
      display: inline-block; padding: .1rem .45rem; border-radius: 4px; background: {CANVAS};
      border: 1px solid {LINE}; color: {MUTED}; font-size: .68rem; font-weight: 600;
      margin-right: .3rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}

  .mt-claim {{
      border: 1px solid {LINE}; border-left: 3px solid {LINE}; border-radius: 6px;
      padding: .7rem .85rem; margin-bottom: .5rem; background: {SURFACE};
  }}
  .mt-claim .txt {{ font-size: .9rem; line-height: 1.45; margin-bottom: .45rem; }}
  .mt-claim .meta {{ font-size: .72rem; color: {MUTED}; }}

  .mt-quote {{
      border-left: 2px solid {NAVY}; background: {CANVAS}; padding: .55rem .7rem;
      margin: .35rem 0 .5rem 0; font-size: .82rem; line-height: 1.45; color: {INK};
      border-radius: 0 5px 5px 0;
  }}
  .mt-quote .src {{
      display: block; font-size: .68rem; color: {MUTED}; font-weight: 640;
      margin-bottom: .25rem; text-transform: uppercase; letter-spacing: .05em;
  }}

  .mt-banner {{
      border: 1px solid #E4D6A7; background: #FCF6E4; color: #6A5310;
      padding: .5rem .8rem; border-radius: 6px; font-size: .78rem; margin-bottom: 1rem;
  }}
  .mt-note {{ font-size: .74rem; color: {MUTED}; line-height: 1.5; }}

  .mt-tl {{ border-left: 2px solid {LINE}; padding-left: .85rem; margin-left: .25rem; }}
  .mt-tl .ev {{ position: relative; padding-bottom: .8rem; }}
  .mt-tl .ev:before {{
      content: ""; position: absolute; left: -1.16rem; top: .3rem; width: 7px; height: 7px;
      border-radius: 50%; background: {NAVY}; border: 2px solid {SURFACE};
  }}
  .mt-tl .dt {{ font-size: .7rem; font-weight: 650; color: {NAVY}; letter-spacing: .03em; }}
  .mt-tl .lb {{ font-size: .84rem; font-weight: 560; }}
  .mt-tl .de {{ font-size: .76rem; color: {MUTED}; }}

  .mt-rec {{
      border-radius: 10px; padding: 1.15rem 1.3rem; margin-bottom: .9rem;
      border: 1px solid transparent;
  }}
  .mt-rec .eyebrow {{
      font-size: .68rem; font-weight: 680; letter-spacing: .1em;
      text-transform: uppercase; opacity: .78;
  }}
  .mt-rec .headline {{
      font-size: 1.5rem; font-weight: 660; letter-spacing: -.015em; margin: .2rem 0 .1rem 0;
      line-height: 1.2;
  }}
  .mt-rec .support {{ font-size: .8rem; opacity: .82; }}

  .mt-stat {{
      border: 1px solid {LINE}; border-radius: 8px; padding: .7rem .85rem;
      background: {SURFACE}; height: 100%;
  }}
  .mt-stat .k {{
      font-size: .66rem; text-transform: uppercase; letter-spacing: .08em;
      color: {MUTED}; font-weight: 640; margin-bottom: .3rem;
  }}
  .mt-stat .v {{ font-size: 1.25rem; font-weight: 640; line-height: 1.15; }}

  .mt-reason {{
      border: 1px solid {LINE}; border-left: 3px solid {NAVY}; border-radius: 6px;
      padding: .75rem .9rem; margin-bottom: .4rem; background: {SURFACE};
  }}
  .mt-reason .n {{
      font-size: .68rem; font-weight: 700; color: {NAVY}; letter-spacing: .06em;
  }}
  .mt-reason .t {{ font-size: .92rem; line-height: 1.5; margin: .2rem 0 .45rem 0; }}

  .mt-assess {{
      background: {CANVAS}; border: 1px solid {LINE}; border-radius: 8px;
      padding: 1rem 1.15rem; font-size: .93rem; line-height: 1.65; margin-bottom: 1rem;
  }}

  .mt-cat {{
      border: 1px solid {LINE}; border-radius: 7px; padding: .6rem .75rem;
      background: {SURFACE}; margin-bottom: .45rem;
  }}
  .mt-cat .name {{ font-size: .84rem; font-weight: 620; }}
  .mt-cat .concl {{ font-size: .76rem; color: {MUTED}; margin-top: .2rem; line-height: 1.45; }}

  /* Addressable passages in the full case record */
  .mt-header .brand {{
      display: inline-flex; align-items: center; gap: .4rem;
      font-size: .8rem; font-weight: 750; letter-spacing: .12em; text-transform: uppercase;
      color: {NAVY}; margin-bottom: .35rem;
  }}
  .mt-header .brand::before {{
      content: "◈"; font-size: .9rem; letter-spacing: 0; opacity: .9;
  }}

  .mt-side-case {{
      display: flex; flex-direction: column; gap: .12rem;
      border: 1px solid {LINE}; border-radius: 7px; padding: .55rem .7rem;
      background: {SURFACE}; margin-top: .2rem;
  }}
  .mt-side-case .k {{
      font-size: .62rem; text-transform: uppercase; letter-spacing: .09em;
      color: {MUTED}; font-weight: 640;
  }}
  .mt-side-case .v {{ font-family: {MONO}; font-size: .76rem; color: {NAVY}; font-weight: 600; }}
  .mt-side-case .n {{ font-size: .82rem; font-weight: 600; }}

  .mt-event-action {{ font-size: .88rem; font-weight: 600; line-height: 1.45; }}

  .mt-footer {{
      border-top: 1px solid {LINE}; margin-top: 1.6rem; padding-top: .7rem;
      font-size: .7rem; line-height: 1.5; color: {MUTED};
  }}

  .mt-strip {{
      display: flex; flex-wrap: wrap; gap: .4rem 1.4rem; align-items: center;
      border: 1px solid {LINE}; border-radius: 8px; background: {CANVAS};
      padding: .6rem .9rem; font-size: .82rem; margin-bottom: .9rem;
  }}
  .mt-strip b {{ font-weight: 680; }}
  .mt-strip .sep {{ color: {LINE}; }}

  .mt-passage {{
      border: 1px solid {LINE}; border-left: 3px solid {LINE}; border-radius: 6px;
      padding: .7rem .9rem; margin-bottom: .5rem; background: {SURFACE};
      font-size: .87rem; line-height: 1.62; white-space: pre-wrap;
  }}
  .mt-passage .anchor {{
      display: block; font-size: .66rem; letter-spacing: .06em; font-weight: 700;
      color: {MUTED}; margin-bottom: .35rem; font-family: {MONO};
  }}
  .mt-passage.is-referenced {{
      border-left-color: #B8860B; background: #FDF8EC; border-color: #EBD5A3;
  }}
  .mt-passage.is-referenced .anchor {{ color: #7A5600; }}
  .mt-passage.is-cited {{ border-left-color: {NAVY}; }}

  /* Reading view: a document as filed, not as indexed */
  .mt-doc {{
      background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px;
      padding: 1.35rem 1.6rem; white-space: pre-wrap; word-wrap: break-word;
      font-size: .875rem; line-height: 1.72; color: {INK};
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  .mt-doc-head {{
      display: flex; justify-content: space-between; align-items: baseline;
      gap: 1rem; margin-bottom: .5rem; flex-wrap: wrap;
  }}
  .mt-doc-head .name {{ font-size: 1.05rem; font-weight: 640; letter-spacing: -.01em; }}
  .mt-doc-head .ref {{
      font-family: {MONO}; font-size: .7rem; font-weight: 700; color: {NAVY};
      letter-spacing: .06em;
  }}

  .mt-refbar {{
      background: #FDF8EC; border: 1px solid #EBD5A3; border-left: 3px solid #B8860B;
      border-radius: 6px; padding: .75rem .9rem; margin-bottom: .8rem;
  }}
  .mt-refbar .eyebrow {{
      font-size: .66rem; font-weight: 700; letter-spacing: .09em; text-transform: uppercase;
      color: #7A5600; margin-bottom: .3rem;
  }}

  .mt-event {{
      border: 1px solid {LINE}; border-left: 3px solid {LINE}; border-radius: 6px;
      padding: .6rem .85rem; margin-bottom: .45rem; background: {SURFACE};
  }}
  .mt-event.is-referenced {{
      border-left-color: #B8860B; background: #FDF8EC; border-color: #EBD5A3;
  }}
  .mt-event .when {{
      font-size: .7rem; font-weight: 700; letter-spacing: .05em; color: {NAVY};
      font-family: {MONO};
  }}
  .mt-event .what {{ font-size: .88rem; font-weight: 600; margin: .18rem 0; }}
  .mt-event .why {{ font-size: .8rem; color: {MUTED}; line-height: 1.5; }}

  .mt-change li {{ margin-bottom: .3rem; }}

  section[data-testid="stSidebar"] {{ background: {CANVAS}; border-right: 1px solid {LINE}; }}
  section[data-testid="stSidebar"] .block-container {{ padding-top: 1.5rem; }}
  div[data-testid="stExpander"] details {{ border: 1px solid {LINE}; border-radius: 6px; }}
  .stButton button {{ border-radius: 6px; font-weight: 560; font-size: .85rem; }}
  div[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 8px; }}
</style>
"""


def status_pill(status: str) -> str:
    style = STATUS_STYLES.get(status, STATUS_STYLES[AssuranceStatus.UNSUPPORTED.value])
    return (
        f"<span class='mt-pill' style='color:{style['fg']};background:{style['bg']};"
        f"border-color:{style['bd']}'>{style['label']}</span>"
    )


def recommendation_style(state: str) -> dict:
    return RECOMMENDATION_STYLES.get(
        state, RECOMMENDATION_STYLES["REQUEST_ADDITIONAL_INFORMATION"]
    )


def concern_pill(level: str) -> str:
    style = CONCERN_STYLES.get(level, CONCERN_STYLES["MODERATE"])
    label = "No concern identified" if level == "NONE" else f"{level.title()} concern"
    return (
        f"<span class='mt-pill' style='color:{style['fg']};background:{style['bg']};"
        f"border-color:{style['bd']}'>{label}</span>"
    )


def severity_pill(severity: str) -> str:
    style = SEVERITY_STYLES.get(severity, SEVERITY_STYLES["informational"])
    return (
        f"<span class='mt-pill' style='color:{style['fg']};background:{style['bg']};"
        f"border-color:{style['bd']}'>{severity.title()}</span>"
    )
