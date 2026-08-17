from __future__ import annotations

import html
import json
import os
import secrets
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.energy_agent import AgentResponse, QUICK_PROMPTS
from src.openai_energy_agent import (
    ALLOWED_EFFORTS,
    ALLOWED_MODELS,
    answer_energy_question_hybrid,
    test_openai_connection,
)
from src.client_onboarding import FIELD_LIBRARY, build_mapping_template, parse_client_file
from src.cloud_document_recognition import CLOUD_EXTENSIONS, recognise_document
from src.client_project import assess_client_project, build_client_deliverable


PROJECT_ROOT = APP_DIR
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CONFIG_DIR = PROJECT_ROOT / "data" / "config"
RESULTS_DIR = PROJECT_ROOT / "results"

COLORS = {
    "cyan": "#43D9FF",
    "blue": "#4C7DFF",
    "green": "#53E6A5",
    "amber": "#FFBE55",
    "red": "#FF6B7A",
    "violet": "#A98BFF",
    "ink": "#07111F",
    "panel": "#0D1B2B",
    "muted": "#8EA3B7",
    "text": "#EAF2F8",
    "grid": "rgba(142,163,183,.14)",
}

st.set_page_config(
    page_title="Irene Energy Command Center",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root {
        --bg: #07111f;
        --panel: rgba(13, 27, 43, .88);
        --panel-strong: #0d1b2b;
        --line: rgba(126, 165, 196, .16);
        --line-strong: rgba(67, 217, 255, .30);
        --text: #eaf2f8;
        --muted: #8ea3b7;
        --cyan: #43d9ff;
        --blue: #4c7dff;
        --green: #53e6a5;
        --amber: #ffbe55;
        --red: #ff6b7a;
      }

      html, body, [class*="css"] {font-family: Inter, "Segoe UI", sans-serif;}
      .stApp {
        background:
          radial-gradient(circle at 80% -10%, rgba(31, 106, 164, .24), transparent 34rem),
          radial-gradient(circle at 8% 20%, rgba(20, 122, 132, .13), transparent 28rem),
          #07111f;
        color: var(--text);
      }
      .block-container {max-width: 1520px; padding: 1.25rem 2.1rem 2.5rem;}
      header[data-testid="stHeader"] {background: transparent;}
      #MainMenu, footer, .stAppDeployButton {visibility: hidden;}

      section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #091522 0%, #07111f 100%);
        border-right: 1px solid var(--line);
      }
      section[data-testid="stSidebar"] > div {padding-top: .7rem;}
      section[data-testid="stSidebar"] [data-testid="stRadio"] > label {
        color: #667d92; font-size: .66rem; letter-spacing: .16em; text-transform: uppercase;
      }
      section[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {gap: .35rem;}
      section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] {
        min-height: 2.9rem; padding: .74rem .85rem; border-radius: .75rem;
        border: 1px solid transparent; transition: all .18s ease;
      }
      section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        background: rgba(67, 217, 255, .055); border-color: rgba(67, 217, 255, .12);
      }
      section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background: linear-gradient(90deg, rgba(67,217,255,.14), rgba(76,125,255,.06));
        border-color: rgba(67,217,255,.26); box-shadow: inset 3px 0 0 var(--cyan);
      }
      section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {display:none;}
      section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] p {
        color: #c9d8e4; font-size: .86rem; font-weight: 600;
      }

      .side-brand {padding: .55rem .35rem 1.1rem;}
      .brand-mark {
        display: inline-grid; place-items: center; width: 2.45rem; height: 2.45rem;
        border: 1px solid rgba(67,217,255,.48); border-radius: .72rem; color: var(--cyan);
        background: rgba(67,217,255,.07); font-weight: 800; margin-bottom: .8rem;
      }
      .side-brand h2 {font-size: 1rem; letter-spacing: .02em; margin: 0; color: #f5fbff;}
      .side-brand p {font-size: .71rem; line-height: 1.55; color: var(--muted); margin: .35rem 0 0;}
      .side-divider {height: 1px; background: var(--line); margin: .25rem .35rem 1rem;}
      .side-label {font-size: .64rem; color: #667d92; text-transform: uppercase; letter-spacing: .16em; margin: 1.1rem .35rem .55rem;}
      .side-fact {display:flex; justify-content:space-between; gap:.7rem; padding:.42rem .35rem; font-size:.72rem; color:var(--muted);}
      .side-fact strong {color:#dce8f1; font-weight:600; text-align:right;}
      .status-row {display:flex; align-items:center; gap:.5rem; margin:.65rem .35rem; color:#a9bdcc; font-size:.7rem;}
      .status-dot {width:.47rem; height:.47rem; border-radius:50%; background:var(--green); box-shadow:0 0 12px rgba(83,230,165,.75);}

      .hero {
        position: relative; overflow: hidden; min-height: 14.5rem; padding: 2rem 2.15rem;
        display: flex; flex-direction: column; justify-content: center;
        border: 1px solid rgba(100, 173, 218, .22); border-radius: 1.2rem;
        background:
          linear-gradient(105deg, rgba(9,25,41,.98) 0%, rgba(9,29,48,.94) 55%, rgba(8,38,55,.82) 100%);
        box-shadow: 0 22px 70px rgba(0,0,0,.24);
        margin-bottom: 1.3rem;
      }
      .hero::before {
        content:""; position:absolute; inset:-40% -12% auto auto; width:34rem; height:34rem; border-radius:50%;
        background:radial-gradient(circle, rgba(67,217,255,.15), transparent 64%);
      }
      .hero::after {
        content:""; position:absolute; right:2.5rem; top:2rem; width:11rem; height:11rem; opacity:.2;
        background-image: linear-gradient(rgba(67,217,255,.3) 1px, transparent 1px), linear-gradient(90deg, rgba(67,217,255,.3) 1px, transparent 1px);
        background-size: 18px 18px; transform: perspective(240px) rotateY(-20deg) rotateX(13deg);
        mask-image: linear-gradient(135deg, #000, transparent 78%);
      }
      .hero-kicker {color:var(--cyan); font-size:.68rem; font-weight:700; letter-spacing:.18em; text-transform:uppercase; position:relative; z-index:1;}
      .hero h1 {max-width: 57rem; margin:.7rem 0 .55rem; color:#f4f9fd; font-size:clamp(1.8rem,3.15vw,3.25rem); line-height:1.08; letter-spacing:-.04em; position:relative; z-index:1;}
      .hero-sub {max-width:50rem; color:#9fb2c2; font-size:.88rem; line-height:1.75; position:relative; z-index:1;}
      .hero-chips {display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.2rem; position:relative; z-index:1;}
      .chip {display:inline-flex; align-items:center; gap:.4rem; padding:.42rem .67rem; border:1px solid var(--line); border-radius:999px; background:rgba(255,255,255,.025); color:#b9cbd9; font-size:.67rem;}
      .chip i {width:.35rem;height:.35rem;border-radius:50%;background:var(--cyan);box-shadow:0 0 8px rgba(67,217,255,.7);}
      .chip.success i {background:var(--green);box-shadow:0 0 8px rgba(83,230,165,.7);}

      .page-head {display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; margin:1.6rem 0 1rem;}
      .page-head .eyebrow, .section-eyebrow {font-size:.62rem; text-transform:uppercase; letter-spacing:.16em; color:var(--cyan); font-weight:700;}
      .page-head h2 {font-size:1.55rem; line-height:1.25; margin:.34rem 0 .2rem; color:#f2f7fb; letter-spacing:-.025em;}
      .page-head p {max-width:50rem; margin:0; color:var(--muted); font-size:.78rem; line-height:1.65;}
      .page-code {color:#547187;font-size:.68rem;border:1px solid var(--line);border-radius:999px;padding:.38rem .66rem;white-space:nowrap;}

      .metric-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.85rem;margin:.6rem 0 1.15rem;}
      .metric-card {
        position:relative; min-height:8.2rem; padding:1.05rem 1.1rem; overflow:hidden;
        border:1px solid var(--line); border-radius:.95rem;
        background:linear-gradient(145deg, rgba(16,35,54,.92), rgba(10,24,39,.86));
        box-shadow:0 12px 35px rgba(0,0,0,.13);
      }
      .metric-card::after {content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:linear-gradient(90deg,var(--accent),transparent 70%);opacity:.8;}
      .metric-label {color:#88a0b3;font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;}
      .metric-value {margin:.62rem 0 .28rem;color:#f6fbff;font-size:1.7rem;font-weight:720;letter-spacing:-.04em;line-height:1;}
      .metric-value small {font-size:.65rem;font-weight:600;color:#a9bdcc;letter-spacing:0;margin-left:.2rem;}
      .metric-note {color:#7890a4;font-size:.66rem;line-height:1.45;}

      .evidence-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;margin:.2rem 0 1.2rem;}
      .evidence-item {padding:.8rem .85rem;border:1px solid var(--line);border-radius:.78rem;background:rgba(11,25,40,.62);}
      .evidence-item .tag {display:inline-flex;align-items:center;gap:.35rem;color:#d8e6ef;font-size:.68rem;font-weight:650;}
      .evidence-item .tag::before {content:"";width:.42rem;height:.42rem;border-radius:50%;background:var(--dot);box-shadow:0 0 9px color-mix(in srgb,var(--dot) 65%,transparent);}
      .evidence-item p {margin:.4rem 0 0;color:#7890a4;font-size:.64rem;line-height:1.45;}

      .notice {border:1px solid var(--notice-line);border-left:3px solid var(--notice);border-radius:.75rem;background:var(--notice-bg);padding:.85rem 1rem;margin:.7rem 0 1rem;color:#b9cbd9;font-size:.73rem;line-height:1.65;}
      .notice strong {color:#ecf5fb;}
      .notice.info {--notice:var(--cyan);--notice-line:rgba(67,217,255,.18);--notice-bg:rgba(67,217,255,.045);}
      .notice.warn {--notice:var(--amber);--notice-line:rgba(255,190,85,.20);--notice-bg:rgba(255,190,85,.045);}
      .notice.danger {--notice:var(--red);--notice-line:rgba(255,107,122,.20);--notice-bg:rgba(255,107,122,.045);}
      .notice.success {--notice:var(--green);--notice-line:rgba(83,230,165,.20);--notice-bg:rgba(83,230,165,.045);}

      .section-title {margin:1.35rem 0 .7rem;}
      .section-title h3 {margin:.28rem 0 0;color:#eaf2f8;font-size:1.02rem;letter-spacing:-.01em;}
      .decision-card {height:100%;min-height:26.3rem;padding:1.1rem 1.15rem;border:1px solid var(--line);border-radius:.95rem;background:linear-gradient(155deg,rgba(16,35,54,.92),rgba(8,23,37,.94));}
      .decision-card h3 {font-size:.92rem;margin:0 0 .25rem;color:#ecf5fb;}
      .decision-card > p {color:#7890a4;font-size:.66rem;margin:0 0 1rem;}
      .decision-row {display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;padding:.85rem 0;border-top:1px solid var(--line);}
      .decision-row span {color:#8098aa;font-size:.67rem;}
      .decision-row strong {color:#f3f9fd;font-size:1.02rem;text-align:right;}
      .decision-row strong em {display:block;color:var(--green);font-size:.62rem;font-style:normal;font-weight:600;margin-top:.2rem;}

      div[data-testid="stPlotlyChart"], div[data-testid="stDataFrame"] {
        border:1px solid var(--line); border-radius:.95rem; overflow:hidden; background:rgba(9,22,36,.58);
      }
      div[data-testid="stPlotlyChart"] {padding:.25rem;}
      div[data-testid="stDataFrame"] {padding:.18rem;}
      div[data-testid="stExpander"] {border-color:var(--line);background:rgba(10,23,37,.56);border-radius:.8rem;}
      button[data-baseweb="tab"] {color:#8fa7b8;font-size:.75rem;}
      button[data-baseweb="tab"][aria-selected="true"] {color:#eaf5fb;}
      [data-testid="stSelectbox"] label, [data-testid="stDateInput"] label {color:#8299aa;font-size:.72rem;}
      div[data-baseweb="select"] > div, [data-baseweb="input"] {background-color:#0c1b2a;border-color:var(--line);}

      .scenario-panel {padding:1rem 1.05rem;border:1px solid var(--line);border-radius:.9rem;background:linear-gradient(145deg,rgba(15,33,51,.92),rgba(9,23,37,.84));margin:.25rem 0 1rem;}
      .scenario-panel .status {color:var(--amber);font-size:.62rem;text-transform:uppercase;letter-spacing:.13em;font-weight:700;}
      .scenario-panel h4 {color:#edf6fc;font-size:1rem;margin:.45rem 0 .35rem;}
      .scenario-panel p {color:#8299aa;font-size:.7rem;line-height:1.55;margin:0;}

      .twin-flow {display:grid;grid-template-columns:1.25fr .8fr .9fr 1.15fr;gap:1.1rem;align-items:center;margin:.5rem 0 1.2rem;}
      .twin-node {position:relative;min-height:7.2rem;padding:.95rem;border:1px solid var(--line);border-radius:.85rem;background:linear-gradient(145deg,rgba(16,34,53,.92),rgba(9,23,37,.9));}
      .twin-node:not(:last-child)::after {content:"→";position:absolute;right:-.82rem;top:42%;color:#54758b;font-size:1rem;}
      .twin-node .level {color:var(--cyan);font-size:.57rem;text-transform:uppercase;letter-spacing:.14em;}
      .twin-node h4 {color:#edf6fb;font-size:.82rem;margin:.4rem 0;}
      .twin-node p {color:#7890a4;font-size:.62rem;line-height:1.45;margin:0;}
      .twin-node .evidence {position:absolute;left:.9rem;bottom:.75rem;font-size:.57rem;color:var(--green);}
      .request-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.75rem;margin:.4rem 0 1rem;}
      .request-card {padding:1rem;border:1px solid var(--line);border-radius:.85rem;background:rgba(12,27,43,.75);}
      .request-card .priority {font-size:.58rem;color:var(--amber);letter-spacing:.13em;text-transform:uppercase;}
      .request-card h4 {font-size:.8rem;color:#e8f2f8;margin:.45rem 0 .35rem;}
      .request-card p {font-size:.63rem;color:#7d95a8;line-height:1.5;margin:0;}

      .agent-status {
        display:flex;align-items:center;justify-content:space-between;gap:1rem;margin:.25rem 0 1rem;
        padding:.9rem 1rem;border:1px solid rgba(83,230,165,.22);border-radius:.85rem;
        background:linear-gradient(100deg,rgba(83,230,165,.055),rgba(67,217,255,.035));
      }
      .agent-status > div {display:flex;align-items:center;gap:.65rem;color:#d9e9f2;font-size:.72rem;font-weight:650;}
      .agent-status i {width:.52rem;height:.52rem;border-radius:50%;background:var(--green);box-shadow:0 0 13px rgba(83,230,165,.85);}
      .agent-status span {color:#718da1;font-size:.62rem;text-align:right;}
      .agent-engine-note {margin:.35rem 0 .9rem;padding:.72rem .85rem;border:1px solid rgba(67,217,255,.14);border-radius:.72rem;background:rgba(67,217,255,.035);color:#7894a8;font-size:.62rem;line-height:1.55;}
      .agent-engine-note b {color:var(--cyan);}
      .agent-welcome {padding:.9rem 1rem;border:1px solid var(--line);border-radius:.85rem;background:rgba(12,28,44,.7);color:#a9bdcc;font-size:.72rem;line-height:1.7;}
      .agent-trace {margin-top:.75rem;padding:.85rem;border:1px solid rgba(67,217,255,.15);border-radius:.72rem;background:rgba(4,15,26,.5);}
      .agent-trace-head {display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:.65rem;}
      .agent-pill {padding:.27rem .45rem;border:1px solid var(--line);border-radius:999px;color:#87a3b6;font-size:.56rem;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;}
      .agent-pill.tool {color:var(--cyan);border-color:rgba(67,217,255,.22);background:rgba(67,217,255,.05);}
      .agent-pill.evidence {color:var(--green);border-color:rgba(83,230,165,.2);background:rgba(83,230,165,.045);}
      .agent-trace h5 {margin:.45rem 0 .25rem;color:#dceaf2;font-size:.66rem;}
      .agent-trace p,.agent-trace li {color:#7892a5;font-size:.62rem;line-height:1.55;}
      .agent-trace ul {margin:.25rem 0 .45rem;padding-left:1.05rem;}
      .agent-plan {display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin:.6rem 0;}
      .agent-plan > div {padding:.7rem;border:1px solid var(--line);border-radius:.65rem;background:rgba(11,27,43,.58);}
      .agent-plan ol,.agent-plan ul {margin:.35rem 0 0;padding-left:1.05rem;}
      .agent-plan .calc li {color:#a7c8d9;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;}
      .agent-mode {display:flex;justify-content:space-between;gap:.8rem;padding-top:.55rem;border-top:1px solid var(--line);color:#5f7c91;font-size:.56rem;}
      .agent-mode b {color:var(--cyan);font-weight:600;}
      .agent-confidence {color:var(--amber)!important;margin:.55rem 0 0!important;}
      div[data-testid="stChatMessage"] {border:1px solid var(--line);border-radius:.95rem;background:rgba(10,24,39,.62);padding:.35rem .55rem;margin:.45rem 0;}
      div[data-testid="stChatMessage"] p {font-size:.75rem;line-height:1.72;}
      div[data-testid="stChatInput"] {border-color:rgba(67,217,255,.24);background:#0b1a29;}
      .agent-quick-label {margin:1rem 0 .35rem;color:#678196;font-size:.61rem;text-transform:uppercase;letter-spacing:.14em;}

      .app-footer {display:flex;justify-content:space-between;gap:1rem;border-top:1px solid var(--line);margin-top:2rem;padding-top:1rem;color:#5f788d;font-size:.62rem;}

      @media (max-width: 1100px) {
        .metric-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
        .evidence-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
        .request-grid {grid-template-columns:1fr 1fr;}
      }
      @media (max-width: 720px) {
        .block-container {padding: .85rem .8rem 1.6rem;}
        .hero {padding:1.4rem 1.15rem;min-height:13rem;}
        .hero::after {display:none;}
        .metric-grid,.evidence-grid,.request-grid {grid-template-columns:1fr;}
        .metric-card {min-height:7.4rem;}
        .page-head {align-items:flex-start;flex-direction:column;}
        .twin-flow {grid-template-columns:1fr;}
        .twin-node:not(:last-child)::after {content:"↓";right:50%;top:auto;bottom:-1rem;}
        .app-footer {flex-direction:column;}
        .agent-plan {grid-template-columns:1fr;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_data() -> dict:
    files = {
        "monthly": PROCESSED_DIR / "monthly_meter_clean.csv",
        "monthly_totals": PROCESSED_DIR / "monthly_totals.csv",
        "meter_summary": PROCESSED_DIR / "meter_summary.csv",
        "hourly": PROCESSED_DIR / "db_hourly_estimated.csv",
        "reconciliation": PROCESSED_DIR / "hourly_monthly_reconciliation.csv",
        "quality": PROCESSED_DIR / "data_quality_flags.csv",
        "scenario": RESULTS_DIR / "scenario_summary.csv",
        "loss_metrics": RESULTS_DIR / "loss_aware_metrics.csv",
        "loss_detail": RESULTS_DIR / "loss_aware_hourly_detail.csv",
        "pv_monthly": PROCESSED_DIR / "db_pv_monthly_measured.csv",
        "pv_hourly": RESULTS_DIR / "target_pv_profile.csv",
        "digital_twin": CONFIG_DIR / "digital_twin_dictionary.csv",
        "data_request": CONFIG_DIR / "data_request_tracker.csv",
        "model_readiness": CONFIG_DIR / "model_readiness_register.csv",
        "lineage": CONFIG_DIR / "source_lineage.csv",
    }
    missing = [str(path) for path in files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Required public data files are missing:\n" + "\n".join(missing))

    loaded = {name: pd.read_csv(path) for name, path in files.items()}
    loaded["hourly"]["timestamp"] = pd.to_datetime(loaded["hourly"]["timestamp"])
    loaded["loss_detail"]["timestamp"] = pd.to_datetime(loaded["loss_detail"]["timestamp"])
    loaded["summary"] = load_json(RESULTS_DIR / "project_summary.json")
    loaded["assumptions"] = load_json(CONFIG_DIR / "project_assumptions.json")
    loaded["model_metrics"] = load_json(RESULTS_DIR / "donor_profile_model_metrics.json")
    validation_path = RESULTS_DIR / "run_validation.json"
    loaded["validation"] = load_json(validation_path) if validation_path.exists() else {}
    return loaded


def safe(value: object) -> str:
    return html.escape(str(value))


def page_header(number: str, title: str, subtitle: str, code: str) -> None:
    st.markdown(
        f"""
        <div class="page-head">
          <div>
            <div class="eyebrow">Module {safe(number)}</div>
            <h2>{safe(title)}</h2>
            <p>{safe(subtitle)}</p>
          </div>
          <div class="page-code">{safe(code)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(eyebrow: str, title: str) -> None:
    st.markdown(
        f'<div class="section-title"><div class="section-eyebrow">{safe(eyebrow)}</div><h3>{safe(title)}</h3></div>',
        unsafe_allow_html=True,
    )


def render_metric_grid(items: list[dict]) -> None:
    cards = []
    for item in items:
        cards.append(
            f"""
            <div class="metric-card" style="--accent:{safe(item.get('color', COLORS['cyan']))}">
              <div class="metric-label">{safe(item['label'])}</div>
              <div class="metric-value">{safe(item['value'])}<small>{safe(item.get('unit', ''))}</small></div>
              <div class="metric-note">{safe(item.get('note', ''))}</div>
            </div>
            """
        )
    st.html('<div class="metric-grid">' + "".join(cards) + "</div>")


def render_notice(kind: str, title: str, body: str) -> None:
    st.markdown(
        f'<div class="notice {safe(kind)}"><strong>{safe(title)}</strong>　{safe(body)}</div>',
        unsafe_allow_html=True,
    )


def style_figure(fig: go.Figure, title: str | None = None, height: int = 390) -> go.Figure:
    fig.update_layout(
        title={"text": title or "", "x": 0.035, "xanchor": "left", "font": {"size": 15, "color": COLORS["text"]}},
        height=height,
        margin={"l": 48, "r": 24, "t": 62 if title else 30, "b": 45},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,21,34,.54)",
        font={"family": "Inter, Segoe UI, sans-serif", "size": 11, "color": COLORS["muted"]},
        hoverlabel={"bgcolor": "#102438", "bordercolor": "#33536C", "font": {"color": "#F1F8FC"}},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "right", "x": 1, "font": {"size": 10}},
        bargap=.28,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=COLORS["grid"], tickfont={"color": COLORS["muted"]})
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False, linecolor=COLORS["grid"], tickfont={"color": COLORS["muted"]})
    return fig


try:
    data = load_data()
except FileNotFoundError as error:
    st.error(str(error))
    st.stop()

summary = data["summary"]
validation = data["validation"]
combo = data["scenario"].query("scenario_id == 'combo_package'").iloc[0]
loss_aware = data["loss_metrics"].query("strategy_id == 'loss_aware_lp'").iloc[0]
naive = data["loss_metrics"].query("strategy_id == 'naive_grid_charge'").iloc[0]
current_pv = data["loss_metrics"].query("strategy_id == 'no_battery'").iloc[0]
checks_pass = bool(validation) and all(
    [
        validation.get("annual_total_matches_expected", False),
        validation.get("hourly_monthly_reconciliation_failures", 1) == 0,
        validation.get("lp_success", False),
    ]
)

with st.sidebar:
    st.markdown(
        f"""
        <div class="side-brand">
          <div class="brand-mark">IR</div>
          <h2>NEXUS ENERGY OS</h2>
          <p>Evidence-led digital twin<br>T1 — AI for Clean Energy<br>Team EnerGen AI · Project Irene</p>
        </div>
        <div class="side-divider"></div>
        """,
        unsafe_allow_html=True,
    )
    page = st.radio(
        "Command modules",
        [
            "01  Project Overview",
            "02  Monthly Evidence",
            "03  Hourly Evidence",
            "04  Efficiency & ROI",
            "05  PV & Future Storage",
            "06  Twin & Data",
            "07  Analysis Agent",
            "08  Client Data Onboarding",
        ],
        label_visibility="visible",
    )
    st.markdown(
        f"""
        <div class="side-label">Confirmed facts</div>
        <div class="side-fact"><span>Building</span><strong>Ningbo Reference</strong></div>
        <div class="side-fact"><span>Gross area</span><strong>{summary['real_case']['gross_floor_area_m2']:,.2f} m²</strong></div>
        <div class="side-fact"><span>Floors</span><strong>{summary['real_case']['floor_count']}</strong></div>
        <div class="side-fact"><span>Ningbo tariff</span><strong>kWh × {summary['tariff']['value']:.3f} CNY</strong></div>
        <div class="side-fact"><span>Opening</span><strong>08:00-22:00</strong></div>
        <div class="side-fact"><span>Installed PV</span><strong>106.14 kWp</strong></div>
        <div class="side-fact"><span>Storage</span><strong>None installed</strong></div>
        <div class="side-label">Model health</div>
        <div class="status-row"><span class="status-dot"></span>{'Integrity checks passed' if checks_pass else 'Review integrity output'}</div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <div class="hero">
      <div class="hero-kicker">MAIC NEXUS CHALLENGE 2026 · T1 — AI FOR CLEAN ENERGY</div>
      <h1>AI-assisted Digital Twin<br>Energy Command Center</h1>
      <div class="hero-sub">Using an anonymized Ningbo reference case, the platform connects approved aggregate evidence, synthetic public demo profiles, auditable hourly estimates and loss-aware optimisation into one traceable decision chain.</div>
      <div class="hero-chips">
        <span class="chip"><i></i> Reference case · Ningbo</span>
        <span class="chip"><i></i> Malaysia local pilot · pending</span>
        <span class="chip success"><i></i> {'Internal checks pass' if checks_pass else 'Integrity review available'}</span>
        <span class="chip"><i></i> Irene auditable model</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if page == "01  Project Overview":
    page_header("01", "Project Overview", "T1 clean-energy decision support from approved aggregate evidence to investment-screening results, with a governed path from client files to verified savings.", "T1 · AI FOR CLEAN ENERGY")
    render_notice("info", "Malaysia deployment pathway", "Validated on a Ningbo reference case; designed for configurable deployment in Malaysia, pending local pilot validation.")
    render_metric_grid(
        [
            {"label": "Annual electricity", "value": f"{summary['annual_total_kwh'] / 1000:,.1f}", "unit": "MWh", "note": "Total from four meters over 12 months", "color": COLORS["cyan"]},
            {"label": "Energy intensity", "value": f"{summary['annual_eui_kwh_m2']:.2f}", "unit": "kWh/m²·year", "note": f"Gross floor area: {summary['real_case']['gross_floor_area_m2']:,.2f} m²", "color": COLORS["blue"]},
            {"label": "HVAC share", "value": f"{summary['hvac_share_pct']:.2f}", "unit": "%", "note": f"HVAC electricity: {summary['annual_hvac_kwh'] / 1000:,.1f} MWh", "color": COLORS["amber"]},
            {"label": "Installed PV", "value": "106.14", "unit": "kWp", "note": f"Approved aggregate generation: {current_pv['pv_generation_kwh']/1000:,.1f} MWh · no storage", "color": COLORS["green"]},
        ]
    )
    st.markdown(
        """
        <div class="evidence-grid">
          <div class="evidence-item" style="--dot:#53e6a5"><div class="tag">AGGREGATE</div><p>Approved monthly energy and generation results for a 106.14 kWp reference PV system</p></div>
          <div class="evidence-item" style="--dot:#43d9ff"><div class="tag">DERIVED</div><p>Monthly-constrained load/PV hourly profiles, EUI and cost</p></div>
          <div class="evidence-item" style="--dot:#ffbe55"><div class="tag">ASSUMED</div><p>Daily 08:00–22:00 opening, comfortable conditions and CAPEX</p></div>
          <div class="evidence-item" style="--dot:#a98bff"><div class="tag">SANDBOX</div><p>Future storage dispatch; the reference case currently has no storage</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.72, 1], gap="large")
    with left:
        totals = data["monthly_totals"].copy()
        totals["month"] = totals["month"].astype(str)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=totals["month"], y=totals["usage_kwh"] / 1000,
                mode="lines+markers", name="Monthly electricity",
                line={"color": COLORS["cyan"], "width": 3},
                marker={"size": 7, "color": COLORS["cyan"], "line": {"width": 2, "color": "#0B1D2D"}},
                fill="tozeroy", fillcolor="rgba(67,217,255,.08)",
                hovertemplate="%{x}<br><b>%{y:,.2f} MWh</b><extra></extra>",
            )
        )
        fig.add_vline(x="2024-10", line_dash="dot", line_color=COLORS["red"], line_width=1.5)
        fig.add_annotation(x="2024-10", y=float(totals["usage_kwh"].max() / 1000), text="Data-quality event", showarrow=True, arrowcolor=COLORS["red"], font={"color": COLORS["red"], "size": 10}, bgcolor="rgba(18,27,40,.88)")
        fig.update_yaxes(title="MWh / month")
        st.plotly_chart(style_figure(fig, "Reference Monthly Electricity Profile · July 2024–June 2025", 420), width="stretch", config={"displayModeBar": False})
    with right:
        st.markdown(
            f"""
            <div class="decision-card">
              <h3>Decision snapshot</h3><p>Current screening result · awaiting site data and supplier quotations</p>
              <div class="decision-row"><span>Combined package P50 savings</span><strong>{combo['annual_saved_kwh_p50']/1000:,.1f} MWh<em>{combo['saving_rate_pct_p50']:.2f}% of baseline</em></strong></div>
              <div class="decision-row"><span>Annual cost savings</span><strong>CNY {combo['annual_saving_cny_p50']/1000:,.1f}k<em>Ningbo tariff · CNY 0.538/kWh</em></strong></div>
              <div class="decision-row"><span>Simple payback</span><strong>{combo['simple_payback_years_p50']:.2f} years<em>CAPEX is assumed</em></strong></div>
              <div class="decision-row"><span>Parameterized Malaysia carbon scenario</span><strong>{combo['avoided_tco2e_maic_p50']:.1f} tCO₂e<em>assumption · not a field result</em></strong></div>
              <div class="decision-row"><span>Loss-aware optimisation</span><strong>-{summary['loss_aware_comparison']['grid_import_reduction_vs_naive_pct']:.2f}%<em>grid import vs rule-based</em></strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Commercial pathway")
    commercial_a, commercial_b, commercial_c = st.columns(3, gap="large")
    with commercial_a:
        st.markdown("**Target customers**\n\nCommercial buildings, campuses, industrial parks and energy service companies (ESCOs).")
        st.markdown("**First paid product**\n\nFile-based energy diagnosis with a confirmed baseline, auditable report and action shortlist.")
    with commercial_b:
        st.markdown("**Revenue model**\n\nOne-off diagnosis fee, annual subscription, and implementation plus M&V service fees.")
        st.markdown("**Competitive edge**\n\nClient-data intake, confirmation gate, evidence chain, deterministic calculations and privacy-safe delivery.")
    with commercial_c:
        st.markdown("**Pilot path**\n\nFile audit → temporary metering → calibration → savings verification → multi-site scale.")
        st.markdown("**Malaysia policy context**\n\nEECA 2024 is in force; the National Energy Transition Roadmap identifies audits and ESCO delivery as priorities. This is a policy signal, not a market-size claim.")

elif page == "02  Monthly Evidence":
    page_header("02", "Reference Monthly Case", "Break down four generic meter series while retaining the approved aggregate anomaly in a privacy-safe audit view.", "AGGREGATE + SYNTHETIC")
    render_notice("danger", "Aggregate anomaly retained", "The approved October 2024 aggregate is retained as a documented case-study anomaly. Public meter rows and identifiers are deterministic synthetic records; no original meter record is distributed.")

    monthly = data["monthly"].copy()
    pivot = monthly.pivot_table(index="month", columns="meter_name", values="usage_kwh", aggfunc="sum").fillna(0)
    palette = [COLORS["cyan"], COLORS["blue"], COLORS["amber"], COLORS["violet"]]
    fig = go.Figure()
    for index, column in enumerate(pivot.columns):
        fig.add_bar(
            name=column, x=pivot.index.astype(str), y=pivot[column] / 1000,
            marker={"color": palette[index % len(palette)]},
            hovertemplate=f"{safe(column)}<br>%{{x}} · %{{y:,.2f}} MWh<extra></extra>",
        )
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="MWh / month")
    st.plotly_chart(style_figure(fig, "Monthly Electricity by Meter", 440), width="stretch", config={"displayModeBar": False})

    annual_by_meter = data["meter_summary"].sort_values("annual_kwh", ascending=True)
    fig2 = go.Figure(
        go.Bar(
            x=annual_by_meter["annual_kwh"] / 1000,
            y=annual_by_meter["meter_name"], orientation="h",
            marker={"color": [COLORS["blue"] if name in {"MTR-A", "MTR-B"} else COLORS["amber"] for name in annual_by_meter["meter_name"]]},
            text=[f"{value / 1000:,.1f} MWh" for value in annual_by_meter["annual_kwh"]], textposition="outside",
            hovertemplate="%{y}<br><b>%{x:,.2f} MWh</b><extra></extra>",
        )
    )
    fig2.update_xaxes(title="Annual MWh")
    st.plotly_chart(style_figure(fig2, "Annual Meter Contribution", 345), width="stretch", config={"displayModeBar": False})

    meter_tab, quality_tab = st.tabs(["Meter Summary", "Data-Quality Register"])
    with meter_tab:
        st.dataframe(data["meter_summary"], width="stretch", hide_index=True)
    with quality_tab:
        st.dataframe(data["quality"], width="stretch", hide_index=True)

elif page == "03  Hourly Evidence":
    page_header("03", "Hourly Estimate & Evidence", "Expose the sources, validation gate and monthly reconciliation of the 8,760-hour estimate without presenting estimates as measurements.", "AUDITABLE ESTIMATION")
    reference_hours = int((data["hourly"]["weather_evidence"] == "synthetic_reference_weather_2024").sum())
    extension_hours = len(data["hourly"]) - reference_hours
    reconciliation_failures = int((data["reconciliation"]["status"] != "PASS").sum())
    metrics = data["model_metrics"]
    render_metric_grid(
        [
            {"label": "Estimated profile", "value": f"{len(data['hourly']):,}", "unit": "hours", "note": "Monthly-constrained synthetic public profile", "color": COLORS["cyan"]},
            {"label": "Reference weather", "value": f"{reference_hours:,}", "unit": "hours", "note": "Deterministic synthetic reference coverage", "color": COLORS["green"]},
            {"label": "Synthetic extension", "value": f"{extension_hours:,}", "unit": "hours", "note": "Synthetic profile for the remaining period", "color": COLORS["amber"]},
            {"label": "Reconciliation failures", "value": str(reconciliation_failures), "unit": "months", "note": "Hourly totals reconciled to monthly meters", "color": COLORS["green"] if reconciliation_failures == 0 else COLORS["red"]},
        ]
    )
    render_notice(
        "info",
        "Candidate-model performance gate enforced",
        f"The HistGradientBoosting candidate did not outperform the transparent weekend-hour calendar prior and was rejected. The selected method's validation NMAE is {metrics['selected_validation_nmae_pct_of_mean_shape']:.2f}%. The public validation uses deterministic synthetic temporal shapes and does not claim site-hourly accuracy.",
    )
    render_notice(
        "success",
        "Opening hours and comfort conditions locked",
        "Classrooms are assumed open daily from 08:00 to 22:00. During opening, the proxy uses 20–26°C, 40–60% RH and CO₂ ≤ 1,000 ppm. Every open hour passes the constraint, but these indoor values are simulation assumptions, not sensor measurements.",
    )

    range_col, proof_col = st.columns([1.5, 1], gap="large")
    with range_col:
        date_range = st.date_input(
            "Displayed period",
            value=(pd.Timestamp("2024-08-05").date(), pd.Timestamp("2024-08-11").date()),
            min_value=data["hourly"]["timestamp"].min().date(),
            max_value=data["hourly"]["timestamp"].max().date(),
        )
    with proof_col:
        st.markdown(
            f"""
            <div class="scenario-panel">
              <div class="status">Selected transparent prior</div>
              <h4>{safe(metrics['selected_model_name'])}</h4>
              <p>Holdout MAE {metrics['selected_validation_mae_shape_index']:.4f} · NMAE {metrics['selected_validation_nmae_pct_of_mean_shape']:.2f}% · ML candidate selected: NO</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start = pd.Timestamp(date_range[0])
        end = pd.Timestamp(date_range[1]) + pd.Timedelta(hours=23, minutes=59)
        view = data["hourly"].loc[data["hourly"]["timestamp"].between(start, end)]
    else:
        view = data["hourly"].head(168)

    fig = go.Figure()
    series = [("total_kwh", "Total load", COLORS["cyan"]), ("hvac_kwh", "HVAC", COLORS["amber"]), ("non_hvac_kwh", "Non-HVAC", COLORS["blue"])]
    for column, label, color in series:
        fig.add_trace(go.Scatter(x=view["timestamp"], y=view[column], name=label, mode="lines", line={"color": color, "width": 2.4 if column == "total_kwh" else 1.5}, hovertemplate=f"{label}<br>%{{x|%m-%d %H:%M}} · %{{y:.2f}} kWh<extra></extra>"))
    fig.update_yaxes(title="kWh / hour")
    st.plotly_chart(style_figure(fig, "Monthly-Constrained Hourly Load · Displayed Window", 460), width="stretch", config={"displayModeBar": False})
    with st.expander("View monthly reconciliation audit table", expanded=False):
        st.dataframe(data["reconciliation"], width="stretch", hide_index=True)

elif page == "04  Efficiency & ROI":
    page_header("04", "Efficiency Scenarios & Investment Screening", "Express uncertainty through low/base/high engineering-screening bounds while keeping CAPEX assumptions beside investment results.", "SCENARIO INTELLIGENCE")
    scenarios = data["scenario"].query("scenario_id != 'baseline'").copy()
    scenario_map = dict(zip(scenarios["scenario_name"], scenarios["scenario_id"]))
    default_index = list(scenario_map.keys()).index("Combined package (HVAC + LED + operations)") if "Combined package (HVAC + LED + operations)" in scenario_map else 0
    selected_name = st.selectbox("Focus scenario", list(scenario_map.keys()), index=default_index)
    selected_id = scenario_map[selected_name]
    selected = scenarios.query("scenario_id == @selected_id")
    if selected.empty:
        selected = scenarios.iloc[[0]]
    selected = selected.iloc[0]

    render_metric_grid(
        [
            {"label": "P50 annual saving", "value": f"{selected['annual_saved_kwh_p50']/1000:,.1f}", "unit": "MWh", "note": f"P10 {selected['annual_saved_kwh_p10']/1000:,.1f} · P90 {selected['annual_saved_kwh_p90']/1000:,.1f}", "color": COLORS["cyan"]},
            {"label": "Saving rate", "value": f"{selected['saving_rate_pct_p50']:.2f}", "unit": "%", "note": "Relative to the annual baseline", "color": COLORS["blue"]},
            {"label": "Annual cost saving", "value": f"{selected['annual_saving_cny_p50']/1000:,.1f}k", "unit": "CNY", "note": "Ningbo reference case: saved kWh × CNY 0.538", "color": COLORS["green"]},
            {"label": "Simple payback", "value": f"{selected['simple_payback_years_p50']:.2f}", "unit": "years", "note": "Assumed CAPEX requires supplier quotations", "color": COLORS["amber"]},
        ]
    )

    chart_col, status_col = st.columns([1.7, .8], gap="large")
    with chart_col:
        scenarios_sorted = scenarios.sort_values("annual_saved_kwh_p50")
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=scenarios_sorted["annual_saved_kwh_p50"] / 1000,
                y=scenarios_sorted["scenario_name"], orientation="h",
                error_x={
                    "type": "data", "symmetric": False,
                    "array": (scenarios_sorted["annual_saved_kwh_p90"] - scenarios_sorted["annual_saved_kwh_p50"]) / 1000,
                    "arrayminus": (scenarios_sorted["annual_saved_kwh_p50"] - scenarios_sorted["annual_saved_kwh_p10"]) / 1000,
                    "color": COLORS["muted"], "thickness": 1.2,
                },
                marker={"color": [COLORS["cyan"] if name == selected_name else "#315876" for name in scenarios_sorted["scenario_name"]], "line": {"width": 0}},
                hovertemplate="%{y}<br>P50 <b>%{x:.2f} MWh</b><extra></extra>",
            )
        )
        fig.update_xaxes(title="Annual saving · MWh")
        st.plotly_chart(style_figure(fig, "Efficiency Scenario Screening Bounds · P10–P90 Labels", 430), width="stretch", config={"displayModeBar": False})
    with status_col:
        st.markdown(
            f"""
            <div class="decision-card" style="min-height:26.9rem">
              <h3>Investment evidence</h3><p>Decision readiness of the selected scenario</p>
              <div class="decision-row"><span>Assumed CAPEX</span><strong>CNY {selected['capex_cny_assumption']:,.0f}<em>screening only</em></strong></div>
              <div class="decision-row"><span>Quotation status</span><strong>Not obtained<em>supplier quote needed</em></strong></div>
              <div class="decision-row"><span>Result type</span><strong>Screening estimate<em>with uncertainty</em></strong></div>
              <div class="decision-row"><span>Next decision gate</span><strong>Site verification<em>schedule + equipment</em></strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    render_notice("warn", "Investment conclusion boundary", "The Ningbo reference-case billing rule is electricity bill = kWh × CNY 0.538, with no time-of-use, demand or other charge components. The Malaysia carbon output is a parameterized scenario assumption, not a Malaysia field result. P10/P50/P90 use 0.75/1.00/1.25 engineering-screening multipliers, not probability quantiles calibrated from site data. Supplier quotations and post-implementation M&V are still required before procurement or guaranteed-savings decisions.")
    with st.expander("View all scenario parameters and results", expanded=False):
        st.dataframe(scenarios, width="stretch", hide_index=True)

elif page == "05  PV & Future Storage":
    page_header("05", "Installed PV & Future Storage", "Use the installed 106.14 kWp PV system as the current case, then compare no storage with two future battery strategies.", "PV NOW · STORAGE FUTURE")
    render_notice("warn", "Current assets and future scenarios are separated", "The anonymized reference case includes an approved aggregate 106.14 kWp PV system and 126.23 MWh annual generation. It currently has no battery storage. The 300 kWh / 120 kW battery is used only in a future loss-aware technology sandbox.")

    grid_reduction = (1 - loss_aware["grid_import_kwh"] / naive["grid_import_kwh"]) * 100
    loss_reduction = (1 - loss_aware["battery_loss_kwh"] / naive["battery_loss_kwh"]) * 100
    render_metric_grid(
        [
            {"label": "Aggregate PV generation", "value": f"{current_pv['pv_generation_kwh']/1000:,.2f}", "unit": "MWh", "note": "Twelve approved aggregate monthly anchors", "color": COLORS["green"]},
            {"label": "Estimated self-sufficiency", "value": f"{current_pv['self_sufficiency_pct']:.2f}", "unit": "%", "note": "Screening estimate; not measured at the grid point", "color": COLORS["cyan"]},
            {"label": "Grid import vs rule-based", "value": f"-{grid_reduction:.2f}", "unit": "%", "note": f"Loss-aware strategy reduces grid import to {loss_aware['grid_import_kwh']/1000:,.1f} MWh", "color": COLORS["green"]},
            {"label": "Battery loss vs rule-based", "value": f"-{loss_reduction:.2f}", "unit": "%", "note": "Future storage sandbox only", "color": COLORS["amber"]},
        ]
    )

    left, right = st.columns(2, gap="large")
    metrics_df = data["loss_metrics"].copy()
    strategy_labels = {"no_battery": "Current PV · no storage", "naive_grid_charge": "Future battery · rule-based", "loss_aware_lp": "Future battery · loss-aware"}
    metrics_df["strategy_label"] = metrics_df["strategy_id"].map(strategy_labels).fillna(metrics_df["strategy_id"])
    with left:
        fig = go.Figure()
        fig.add_bar(name="Grid import · MWh", x=metrics_df["strategy_label"], y=metrics_df["grid_import_kwh"] / 1000, marker_color=COLORS["cyan"], hovertemplate="%{x}<br>%{y:.2f} MWh<extra></extra>")
        fig.update_yaxes(title="MWh")
        st.plotly_chart(style_figure(fig, "Grid Imports across Three Strategies", 365), width="stretch", config={"displayModeBar": False})
    with right:
        battery_rows = metrics_df.query("strategy_id != 'no_battery'")
        fig = go.Figure()
        fig.add_bar(name="Battery loss", x=battery_rows["strategy_label"], y=battery_rows["battery_loss_kwh"] / 1000, marker_color=COLORS["amber"])
        fig.add_bar(name="Battery throughput", x=battery_rows["strategy_label"], y=battery_rows["battery_throughput_kwh"] / 1000, marker_color=COLORS["blue"])
        fig.update_layout(barmode="group")
        fig.update_yaxes(title="MWh")
        st.plotly_chart(style_figure(fig, "Battery Loss and Throughput", 365), width="stretch", config={"displayModeBar": False})

    section_title("Representative week", "Energy Flows · Future Loss-Aware Battery Scenario")
    week = data["loss_detail"].query("strategy_id == 'loss_aware_lp'")
    week = week.loc[week["timestamp"].between("2024-08-05", "2024-08-11 23:00")]
    fig = go.Figure()
    for column, label, color in [
        ("load_kwh", "Building load", COLORS["cyan"]),
        ("pv_generation_kwh", "PV generation", COLORS["amber"]),
        ("grid_import_kwh", "Grid import", COLORS["blue"]),
        ("battery_to_load_kwh", "Battery to load", COLORS["green"]),
    ]:
        fig.add_trace(go.Scatter(x=week["timestamp"], y=week[column], name=label, mode="lines", line={"color": color, "width": 2}, hovertemplate=f"{label}<br>%{{x|%m-%d %H:%M}} · %{{y:.2f}} kWh<extra></extra>"))
    fig.update_yaxes(title="kWh / hour")
    st.plotly_chart(style_figure(fig, None, 430), width="stretch", config={"displayModeBar": False})
    with st.expander("View strategy metrics and the energy-balance explanation", expanded=False):
        st.dataframe(data["loss_metrics"], width="stretch", hide_index=True)
        st.caption("Grid import = grid to load + grid to battery. The linear programme uses the Ningbo reference-case tariff of CNY 0.538/kWh and constrains hourly energy balance, power and SOC. Procurement value still depends on battery quotations, maintenance and lifetime.")

elif page == "06  Twin & Data":
    page_header("06", "Digital Twin & Missing Evidence", "Bring the building–floor–system–meter/model relationships and next data-collection tasks into one evidence-governance view.", "EVIDENCE GOVERNANCE")
    twin = data["digital_twin"]
    requests = data["data_request"]
    p0 = requests.query("priority == 'P0'")
    documented = int(twin["evidence_level"].isin(["documented", "measured"]).sum())
    render_metric_grid(
        [
            {"label": "Twin entities", "value": str(len(twin)), "unit": "objects", "note": "Building, floors, systems, meters and models", "color": COLORS["cyan"]},
            {"label": "Measured / documented", "value": str(documented), "unit": "objects", "note": "Supported by primary or documentary evidence", "color": COLORS["green"]},
            {"label": "P0 data requests", "value": str(len(p0)), "unit": "items", "note": "Site data with the highest model-upgrade value", "color": COLORS["amber"]},
            {"label": "Source lineage", "value": str(len(data["lineage"])), "unit": "sources", "note": "Provenance, availability and use boundaries", "color": COLORS["blue"]},
        ]
    )

    section_title("Twin topology", "Traceable Entity Relationships")
    st.markdown(
        """
        <div class="twin-flow">
          <div class="twin-node"><div class="level">Building</div><h4>Ningbo Reference Building</h4><p>6,231.26 m² · 3 floors · identity anonymized</p><div class="evidence">● approved aggregate</div></div>
          <div class="twin-node"><div class="level">Floors</div><h4>1F · 2F · 3F</h4><p>Assumed open daily 08:00–22:00; comfort values are a synthetic proxy</p><div class="evidence">● documented + assumed</div></div>
          <div class="twin-node"><div class="level">Systems</div><h4>Metering · HVAC · PV</h4><p>Four monthly meters, VRF design schedule and 106.14 kWp PV</p><div class="evidence">● measured + design</div></div>
          <div class="twin-node"><div class="level">Models</div><h4>8,760 · Comfort · Loss-aware</h4><p>Monthly-constrained hourly estimates; storage is a future scenario only</p><div class="evidence">● derived + sandbox</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_title("Next evidence actions", "Highest-Priority Site Information")
    cards = []
    for _, row in p0.head(3).iterrows():
        cards.append(
            f"""
            <div class="request-card">
              <div class="priority">P0 · highest priority</div>
              <h4>{safe(row['data_needed'])}</h4>
              <p>{safe(row['practical_way_to_get_it'])}</p>
            </div>
            """
        )
    st.html('<div class="request-grid">' + "".join(cards) + "</div>")
    render_notice("info", "Screening-stage substitutes exist for every critical gap", "Use a monthly-constrained 8,760-hour estimate when high-frequency meters are unavailable; a comfort proxy when indoor records are missing; approved aggregate PV anchors with a synthetic intraday shape; and engineering-screening bounds when quotations are missing. Substitutes are not site calibration, and any additional rooftop capacity still requires structural-engineer review.")

    entity_tab, readiness_tab, request_tab, lineage_tab = st.tabs(["Entity Register", "Model Readiness", "Data Requests", "Source Lineage"])
    with entity_tab:
        st.dataframe(twin, width="stretch", hide_index=True)
    with readiness_tab:
        st.dataframe(data["model_readiness"], width="stretch", hide_index=True)
    with request_tab:
        st.dataframe(requests, width="stretch", hide_index=True)
    with lineage_tab:
        visible_columns = [column for column in ["source_name", "exists", "evidence_type", "use_boundary"] if column in data["lineage"].columns]
        st.dataframe(data["lineage"][visible_columns], width="stretch", hide_index=True)

elif page == "07  Analysis Agent":
    page_header("07", "Hybrid Energy Analysis Agent", "Deterministic local tools produce project numbers; optional OpenAI orchestration improves understanding, planning and expression, with automatic local fallback.", "HYBRID AGENT · 9 AUDITABLE TOOLS")

    if "agent_session_id" not in st.session_state:
        st.session_state.agent_session_id = secrets.token_hex(12)

    engine_label = st.segmented_control(
        "Agent engine",
        options=("Auditable local mode", "OpenAI-enhanced mode"),
        default="Auditable local mode",
        key="agent_engine_label",
        width="stretch",
    ) or "Auditable local mode"
    enhanced_mode = engine_label == "OpenAI-enhanced mode"

    setting_col1, setting_col2, setting_col3 = st.columns([1.15, 1, 1])
    with setting_col1:
        selected_model = st.selectbox("Enhanced model", ALLOWED_MODELS, index=1, disabled=not enhanced_mode, key="agent_openai_model")
    with setting_col2:
        selected_effort = st.selectbox("Reasoning effort", ALLOWED_EFFORTS, index=1, disabled=not enhanced_mode, key="agent_openai_effort")
    with setting_col3:
        session_key = st.text_input(
            "Session API key (optional)",
            type="password",
            disabled=not enhanced_mode,
            placeholder="Retained only for this Streamlit session",
            key="agent_session_api_key",
        )

    server_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not server_key:
        try:
            server_key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        except Exception:
            server_key = ""
    api_key = server_key or session_key.strip()
    key_source = "secure server configuration" if server_key else "temporary session input" if session_key.strip() else "not configured"
    if enhanced_mode:
        st.markdown(
            f'<div class="agent-engine-note"><b>Key status: {safe(key_source)}</b> · The server key is never exposed to the browser, and session input is not written to project files or Git. Only the current question, six recent user questions and deterministic-tool summaries are sent. Local mode is used automatically if OpenAI is unavailable.</div>',
            unsafe_allow_html=True,
        )
        if st.button("Test OpenAI connection", disabled=not bool(api_key), key="test_openai_connection"):
            with st.spinner("Running a minimal connection test…"):
                connection_ok, connection_message = test_openai_connection(api_key, selected_model, selected_effort)
            (st.success if connection_ok else st.error)(connection_message)

    planner_text = "OpenAI tool orchestration + 9 deterministic tools" if enhanced_mode and api_key else "local planner + 9 deterministic tools"
    status_tail = f"Model {selected_model} · key source: {key_source}" if enhanced_mode else "Fully offline · no external API"
    st.markdown(
        f"""
        <div class="agent-status">
          <div><i></i>Agent online · {safe(planner_text)}</div>
          <span>{safe(status_tail)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = [
            {
                "role": "assistant",
                "content": "Hello, I am the Irene hybrid energy-analysis Agent. In both local and OpenAI-enhanced modes, the same auditable tools calculate every project number. Enhanced mode improves understanding, tool orchestration and answer composition. Try: ‘If the tariff rises by 20%, which measure pays back fastest and which saves the most energy?’ Then ask ‘What if it falls by 10%?’ and I will retain the context.",
                "response": None,
            }
        ]

    def render_agent_meta(response: AgentResponse) -> None:
        source_items = "".join(f"<li>{safe(item)}</li>" for item in response.sources)
        action_items = "".join(f"<li>{safe(item)}</li>" for item in response.next_steps)
        plan_items = "".join(f"<li>{safe(item)}</li>" for item in response.plan_steps)
        calculation_items = "".join(f"<li>{safe(item)}</li>" for item in response.calculations) or "<li>No additional numerical recalculation was triggered</li>"
        concept_items = ", ".join(safe(item) for item in response.matched_concepts) or "text-similarity features"
        warning_items = "".join(f"<li>{safe(item)}</li>" for item in response.warnings)
        fallback_html = f'<h5>Automatic fallback</h5><p>{safe(response.fallback_reason)}</p>' if response.fallback_reason else ""
        if response.engine == "openai":
            mode_detail = f"OpenAI orchestration · {response.tool_call_count} tool call(s) · tokens {response.input_tokens}/{response.output_tokens} in/out"
        elif response.engine == "fallback":
            mode_detail = "Local fallback · deterministic Irene tools"
        else:
            mode_detail = f"Intent match score {response.route_confidence*100:.0f}% · heuristic"
        st.markdown(
            f"""
            <div class="agent-trace">
              <div class="agent-trace-head">
                <span class="agent-pill tool">TOOL · {safe(response.tool_name)}</span>
                <span class="agent-pill">INTENTS · {safe(' + '.join(response.intents or (response.intent,)))}</span>
                <span class="agent-pill evidence">EVIDENCE · {safe(response.evidence_class)}</span>
              </div>
              <div class="agent-plan">
                <div><h5>Analysis plan</h5><ol>{plan_items}</ol></div>
                <div class="calc"><h5>Scenario calculations</h5><ul>{calculation_items}</ul></div>
              </div>
              <h5>Routing basis</h5><p>{concept_items}</p>
              <h5>Decision readiness</h5><p>{safe(response.decision_readiness)}</p>
              {f'<h5>Input notes</h5><ul>{warning_items}</ul>' if warning_items else ''}
              {fallback_html}
              <h5>Evidence sources</h5><ul>{source_items}</ul>
              <h5>Recommended next steps</h5><ul>{action_items}</ul>
              <p class="agent-confidence">Interpretation boundary · {safe(response.confidence)}</p>
              <div class="agent-mode"><b>{safe(response.model_mode)}</b><span>{safe(mode_detail)}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            response = message.get("response")
            if response is None:
                st.markdown(message["content"])
            else:
                st.markdown(f"**{response.title}**")
                st.markdown(response.answer)
                render_agent_meta(response)

    selected_prompt = None
    latest_response = next((item.get("response") for item in reversed(st.session_state.agent_messages) if item.get("response") is not None), None)
    if latest_response and latest_response.follow_ups:
        st.markdown('<div class="agent-quick-label">Context-aware follow-ups</div>', unsafe_allow_html=True)
        follow_columns = st.columns(len(latest_response.follow_ups))
        for index, follow_up in enumerate(latest_response.follow_ups):
            if follow_columns[index].button(follow_up, key=f"agent_follow_{len(st.session_state.agent_messages)}_{index}", width="stretch"):
                selected_prompt = follow_up

    st.markdown('<div class="agent-quick-label">Reasoning challenges</div>', unsafe_allow_html=True)
    quick_columns = st.columns(3)
    for index, prompt in enumerate(QUICK_PROMPTS):
        if quick_columns[index % 3].button(prompt, key=f"agent_quick_{index}", width="stretch"):
            selected_prompt = prompt

    typed_prompt = st.chat_input("Ask about the Irene energy model…")
    prompt = typed_prompt or selected_prompt
    if prompt:
        context = {
            "model_version": summary["model_version"],
            "annual_total_kwh": summary["annual_total_kwh"],
            "annual_hvac_kwh": summary["annual_hvac_kwh"],
            "hvac_share_pct": summary["hvac_share_pct"],
            "gross_floor_area_m2": summary["real_case"]["gross_floor_area_m2"],
            "annual_eui_kwh_m2": summary["annual_eui_kwh_m2"],
            "tariff_cny_kwh": summary["tariff"]["value"],
            "pv_generation_kwh": current_pv["pv_generation_kwh"],
            "current_grid_import_kwh": current_pv["grid_import_kwh"],
            "current_self_sufficiency_pct": current_pv["self_sufficiency_pct"],
            "current_pv_self_consumption_pct": current_pv["pv_self_consumption_pct"],
            "combo_saved_kwh": combo["annual_saved_kwh_p50"],
            "combo_saving_rate_pct": combo["saving_rate_pct_p50"],
            "combo_saving_cny": combo["annual_saving_cny_p50"],
            "combo_capex_cny": combo["capex_cny_assumption"],
            "combo_payback_years": combo["simple_payback_years_p50"],
            "combo_carbon_tco2e": combo["avoided_tco2e_maic_p50"],
            "loss_aware_grid_import_kwh": loss_aware["grid_import_kwh"],
            "naive_grid_import_kwh": naive["grid_import_kwh"],
            "grid_reduction_vs_naive_pct": (1 - loss_aware["grid_import_kwh"] / naive["grid_import_kwh"]) * 100,
            "battery_loss_reduction_pct": (1 - loss_aware["battery_loss_kwh"] / naive["battery_loss_kwh"]) * 100,
        }
        history = [message["content"] for message in st.session_state.agent_messages if message["role"] == "user" and message.get("content")]
        st.session_state.agent_messages.append({"role": "user", "content": prompt, "response": None})
        with st.spinner("Planning and running Irene project tools…"):
            response = answer_energy_question_hybrid(
                prompt,
                context,
                history,
                mode="openai" if enhanced_mode else "local",
                api_key=api_key,
                model=selected_model,
                effort=selected_effort,
                safety_identifier=f"db-streamlit-{st.session_state.agent_session_id}",
            )
        st.session_state.agent_messages.append({"role": "assistant", "content": "", "response": response})
        st.rerun()

else:
    page_header(
        "08",
        "Client Data Onboarding",
        "Bring client-owned meters, workbooks, documents and building files into a controlled review flow before any value is admitted to the energy model.",
        "SESSION-ONLY · HUMAN-CONFIRMED",
    )
    render_notice(
        "success",
        "Local processing is the default",
        "CSV, Excel, text-bearing PDF and Word files, DXF and IFC are inspected in this Streamlit session. Raw uploads are not written to the project, committed to GitHub or admitted to the model automatically.",
    )
    st.markdown(
        """
        <div class="evidence-grid">
          <div class="evidence-item" style="--dot:#53e6a5"><div class="tag">PHASE 1 · DATA</div><p>CSV and Excel mapping, unit review, data-quality checks and readiness scoring</p></div>
          <div class="evidence-item" style="--dot:#43d9ff"><div class="tag">PHASE 2 · DOCUMENTS</div><p>PDF and Word facts locally; scans and images through explicit optional recognition</p></div>
          <div class="evidence-item" style="--dot:#a98bff"><div class="tag">PHASE 3 · BIM / CAD</div><p>IFC entities and DXF layers, blocks and labels; DWG enters through a verified conversion gate</p></div>
          <div class="evidence-item" style="--dot:#ffbe55"><div class="tag">CONTROL GATE</div><p>Every mapping, unit and extracted fact requires client-side review before approval</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_title("CLIENT PROJECT", "Project assumptions and reporting boundary")
    profile_1, profile_2, profile_3, profile_4 = st.columns(4)
    with profile_1:
        client_project_name = st.text_input("Project name", value="Client energy review")
        client_reference = st.text_input("Client reference", placeholder="Optional internal reference")
    with profile_2:
        client_site_name = st.text_input("Site name", placeholder="Client site or portfolio")
        client_region = st.text_input("Country or region", placeholder="Reporting jurisdiction")
    with profile_3:
        client_currency = st.text_input("Currency", value="MYR", max_chars=16)
        client_tariff = st.number_input("Tariff per kWh", min_value=0.0, value=0.0, step=0.001, format="%.4f", help="Enter 0 when no confirmed tariff is available.")
    with profile_4:
        client_carbon_factor = st.number_input("Grid factor (kgCO₂e/kWh)", min_value=0.0, value=0.0, step=0.001, format="%.4f", help="Use the factor approved for the client's reporting boundary; no default is assumed.")
        client_floor_area = st.number_input("Gross floor area (m²)", min_value=0.0, value=0.0, step=10.0, help="Enter 0 when area is not yet confirmed.")
    client_profile = {
        "project_name": client_project_name,
        "client_reference": client_reference,
        "site_name": client_site_name,
        "country_or_region": client_region,
        "currency": client_currency,
        "tariff_per_kwh": client_tariff,
        "grid_emission_factor_kg_co2e_kwh": client_carbon_factor,
        "gross_floor_area_m2": client_floor_area,
    }
    st.caption("Tariff, grid factor and floor area remain explicit client inputs unless the same field is present in a confirmed source file. Irene does not silently substitute jurisdictional defaults.")

    uploaded_files = st.file_uploader(
        "Add client files",
        type=["csv", "xlsx", "xlsm", "pdf", "docx", "png", "jpg", "jpeg", "tif", "tiff", "dxf", "ifc", "dwg"],
        accept_multiple_files=True,
        help="Maximum 25 MB per file. Password-protected and unsupported active-content files are rejected.",
    )
    if not uploaded_files:
        st.info("Start with a meter CSV or workbook. Add bills, equipment schedules, IFC or DXF files when available; the system will show which analyses become supportable.")
    else:
        manifests: list[dict[str, object]] = []
        source_bytes: dict[str, bytes] = {}
        for uploaded in uploaded_files:
            content = uploaded.getvalue()
            try:
                manifest = parse_client_file(uploaded.name, content)
                manifests.append(manifest)
                source_bytes[str(manifest["sha256"])] = content
            except Exception as error:
                st.error(f"{uploaded.name}: {error}")

        if manifests:
            confirmed_manifests: list[dict[str, object]] = []
            total_tables = sum(len(item.get("tables", [])) for item in manifests)
            total_facts = sum(len(item.get("extracted_facts", [])) for item in manifests)
            conversion_items = sum(item.get("status") == "conversion_required" for item in manifests)
            render_metric_grid(
                [
                    {"label": "Accepted files", "value": str(len(manifests)), "unit": "session", "note": "Held in memory for this review", "color": COLORS["green"]},
                    {"label": "Data tables", "value": str(total_tables), "unit": "mapped", "note": "Each field remains editable", "color": COLORS["cyan"]},
                    {"label": "Extracted facts", "value": str(total_facts), "unit": "review", "note": "No inferred missing values", "color": COLORS["blue"]},
                    {"label": "Conversion gates", "value": str(conversion_items), "unit": "DWG", "note": "DXF is the portable fallback", "color": COLORS["amber"]},
                ]
            )

            for file_index, manifest in enumerate(manifests):
                digest = str(manifest["sha256"])
                with st.expander(f"{manifest['phase']} · {manifest['filename']} · {manifest['status'].replace('_', ' ').title()}", expanded=file_index == 0):
                    st.caption(f"{manifest['kind']} · {manifest['size_bytes'] / 1024:,.1f} KB · SHA-256 {digest[:12]}…")
                    for note in manifest.get("notes", []):
                        st.write(f"• {note}")

                    edited_mappings: dict[str, list[dict[str, object]]] = {}
                    for table_index, table in enumerate(manifest.get("tables", [])):
                        st.markdown(f"#### {table['name']} · {table['row_count']:,} rows × {table['column_count']:,} columns")
                        table["included_for_project"] = st.checkbox(
                            "Include this table in the consolidated client analysis",
                            value=bool(table.get("included_for_project", True)),
                            key=f"include_{digest}_{table_index}",
                            help="Turn this off for cover sheets, lookup tabs or duplicate summaries.",
                        )
                        st.dataframe(pd.DataFrame(table["preview"]), width="stretch", hide_index=True)
                        mapping_frame = pd.DataFrame(table["mappings"])[["source", "target", "unit", "confidence", "requires_confirmation"]]
                        edited = st.data_editor(
                            mapping_frame,
                            width="stretch",
                            hide_index=True,
                            disabled=["source", "confidence", "requires_confirmation"],
                            column_config={
                                "target": st.column_config.SelectboxColumn("Model field", options=["unmapped", *FIELD_LIBRARY.keys()], required=True),
                                "unit": st.column_config.TextColumn("Confirmed source unit"),
                                "confidence": st.column_config.ProgressColumn("Match", min_value=0.0, max_value=1.0, format="%.0f%%"),
                                "requires_confirmation": st.column_config.CheckboxColumn("Review"),
                            },
                            key=f"mapping_{digest}_{table_index}",
                        )
                        edited_mappings[str(table["name"])] = edited.to_dict(orient="records")
                        table["mappings"] = edited_mappings[str(table["name"])]
                        quality = table["quality"]
                        q1, q2, q3, q4 = st.columns(4)
                        q1.metric("Quality score", f"{quality['score']}/100")
                        q2.metric("Errors", quality["errors"])
                        q3.metric("Warnings", quality["warnings"])
                        q4.metric("Granularity", quality["coverage"]["granularity"])
                        if quality["issues"]:
                            st.dataframe(pd.DataFrame(quality["issues"]), width="stretch", hide_index=True)
                        for unit_note in table.get("unit_notes", []):
                            st.warning(unit_note)

                    facts = manifest.get("extracted_facts", [])
                    if facts:
                        st.markdown("#### Extracted document or drawing facts")
                        st.dataframe(pd.DataFrame(facts), width="stretch", hide_index=True)
                    if manifest.get("details"):
                        with st.popover("View technical extraction details"):
                            st.json(manifest["details"])

                    extension = str(manifest["extension"])
                    if extension in CLOUD_EXTENSIONS:
                        consent = st.checkbox(
                            "I have permission to send this selected file to the configured recognition service for this request.",
                            key=f"cloud_consent_{digest}",
                        )
                        st.caption("Optional: use this only for scans, images or ambiguous pages. The request is made server-side with store:false; CSV, Excel, DXF, IFC and DWG are never sent by this control.")
                        if st.button("Run optional document recognition", key=f"cloud_run_{digest}", disabled=not consent):
                            api_key = os.environ.get("OPENAI_API_KEY", "")
                            try:
                                with st.spinner("Reading the selected document…"):
                                    cloud_result = recognise_document(str(manifest["filename"]), source_bytes[digest], api_key)
                                st.session_state[f"cloud_result_{digest}"] = cloud_result
                            except Exception as error:
                                st.error(str(error))
                        cloud_result = st.session_state.get(f"cloud_result_{digest}")
                        if cloud_result:
                            st.success(cloud_result.get("summary", "Recognition completed."))
                            if cloud_result.get("facts"):
                                st.dataframe(pd.DataFrame(cloud_result["facts"]), width="stretch", hide_index=True)
                            if cloud_result.get("equipment"):
                                st.dataframe(pd.DataFrame(cloud_result["equipment"]), width="stretch", hide_index=True)
                            for review_item in cloud_result.get("review_items", []):
                                st.warning(review_item)

                    confirmed = st.checkbox(
                        "I reviewed the field mappings, source units, quality findings and extracted facts for this file.",
                        key=f"confirm_{digest}",
                    )
                    template = build_mapping_template(manifest)
                    for table_template in template["tables"]:
                        table_template["mappings"] = edited_mappings.get(str(table_template["name"]), table_template["mappings"])
                        for mapping in table_template["mappings"]:
                            mapping["confirmed"] = confirmed
                    template["approved_for_model"] = confirmed
                    st.download_button(
                        "Download reviewed mapping record",
                        data=json.dumps(template, indent=2, ensure_ascii=False),
                        file_name=f"{Path(str(manifest['filename'])).stem}_irene_mapping.json",
                        mime="application/json",
                        key=f"mapping_download_{digest}",
                    )
                    if confirmed:
                        confirmed_manifests.append(manifest)
                        st.success("Control gate passed for this file. Its reviewed mapping record is ready for the client-specific model pipeline.")
                    else:
                        st.info("Review is incomplete. This file remains outside the model pipeline.")

            if confirmed_manifests:
                client_analysis = assess_client_project(confirmed_manifests, client_profile)
                client_results = client_analysis["results"]
                client_currency_label = client_analysis["project"]["currency"]

                section_title("CONFIRMED RESULTS", "Client reporting-period baseline")
                energy_value = client_results.get("electricity_kwh")
                reporting_cost = client_results.get("reporting_cost")
                emissions = client_results.get("emissions_tco2e")
                eui = client_results.get("reporting_period_eui_kwh_m2")
                render_metric_grid(
                    [
                        {"label": "Electricity", "value": f"{energy_value / 1000:,.2f}" if energy_value is not None else "—", "unit": "MWh", "note": "Confirmed reporting period", "color": COLORS["green"]},
                        {"label": "Energy cost", "value": f"{reporting_cost:,.2f}" if reporting_cost is not None else "—", "unit": client_currency_label, "note": str(client_results.get("cost_basis", "unavailable")), "color": COLORS["cyan"]},
                        {"label": "Operational emissions", "value": f"{emissions:,.3f}" if emissions is not None else "—", "unit": "tCO₂e", "note": "Client-supplied grid factor", "color": COLORS["blue"]},
                        {"label": "Reporting-period EUI", "value": f"{eui:,.2f}" if eui is not None else "—", "unit": "kWh/m²", "note": "Not annualised unless coverage supports it", "color": COLORS["amber"]},
                    ]
                )

                coverage = client_analysis["coverage"]
                source_a, source_b, source_c, source_d = st.columns(4)
                source_a.metric("Confirmed files", client_analysis["control_gate"]["approved_files"])
                source_b.metric("Included tables", len(client_analysis["source_tables"]))
                source_c.metric("Data quality", f"{client_results['quality_score']}/100" if client_results.get("quality_score") is not None else "—")
                source_d.metric("Coverage", f"{coverage['dated_months']} dated month(s)")

                if client_analysis["monthly"]:
                    monthly_frame = pd.DataFrame(client_analysis["monthly"])
                    st.markdown("#### Consolidated monthly baseline")
                    st.dataframe(monthly_frame, width="stretch", hide_index=True)
                    if "electricity_kwh" in monthly_frame.columns:
                        chart_frame = monthly_frame.loc[monthly_frame["period"] != "undated", ["period", "electricity_kwh"]].dropna()
                        if len(chart_frame):
                            st.bar_chart(chart_frame.set_index("period"), color=COLORS["cyan"])

                for warning in client_analysis["warnings"]:
                    st.warning(warning)
                render_notice("success", "Evidence boundary preserved", client_analysis["evidence_boundary"])
                deliverable = build_client_deliverable(confirmed_manifests, client_analysis)
                st.download_button(
                    "Download client project deliverable (.zip)",
                    data=deliverable,
                    file_name="irene_client_project_deliverable.zip",
                    mime="application/zip",
                    help="Contains results, mappings, quality records, file fingerprints and an audit log. Raw uploads are excluded.",
                )
            elif manifests:
                render_notice("warning", "Project analysis locked", "Confirm at least one reviewed file to calculate client results and create the audit-ready deliverable pack.")

st.markdown(
    f"""
    <div class="app-footer">
      <span>TEAM ENERGEN AI · PROJECT IRENE · T1 — AI FOR CLEAN ENERGY</span>
      <span>Approved Aggregate → Synthetic → Derived → Assumed → Sandbox</span>
    </div>
    """,
    unsafe_allow_html=True,
)
