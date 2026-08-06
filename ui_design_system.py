from __future__ import annotations

from html import escape
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st


def apply_design_system() -> None:
    st.markdown(
        """
        <style>
        :root {
          --momo-space-1: .25rem;
          --momo-space-2: .5rem;
          --momo-space-3: .75rem;
          --momo-space-4: 1rem;
          --momo-space-5: 1.5rem;
          --momo-radius-sm: .55rem;
          --momo-radius-md: .85rem;
          --momo-radius-lg: 1.1rem;
          --momo-border: rgba(148,163,184,.24);
          --momo-surface: rgba(15,23,42,.42);
          --momo-surface-strong: rgba(15,23,42,.68);
          --momo-muted: rgba(226,232,240,.72);
          --momo-shadow: 0 8px 28px rgba(2,6,23,.16);
        }
        .block-container {padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1600px;}
        h1,h2,h3,h4 {letter-spacing: -.02em;}
        hr {border-color: var(--momo-border) !important;}

        /* Cards and containers */
        [data-testid="stMetric"], [data-testid="stAlert"],
        [data-testid="stExpander"], [data-testid="stForm"] {
          border: 1px solid var(--momo-border);
          border-radius: var(--momo-radius-md);
          box-shadow: var(--momo-shadow);
          background: var(--momo-surface);
        }
        [data-testid="stMetric"] {padding: .8rem .9rem; min-height: 96px;}
        [data-testid="stMetricLabel"] {font-size: .78rem; opacity: .76;}
        [data-testid="stMetricValue"] {font-size: clamp(1.15rem,2vw,1.85rem) !important;}

        /* Buttons: consistent hierarchy */
        .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
          border-radius: var(--momo-radius-sm) !important;
          min-height: 2.45rem;
          padding: .48rem .85rem;
          font-weight: 650;
          border: 1px solid var(--momo-border);
          transition: transform .12s ease, border-color .12s ease, filter .12s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover {transform: translateY(-1px); filter: brightness(1.06);}
        button[kind="primary"] {box-shadow: 0 6px 18px rgba(239,68,68,.2);}

        /* Navigation and tabs */
        [data-testid="stTabs"] [role="tablist"] {gap: .35rem; flex-wrap: wrap;}
        [data-testid="stTabs"] [role="tab"] {
          border: 1px solid var(--momo-border);
          border-radius: var(--momo-radius-sm);
          padding: .42rem .7rem;
          min-height: 2.35rem;
        }
        [data-testid="stTabs"] [aria-selected="true"] {background: rgba(239,68,68,.14);}

        /* Tables */
        [data-testid="stDataFrame"] {
          border: 1px solid var(--momo-border);
          border-radius: var(--momo-radius-md);
          overflow: auto !important;
          box-shadow: var(--momo-shadow);
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
          position: sticky !important; top: 0; z-index: 5;
          background: var(--momo-surface-strong) !important;
          font-weight: 700 !important;
        }
        [data-testid="stDataFrame"] [role="row"]:nth-child(even) {
          background: rgba(148,163,184,.035);
        }
        [data-testid="stDataFrame"] [role="gridcell"],
        [data-testid="stDataFrame"] [role="columnheader"] {
          line-height: 1.25 !important;
          padding-top: .38rem !important; padding-bottom: .38rem !important;
        }

        /* Inputs */
        [data-baseweb="input"] > div, [data-baseweb="select"] > div,
        [data-baseweb="textarea"] textarea {
          border-radius: var(--momo-radius-sm) !important;
          border-color: var(--momo-border) !important;
        }

        /* Reusable custom components */
        .momo-card {border:1px solid var(--momo-border); border-radius:var(--momo-radius-md);
          padding:1rem; background:var(--momo-surface); box-shadow:var(--momo-shadow); margin:.45rem 0 .8rem;}
        .momo-card-title {font-weight:750; font-size:1rem; margin-bottom:.3rem;}
        .momo-card-subtitle {color:var(--momo-muted); font-size:.83rem; line-height:1.45;}
        .momo-empty {border:1px dashed rgba(148,163,184,.38); border-radius:var(--momo-radius-md);
          padding:1.15rem; text-align:center; background:rgba(15,23,42,.22); margin:.5rem 0;}
        .momo-empty-icon {font-size:1.6rem; margin-bottom:.35rem;}
        .momo-coach-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:.7rem; margin:.55rem 0 1rem;}
        .momo-coach-card {border:1px solid var(--momo-border); border-radius:var(--momo-radius-md);
          padding:.85rem .9rem; background:var(--momo-surface); min-width:0;}
        .momo-coach-label {font-size:.73rem; text-transform:uppercase; letter-spacing:.05em; opacity:.68; margin-bottom:.28rem;}
        .momo-coach-value {font-weight:700; line-height:1.35; overflow-wrap:anywhere;}

        /* Responsive priorities */
        @media (max-width: 900px) {
          .block-container {padding-left:.8rem; padding-right:.8rem;}
          [data-testid="stHorizontalBlock"] {gap:.55rem;}
          [data-testid="column"] {min-width: 100% !important; width:100% !important; flex:1 1 100% !important;}
          [data-testid="stMetric"] {min-height:82px;}
          [data-testid="stDataFrame"] {max-height:72vh;}
        }
        @media (max-width: 620px) {
          .momo-coach-grid {grid-template-columns:1fr;}
          [data-testid="stTabs"] [role="tab"] {font-size:.82rem; padding:.36rem .52rem;}
          .stButton > button {width:100%;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, message: str, icon: str = "📭") -> None:
    st.markdown(
        f'<div class="momo-empty"><div class="momo-empty-icon">{escape(icon)}</div>'
        f'<div class="momo-card-title">{escape(title)}</div>'
        f'<div class="momo-card-subtitle">{escape(message)}</div></div>',
        unsafe_allow_html=True,
    )


def build_reconstruction_coach(reconstruction: Mapping[str, Any]) -> dict[str, str]:
    grade = str(reconstruction.get("objective_entry_grade") or "—")
    score = float(reconstruction.get("objective_entry_score") or 0)
    setup = str(reconstruction.get("likely_setup") or "Unclassified setup")
    confidence = float(reconstruction.get("setup_confidence") or 0)
    daily = reconstruction.get("daily_context") or {}
    intraday = reconstruction.get("intraday_execution_context") or {}
    distance = daily.get("distance_from_ema21_pct")
    rvol = intraday.get("rvol", daily.get("rvol"))
    strengths = []
    cautions = []
    if score >= 85: strengths.append("Entry aligned well with the reconstructed setup conditions.")
    elif score >= 70: strengths.append("Entry had a workable technical foundation.")
    else: cautions.append("Entry quality was below the preferred A-range threshold.")
    if distance is not None and abs(float(distance)) <= 3: strengths.append("Price was close to EMA21 rather than extended.")
    elif distance is not None: cautions.append("Price location was extended from EMA21 at entry.")
    if rvol is not None and float(rvol) >= 1.0: strengths.append("Relative volume supported the move.")
    elif rvol is not None: cautions.append("Volume confirmation was limited.")
    return {
        "Verdict": f"{grade} reconstructed entry · {score:.0f}/100",
        "Setup Read": f"{setup} ({confidence:.0f}% confidence)",
        "What Worked": strengths[0] if strengths else "The reconstruction did not identify a dominant strength.",
        "Coach Focus": cautions[0] if cautions else "Preserve the same entry discipline and verify the plan before execution.",
    }


def render_coach_summary(summary: Mapping[str, str]) -> None:
    cards = "".join(
        f'<div class="momo-coach-card"><div class="momo-coach-label">{escape(str(label))}</div>'
        f'<div class="momo-coach-value">{escape(str(value))}</div></div>'
        for label, value in summary.items()
    )
    st.markdown(f'<div class="momo-coach-grid">{cards}</div>', unsafe_allow_html=True)


def render_chart_thumbnail(points: Sequence[Mapping[str, Any]] | None, title: str = "Historical chart snapshot") -> None:
    if not points:
        render_empty_state(title, "A chart thumbnail will appear after historical reconstruction is generated.", "📈")
        return
    frame = pd.DataFrame(points)
    if frame.empty or "close" not in frame.columns:
        render_empty_state(title, "The saved reconstruction does not contain chart points.", "📈")
        return
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
        frame = frame.dropna(subset=["timestamp"]).set_index("timestamp")
    st.caption(title)
    st.line_chart(frame[["close"]], height=190, width="stretch")
