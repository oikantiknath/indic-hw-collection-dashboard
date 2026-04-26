import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import numpy as np
import boto3
from botocore.client import Config
import io
import json as _json
import pypdf
import urllib3
import os
from dotenv import load_dotenv

from mappings import (
    STATE_TO_LANGUAGE, CLASS_LEVEL_FROM_GRADE,
    SUBJECT_MAP, SAMPLE_TYPE_MAP, GENDER_MAP, BOARD_MAP,
    BLOCK_MAP, SCHOOL_NORMALIZATIONS, SUBJ_CAT_MAP, fuzzy_subject,
)
from s3_helpers import (
    _s3,
    presigned_url as _presigned_url,
    load_page_cache as _load_page_cache,
    save_page_cache as _save_page_cache,
    count_pdf_pages as _count_pdf_pages,
    MINIO_BUCKET, MINIO_PREFIX,
)
from chart_helpers import (
    make_chart_layout, section, badge, progress_bar_html,
    C_GREEN, C_RED, C_AMBER, C_GREY,
    C_FEMALE, C_MALE, C_GOVT, C_AIDED, C_PRIVATE,
    C_RURAL, C_URBAN, C_LEFT, C_RIGHT,
    C_INDIGO, C_VIOLET, COLORS, CHART_HEIGHT,
)

load_dotenv()



urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OCR-VS Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Theme state (light default) ──────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True

_dark = st.session_state["dark_mode"]

# ── Styling ───────────────────────────────────────────────────────────────────
if _dark:
    _bg               = "#09090B"
    _bg2              = "#121217"
    _bg3              = "#18181F"
    _bg4              = "#1E1E2E"
    _border           = "rgba(255,255,255,0.07)"
    _border2          = "rgba(255,255,255,0.05)"
    _border_card      = "rgba(255,255,255,0.08)"
    _text             = "#FFFFFF"
    _text2            = "#A1A1AA"
    _text3            = "#E2E8F0"
    _text4            = "#94A3B8"
    _input_bg         = "#18181F"
    _input_border     = "rgba(255,255,255,0.12)"
    _title_grad       = "linear-gradient(90deg, #FFFFFF 0%, #A1A1AA 100%)"
    _card_hover_border= "rgba(255,255,255,0.15)"
    _tab_border       = "rgba(255,255,255,0.05)"
    _sidebar_bg       = "#121217"
    _sidebar_hr       = "rgba(255,255,255,0.05)"
    _jump_bg          = "#121217"
    _jump_content_bg  = "#18181F"
    _alert_border     = "rgba(255,255,255,0.05)"
    _progress_track   = "rgba(255,255,255,0.08)"
    _toggle_bg        = "#1E1E2E"
    _toggle_color     = "#FFFFFF"
    _theme_icon       = "☀️"
    _btn_bg           = "#1E1E2E"
    _btn_bg_hover     = "#2A2A3E"
    _btn_color        = "#E2E8F0"
    _btn_border       = "rgba(255,255,255,0.12)"
else:
    _bg               = "#F4F6FB"
    _bg2              = "#FFFFFF"
    _bg3              = "#EEF2F9"
    _bg4              = "#E8EDF7"
    _border           = "rgba(99,102,241,0.12)"
    _border2          = "rgba(99,102,241,0.08)"
    _border_card      = "rgba(99,102,241,0.14)"
    _text             = "#0F172A"
    _text2            = "#475569"
    _text3            = "#1E293B"
    _text4            = "#64748B"
    _input_bg         = "#FFFFFF"
    _input_border     = "rgba(99,102,241,0.25)"
    _title_grad       = "linear-gradient(90deg, #4F46E5 0%, #7C3AED 100%)"
    _card_hover_border= "rgba(99,102,241,0.4)"
    _tab_border       = "rgba(99,102,241,0.12)"
    _sidebar_bg       = "#FFFFFF"
    _sidebar_hr       = "rgba(99,102,241,0.1)"
    _jump_bg          = "#FFFFFF"
    _jump_content_bg  = "#F4F6FB"
    _alert_border     = "rgba(99,102,241,0.12)"
    _progress_track   = "rgba(99,102,241,0.08)"
    _toggle_bg        = "#FFFFFF"
    _toggle_color     = "#4F46E5"
    _theme_icon       = "🌙"
    _btn_bg           = "#FFFFFF"
    _btn_bg_hover     = "#EEF2F9"
    _btn_color        = "#1E293B"
    _btn_border       = "rgba(99,102,241,0.25)"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* ── Streamlit root theme tokens — controls canvas dataframe colours ── */
    :root {{
        --background-color: {_bg2};
        --secondary-background-color: {_bg3};
        --text-color: {_text};
        --font: 'Inter', sans-serif;
    }}

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp > header {{ background-color: transparent !important; }}
    .stApp {{
        background-color: {_bg} !important;
        background-image:
            radial-gradient(circle at 15% 50%, rgba(99,102,241,0.06), transparent 40%),
            radial-gradient(circle at 85% 30%, rgba(16,185,129,0.04), transparent 40%);
    }}
    .main .block-container {{ padding-top: 1.2rem; max-width: 1400px; }}

    /* ── Base text & background ── */
    .stApp, .main, [data-testid="stAppViewContainer"] {{
        background-color: {_bg} !important;
        color: {_text} !important;
    }}
    /* Force ALL text elements to use theme colour so nothing goes white-on-white */
    p, li, span:not([data-baseweb]), label, td, th, dt, dd {{ color: {_text3} !important; }}
    div {{ color: {_text3}; }}
    /* Override back to transparent for purely structural divs */
    .element-container, .stPlotlyChart, .block-container {{ color: inherit !important; }}

    /* ── Title ── */
    .dashboard-title {{
        font-size: 4rem; font-weight: 900;
        background: {_title_grad};
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0; letter-spacing: -2px; line-height: 1.1;
    }}
    .dashboard-subtitle {{
        font-size: 1.05rem; color: {_text2}; margin-top: 4px; margin-bottom: 10px;
        font-weight: 500; letter-spacing: -0.2px;
    }}

    /* ── Section headers ── */
    .section-header {{
        font-size: 1.4rem; font-weight: 700; color: {_text} !important;
        display: flex; align-items: center; gap: 12px;
        margin: 20px 0 16px 0; letter-spacing: -0.3px;
    }}
    .section-header::before {{
        content: ''; display: block; width: 6px; height: 24px;
        background: linear-gradient(180deg, #6366F1, #8B5CF6); border-radius: 4px;
    }}

    /* ── KPI cards ── */
    div[data-testid="metric-container"] {{
        background: {_bg2} !important;
        border: 1px solid {_border_card} !important;
        border-radius: 16px; padding: 20px 24px;
        box-shadow: 0 2px 12px rgba(99,102,241,0.07);
        transition: all 0.25s ease;
    }}
    div[data-testid="metric-container"]:hover {{
        transform: translateY(-3px);
        border-color: {_card_hover_border} !important;
        box-shadow: 0 8px 24px rgba(99,102,241,0.13);
    }}
    div[data-testid="metric-container"] label {{
        color: {_text2} !important;
        font-size: 0.75rem !important; font-weight: 600 !important;
        text-transform: uppercase; letter-spacing: 1px;
    }}
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {{
        color: {_text} !important;
        font-size: 2.2rem !important; font-weight: 800 !important; letter-spacing: -0.5px;
    }}
    div[data-testid="metric-container"] div[data-testid="stMetricDelta"] {{
        font-size: 0.8rem !important; font-weight: 600 !important;
    }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{
        background-color: {_sidebar_bg} !important;
        border-right: 1px solid {_border2} !important;
    }}
    section[data-testid="stSidebar"] > div {{
        background-color: {_sidebar_bg} !important;
    }}
    section[data-testid="stSidebar"] * {{ color: {_text2} !important; }}
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {{
        color: {_text} !important; font-weight: 800 !important; letter-spacing: -0.5px;
    }}
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: {_text} !important; font-weight: 600 !important;
        font-size: 0.8rem !important; text-transform: uppercase; letter-spacing: 0.5px;
    }}
    section[data-testid="stSidebar"] hr {{ border-color: {_sidebar_hr} !important; }}

    /* ── Sidebar selectbox controls ── */
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
        background-color: {_input_bg} !important;
        border-color: {_input_border} !important;
        color: {_text} !important;
    }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] span,
    section[data-testid="stSidebar"] div[data-baseweb="select"] p,
    section[data-testid="stSidebar"] div[data-baseweb="select"] input {{
        color: {_text} !important;
        background-color: transparent !important;
    }}

    /* ── Markdown ── */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {{ color: {_text} !important; }}
    .stMarkdown strong {{ color: {_text3} !important; }}
    .stMarkdown p {{ color: {_text3} !important; }}

    /* ── Expander ── */
    .streamlit-expanderHeader, [data-testid="stExpanderToggleIcon"] {{
        color: {_text} !important; font-weight: 600 !important;
    }}
    [data-testid="stExpander"] {{
        background-color: {_bg2} !important;
        border: 1px solid {_border} !important;
        border-radius: 10px !important;
    }}
    [data-testid="stExpander"] summary {{
        background-color: {_bg2} !important;
        color: {_text} !important;
    }}

    /* ── Progress bar labels ── */
    .progress-label {{
        display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;
    }}
    .progress-label span {{ color: {_text2}; font-size: 0.85rem; font-weight: 500; }}
    .progress-label .pct {{ font-weight: 700; color: {_text}; }}

    /* ── Badges ── */
    .badge-pass {{
        background: rgba(16,185,129,0.15); color: #10B981;
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    }}
    .badge-fail {{
        background: rgba(244,63,94,0.15); color: #F43F5E;
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    }}
    .badge-warn {{
        background: rgba(245,158,11,0.15); color: #F59E0B;
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    }}

    /* ── Widgets: selectbox / inputs ── */
    div[data-baseweb="select"] > div {{
        background-color: {_input_bg} !important;
        border-color: {_input_border} !important;
        color: {_text} !important;
        border-radius: 8px !important;
    }}
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] p {{
        background-color: transparent !important;
        color: {_text} !important;
    }}
    div[data-baseweb="select"] svg {{ fill: {_text2} !important; }}

    /* ── Dropdown option list (popover/menu) ── */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    ul[data-baseweb="menu"] {{
        background-color: {_bg2} !important;
        border: 1px solid {_border_card} !important;
        border-radius: 10px !important;
        box-shadow: 0 8px 24px rgba(99,102,241,0.12) !important;
    }}
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li,
    ul[data-baseweb="menu"] li {{
        background-color: {_bg2} !important;
        color: {_text} !important;
    }}
    div[data-baseweb="popover"] *,
    div[data-baseweb="menu"] *,
    ul[data-baseweb="menu"] * {{
        color: {_text} !important;
    }}
    li[role="option"]:hover,
    div[data-baseweb="menu"] li:hover {{
        background-color: {_bg3} !important;
        color: {_text} !important;
    }}
    li[aria-selected="true"] {{
        background-color: rgba(99,102,241,0.12) !important;
    }}

    /* ── Text / number / date inputs ── */
    .stTextInput input, .stNumberInput input, .stDateInput input,
    .stTextArea textarea {{
        background-color: {_input_bg} !important;
        color: {_text} !important;
        border-color: {_input_border} !important;
        border-radius: 8px !important;
    }}
    .stTextInput input:focus, .stNumberInput input:focus,
    .stDateInput input:focus, .stTextArea textarea:focus {{
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.15) !important;
    }}

    /* ── Widget labels ── */
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    .stSelectbox label, .stDateInput label, .stTextInput label,
    .stNumberInput label, .stRadio label, .stCheckbox label {{
        color: {_text2} !important;
        font-weight: 500 !important;
    }}

    /* ── Dataframe / table ── */
    [data-testid="stDataFrame"],
    .stDataFrame {{
        background-color: {_bg2} !important;
        border: 1px solid {_border} !important;
        border-radius: 10px !important;
        overflow: hidden;
    }}
    [data-testid="stDataFrame"] *,
    .stDataFrame * {{
        color: {_text} !important;
        background-color: transparent !important;
    }}
    [data-testid="stDataFrame"] thead th,
    .stDataFrame thead th {{
        background-color: {_bg3} !important;
        color: {_text} !important;
        font-weight: 700 !important;
        border-bottom: 1px solid {_border} !important;
    }}
    [data-testid="stDataFrame"] tbody tr:hover td,
    .stDataFrame tbody tr:hover td {{
        background-color: {_bg4} !important;
    }}
    [data-testid="stDataFrame"] tbody tr:nth-child(even) td,
    .stDataFrame tbody tr:nth-child(even) td {{
        background-color: {_bg3} !important;
    }}
    /* Glide-data-grid (canvas-based table) — set every token it reads */
    [data-testid="stDataFrame"],
    [data-testid="stDataFrameResizable"],
    .stDataFrame,
    .glide-data-grid-container,
    .glide-data-grid {{
        --gdg-text-dark:           {_text} !important;
        --gdg-text-medium:         {_text2} !important;
        --gdg-text-light:          {_text4} !important;
        --gdg-bg-cell:             {_bg2} !important;
        --gdg-bg-cell-medium:      {_bg3} !important;
        --gdg-bg-header:           {_bg3} !important;
        --gdg-bg-header-has-focus: {_bg4} !important;
        --gdg-bg-header-hovered:   {_bg4} !important;
        --gdg-border-color:        {_border} !important;
        --gdg-horizontal-border-color: {_border} !important;
        --gdg-accent-color:        #6366F1 !important;
        --gdg-accent-light:        rgba(99,102,241,0.1) !important;
        background-color:          {_bg2} !important;
        color:                     {_text} !important;
    }}
    /* The wrapper div Streamlit puts around the canvas */
    [data-testid="stDataFrame"] > div,
    [data-testid="stDataFrameResizable"] > div {{
        background-color: {_bg2} !important;
    }}
    /* Fallback for legacy non-canvas tables */
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th,
    [data-testid="stDataFrameResizable"] td, [data-testid="stDataFrameResizable"] th {{
        color: {_text} !important;
        background-color: transparent !important;
    }}

    /* ── Multiselect tags ── */
    span[data-baseweb="tag"] {{
        background-color: rgba(99,102,241,0.12) !important;
        color: {_text} !important;
        border: 1px solid rgba(99,102,241,0.2) !important;
    }}
    span[data-baseweb="tag"] span {{ color: {_text} !important; }}

    /* ── Caption / helper text ── */
    .stCaption p, [data-testid="stCaptionContainer"] p,
    small, .stMarkdown small {{ color: {_text2} !important; }}

    /* ── Alerts / info boxes ── */
    .stAlert {{
        background-color: {_bg2} !important;
        border: 1px solid {_alert_border} !important;
        border-radius: 10px !important;
        color: {_text} !important;
    }}
    .stAlert p {{ color: {_text3} !important; }}

    /* ── Plotly chart backgrounds ── */
    .js-plotly-plot .plotly, .js-plotly-plot .plotly .bg {{
        background: transparent !important;
    }}

    /* ── Sidebar nav dropdown ── */
    .st-jump-menu {{ position: relative; display: inline-block; width: 100%; margin-bottom: 24px; }}
    .st-jump-btn {{
        background-color: {_jump_bg}; color: {_text};
        padding: 12px 16px; font-size: 0.9rem; font-weight: 600;
        border: 1px solid {_border}; border-radius: 8px;
        cursor: pointer; width: 100%; text-align: left;
        display: flex; justify-content: space-between; align-items: center;
        transition: border-color 0.2s;
    }}
    .st-jump-btn::after {{ content: "▼"; font-size: 0.7rem; color: {_text2}; }}
    .st-jump-content {{
        display: none; position: absolute; background-color: {_jump_content_bg};
        min-width: 100%; box-shadow: 0 8px 24px rgba(99,102,241,0.12);
        z-index: 10000; border: 1px solid #6366F1; border-radius: 8px;
        margin-top: 4px; max-height: 400px; overflow-y: auto;
    }}
    .st-jump-content a {{
        color: {_text2}; padding: 12px 16px; text-decoration: none;
        display: block; font-size: 0.85rem; font-weight: 500;
        border-bottom: 1px solid {_border2};
    }}
    .st-jump-content a:last-child {{ border-bottom: none; }}
    .st-jump-content a:hover {{
        background-color: rgba(99,102,241,0.1); color: {_text};
    }}
    .st-jump-menu:hover .st-jump-content {{ display: block; }}
    .st-jump-menu:hover .st-jump-btn {{ border-color: #6366F1; }}

    /* ── Theme toggle button ── */
    .theme-toggle-fixed {{
        position: fixed; top: 12px; right: 18px; z-index: 99999;
    }}
    .theme-toggle-fixed button {{
        background: {_toggle_bg} !important;
        color: {_toggle_color} !important;
        border: 1px solid {_border} !important;
        border-radius: 20px !important;
        padding: 4px 14px !important;
        font-size: 1rem !important;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(99,102,241,0.15);
        font-family: 'Inter', sans-serif;
    }}
    .theme-toggle-fixed button:hover {{
        box-shadow: 0 4px 12px rgba(99,102,241,0.3);
        border-color: #6366F1 !important;
    }}

    .spacer {{ margin-top: 24px; }}

    /* ── General buttons ── */
    .stButton > button,
    div[data-testid="stButton"] > button,
    button[kind="secondary"],
    button[kind="tertiary"] {{
        background-color: {_btn_bg} !important;
        color: {_btn_color} !important;
        border: 1px solid {_btn_border} !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        transition: background-color 0.15s, border-color 0.15s, box-shadow 0.15s !important;
    }}
    .stButton > button:hover,
    div[data-testid="stButton"] > button:hover {{
        background-color: {_btn_bg_hover} !important;
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.18) !important;
        color: {_btn_color} !important;
    }}
    .stButton > button:active,
    div[data-testid="stButton"] > button:active {{
        background-color: {_btn_bg_hover} !important;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 16px; border-bottom: 1px solid {_tab_border};
        background-color: transparent !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {_text2} !important; font-weight: 500;
        padding: 8px 16px; border-radius: 8px 8px 0 0;
        background-color: transparent !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: {_text} !important;
        border-bottom: 2px solid #6366F1 !important;
        background: linear-gradient(180deg, rgba(99,102,241,0) 0%, rgba(99,102,241,0.08) 100%) !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background-color: transparent !important;
        padding-top: 16px;
    }}
</style>
""", unsafe_allow_html=True)

# Theme toggle — styled via CSS to appear fixed top-right
st.markdown(f"""
<style>
div[data-testid="stButton"]:has(button[key="toggle_theme"]) {{
    position: fixed !important;
    top: 12px !important;
    right: 18px !important;
    z-index: 99999 !important;
    width: auto !important;
}}
div[data-testid="stButton"]:has(button[key="toggle_theme"]) button {{
    background: {_toggle_bg} !important;
    color: {_toggle_color} !important;
    border: 1px solid {_border} !important;
    border-radius: 20px !important;
    padding: 4px 16px !important;
    font-size: 1rem !important;
    min-width: 0 !important;
    width: auto !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
}}
div[data-testid="stButton"]:has(button[key="toggle_theme"]) button:hover {{
    border-color: #6366F1 !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.3) !important;
}}
</style>
""", unsafe_allow_html=True)

# Inject global styles targeting body-level Base Web popovers (teleport outside .stApp)
st.markdown(f"""
<style>
/* Base Web popovers render at document.body — must be global, not scoped */
body div[data-baseweb="popover"],
body div[data-baseweb="menu"],
body ul[data-baseweb="menu"],
body [data-baseweb="select-dropdown"] {{
    background-color: {_bg2} !important;
    border: 1px solid {_border_card} !important;
    border-radius: 10px !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.14) !important;
    color: {_text} !important;
}}
body div[data-baseweb="popover"] *,
body div[data-baseweb="menu"] *,
body ul[data-baseweb="menu"] * {{
    background-color: transparent !important;
    color: {_text} !important;
}}
body li[role="option"] {{
    background-color: {_bg2} !important;
    color: {_text} !important;
}}
body li[role="option"]:hover {{
    background-color: {_bg3} !important;
    color: {_text} !important;
}}
body li[aria-selected="true"] {{
    background-color: rgba(99,102,241,0.15) !important;
    color: {_text} !important;
}}
/* Selectbox trigger box */
body div[data-baseweb="select"] > div {{
    background-color: {_input_bg} !important;
    border-color: {_input_border} !important;
}}
body div[data-baseweb="select"] span,
body div[data-baseweb="select"] p,
body div[data-baseweb="select"] input {{
    color: {_text} !important;
    background-color: transparent !important;
}}
body div[data-baseweb="select"] svg {{ fill: {_text2} !important; }}
/* Multiselect tags in body */
body span[data-baseweb="tag"] {{
    background-color: rgba(99,102,241,0.12) !important;
    color: {_text} !important;
    border: 1px solid rgba(99,102,241,0.2) !important;
}}
body span[data-baseweb="tag"] span {{ color: {_text} !important; }}
</style>
""", unsafe_allow_html=True)

if st.button(_theme_icon, key="toggle_theme", help="Toggle dark / light mode"):
    st.session_state["dark_mode"] = not _dark
    st.rerun()



# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING & CLEANING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner="Loading data from bucket…")
def load_bucket_data(exact_pages: bool = False) -> pd.DataFrame:
    """Load all student records from MinIO bucket.

    exact_pages=True downloads every PDF to count pages precisely (slow, one-time).
    exact_pages=False uses the persistent cache when available and estimates otherwise.
    """
    s3 = _s3()
    page_cache = _load_page_cache()
    cache_dirty = False

    # Single listing pass: collect JSON keys + PDF sizes
    json_keys: list[str] = []
    pdf_sizes: dict[str, int] = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=MINIO_BUCKET, Prefix=MINIO_PREFIX):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            if k.endswith(".json"):
                json_keys.append(k)
            elif k.endswith(".pdf"):
                pdf_sizes[k] = obj["Size"]

    rows = []
    for key in json_keys:
        try:
            meta = _json.loads(
                s3.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()
            )
        except Exception:
            continue

        pdf_key   = key[:-5] + ".pdf"
        pdf_size  = pdf_sizes.get(pdf_key, 0)
        if exact_pages and pdf_key not in page_cache:
            cache_dirty = True
        num_pages = _count_pdf_pages(s3, pdf_key, pdf_size, page_cache, exact=exact_pages)

        grade     = meta.get("grade")
        state_raw = str(meta.get("state") or "").lower().strip()
        lang_prim = str(meta.get("language_primary") or "").strip().title()

        rows.append({
            "student_name":          str(meta.get("student_name") or "not mentioned").strip(),
            "student_id":            str(meta.get("student_id")   or ""),
            "unique_file_id":        str(meta.get("unique_file_id") or ""),
            "school_id":             str(meta.get("school_id")    or ""),
            "gender":                str(meta.get("gender")        or "not mentioned").lower().strip(),
            "class":                 int(grade) if grade else None,
            "class_level":           CLASS_LEVEL_FROM_GRADE.get(int(grade), "Unknown") if grade else "Unknown",
            "school_name":           str(meta.get("school_name")   or "").strip(),
            "school_type":           str(meta.get("school_type")   or "").strip(),
            "board":                 ("not mentioned" if str(meta.get("board") or "").lower().strip() in ("", "unknown", "none") else str(meta.get("board")).lower().strip()),
            "block":                 ("not mentioned" if str(meta.get("city_town_village") or "").lower().strip() in ("", "unknown", "none") else str(meta.get("city_town_village")).lower().strip()),
            "district":              str(meta.get("district")      or "").strip().title(),
            "state":                 state_raw.replace("_", " ").title() or "Unknown",
            "regional_language":     lang_prim or STATE_TO_LANGUAGE.get(state_raw, "Unknown"),
            "medium_of_instruction": str(meta.get("medium_of_instruction") or "not mentioned").strip().title(),
            "subject":               str(meta.get("subject")       or "").lower().strip(),
            "sample_type":           str(meta.get("source_type")   or "").lower().strip(),
            "num_pages":             num_pages,
            "date":                  pd.to_datetime(meta.get("uploaded_at"), errors="coerce", utc=True),
            "rural_urban":           str(meta.get("rural_urban")   or "").strip().title(),
            "aspirational_district": meta.get("aspirational_district", False),
            "curriculum_type":       str(meta.get("curriculum_type") or "").strip(),
            "performance_group":     str(meta.get("performance_group") or "").strip() or "Not Mentioned",
            "capture_device":        str(meta.get("capture_device") or "").strip(),
            "orientation":           str(meta.get("orientation")   or "").strip(),
            "handedness":            ("not mentioned" if str(meta.get("handedness") or "").lower().strip() in ("", "unknown", "none", "null") else str(meta.get("handedness")).lower().strip()),
            "handwritten_or_handdrawn": str(meta.get("handwritten_or_handdrawn") or "").lower().strip(),
            "printed":               str(meta.get("printed")       or "").lower().strip(),
            "mixed_content":         str(meta.get("mixed_content")  or "").lower().strip(),
            "rotation":              str(meta.get("rotation")       or "").lower().strip(),
            "distributor":           (lambda v: v.split("@")[0].strip() if "@" in v else v)(str(meta.get("distributor") or meta.get("uploaded_by") or meta.get("collector_name") or meta.get("data_collector") or "Not Mentioned").strip()),
            "pdf_key":               pdf_key,
        })

    if cache_dirty:
        _save_page_cache(page_cache)

    if not rows:
        cols = ["student_name", "gender", "class", "class_level", "school_name",
                "board", "block", "district", "state", "regional_language",
                "medium_of_instruction", "subject", "sample_type", "num_pages",
                "date", "subject_category"]
        return pd.DataFrame(columns=cols)

    data = pd.DataFrame(rows)

    # Normalize via maps (values already lowercase from above)
    def _map_subject(raw: str) -> str:
        mapped = SUBJECT_MAP.get(str(raw).lower().strip())
        if mapped:
            return mapped
        fuzzy = fuzzy_subject(str(raw).replace("_", " "))
        return fuzzy if fuzzy else "Other"

    data["subject"] = data["subject"].apply(_map_subject)
    data["gender"]      = data["gender"].map(GENDER_MAP).fillna("Not Mentioned")
    _board_valid = set(BOARD_MAP.values())
    _b = data["board"].str.lower().str.strip()
    data["board"] = (
        data["board"].where(data["board"].isin(_board_valid))
        .fillna(data["board"].map(BOARD_MAP))
        .fillna(_b.map(BOARD_MAP))
        .fillna(_b.str.replace(" ", "_", regex=False).map(BOARD_MAP))
        .fillna("Other")
    )
    data["block"]       = (
        data["block"].map(BLOCK_MAP)
        .fillna(data["block"].str.replace("_", " ").str.title())
    )
    data["sample_type"] = (
        data["sample_type"].map(SAMPLE_TYPE_MAP)
        .fillna(data["sample_type"].str.replace("_", " ").str.title())
    )

    data["school_name"] = data["school_name"].apply(
        lambda x: SCHOOL_NORMALIZATIONS.get(str(x).strip().lower(), str(x).strip().title())
    )
    data["subject_category"] = data["subject"].map(SUBJ_CAT_MAP).fillna("Other")
    return data


# ── Load targets from targets.json ───────────────────────────────────────────
# Edit targets.json to change phase1_total_pages, per_language_pages, or participant counts.
# Each language has a flat target of per_language_pages (default 2L).
# Class-level split within each language uses enrollment weights from language_participants.
_TARGETS_FILE = Path(__file__).parent / "targets.json"
_raw = _json.loads(_TARGETS_FILE.read_text())

_PHASE1_TOTAL_PAGES_FULL = _raw["phase1_total_pages"]   # e.g. 20_00_000
_PER_LANG_PAGES = _raw.get("per_language_pages", 200_000)  # flat 2L per language
_PG_PER = _raw["pg_per_participant"]                    # {level: pages}
_LANG_PARTICIPANTS = _raw["language_participants"]       # {lang: {level: n}}

_LEVELS = ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)")
_N_LEVELS = len(_LEVELS)

LANGUAGE_SPECIFIC_TARGETS = {}
for _lang, _lvls in _LANG_PARTICIPANTS.items():
    # Each language: flat 2L total, split equally across 3 class levels
    _lang_total_target = _PER_LANG_PAGES
    _lvl_pages_each = round(_lang_total_target / _N_LEVELS)  # ~66,667 per level

    _lang_entry = {"total": _lang_total_target}
    for _lvl in _LEVELS:
        _pg_per = _PG_PER[_lvl]  # 50 pages/student
        _lang_entry[_lvl] = {
            "pages": _lvl_pages_each,
            "participants": round(_lvl_pages_each / _pg_per),  # ~1,333
            "pg_per_participant": _pg_per,
        }
    LANGUAGE_SPECIFIC_TARGETS[_lang] = _lang_entry


# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════

CACHE_PARQUET  = Path(__file__).parent / "data_cache.parquet"
LAST_UPDATED   = Path(__file__).parent / ".last_updated.json"


@st.cache_data
def load_from_cache(mtime: float) -> pd.DataFrame:
    """Read the parquet file. mtime param busts cache whenever the file changes."""
    return pd.read_parquet(CACHE_PARQUET)


def _last_updated_str() -> str:
    try:
        meta = _json.loads(LAST_UPDATED.read_text())
        ts = pd.to_datetime(meta["last_updated"]).tz_convert("Asia/Kolkata")
        return ts.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return "unknown"


# Prefer cached parquet (written by cron); fall back to live bucket load
if CACHE_PARQUET.exists():
    _exact = st.session_state.pop("exact_pages", False)
    if _exact:
        df = load_bucket_data(exact_pages=True)
    else:
        df = load_from_cache(CACHE_PARQUET.stat().st_mtime)
    _data_source = f"Cache (updated {_last_updated_str()})"
else:
    _exact = st.session_state.pop("exact_pages", False)
    df = load_bucket_data(exact_pages=_exact)
    _data_source = "Live bucket (no cache yet — run fetch_data.py)"

# Ensure pdf_key and distributor always exist (may be missing from older parquet cache)
if "pdf_key" not in df.columns:
    df["pdf_key"] = ""
if "distributor" not in df.columns:
    df["distributor"] = "Not Mentioned"

# Backfill columns added after parquet was originally written
for _col in ("handwritten_or_handdrawn", "printed", "mixed_content", "rotation"):
    if _col not in df.columns:
        df[_col] = ""

# Re-apply board normalisation in case parquet was built before current BOARD_MAP
_board_valid = set(BOARD_MAP.values())
_b = df["board"].str.lower().str.strip()
df["board"] = (
    df["board"].where(df["board"].isin(_board_valid))   # already a short name → keep
    .fillna(df["board"].map(BOARD_MAP))                  # raw slug key → map
    .fillna(_b.map(BOARD_MAP))                           # lowercased
    .fillna(_b.str.replace(" ", "_", regex=False).map(BOARD_MAP))  # spaces→underscores
    .fillna("Other")
)

# Re-apply subject normalisation so cached parquet always reflects current mappings
_already_mapped = set(SUBJ_CAT_MAP.keys())

def _remap_subject(val: str) -> str:
    # If already a known mapped value (canonical or granular), keep it
    if val in _already_mapped:
        return val
    mapped = SUBJECT_MAP.get(str(val).lower().strip())
    if mapped:
        return mapped
    fuzzy = fuzzy_subject(str(val).replace("_", " "))
    return fuzzy if fuzzy else "Other"

df["subject"] = df["subject"].apply(_remap_subject)
df["subject_category"] = df["subject"].map(SUBJ_CAT_MAP).fillna("Other")

# LANGUAGE_SPECIFIC_TARGETS is defined as a constant above (no external file needed)

# ── Aspirational Districts mapping (GoI list) ─────────────────────────────────
_ASPIRATIONAL_DISTRICTS: dict[str, set[str]] = {
    "haryana":           {"mewat", "nuh"},
    "himachal pradesh":  {"chamba"},
    "jammu & kashmir":   {"baramulla", "kupwara"},
    "jammu and kashmir": {"baramulla", "kupwara"},
    "punjab":            {"firozpur", "moga"},
    "uttarakhand":       {"haridwar", "udham singh nagar"},
    "uttar pradesh":     {"bahraich", "balrampur", "chandauli", "chitrakoot",
                          "fatehpur", "shrawasti", "siddharthnagar", "sonbhadra"},
    "bihar":             {"araria", "aurangabad", "banka", "begusarai", "gaya",
                          "jamui", "katihar", "khagaria", "muzaffarpur", "nawada",
                          "purnia", "sheikhpura", "sitamarhi"},
    "jharkhand":         {"bokaro", "chatra", "dumka", "garhwa", "giridih", "godda",
                          "gumla", "hazaribagh", "khunti", "latehar", "lohardaga",
                          "pakur", "palamu", "pashchimi singhbhum", "purbi singhbhum",
                          "ramgarh", "ranchi", "sahibganj", "simdega"},
    "odisha":            {"balangir", "dhenkanal", "gajapati", "kalahandi", "kandhamal",
                          "koraput", "malkangiri", "nabarangpur", "nuapada", "rayagada"},
    "west bengal":       {"birbhum", "dakshin dinajpur", "nadia", "murshidabad", "maldah"},
    "chhattisgarh":      {"bastar", "bijapur", "dantewada", "kanker", "kondagaon",
                          "korba", "mahasamund", "narayanpur", "rajnandgaon", "sukma"},
    "madhya pradesh":    {"barwani", "chhatarpur", "damoh", "guna", "khandwa",
                          "rajgarh", "singrauli", "vidisha"},
    "gujarat":           {"dahod", "narmada"},
    "maharashtra":       {"gadchiroli", "nandurbar", "osmanabad", "dharashiv", "washim"},
    "rajasthan":         {"baran", "dhaulpur", "jaisalmer", "karauli", "sirohi"},
    "andhra pradesh":    {"alluri sitharama raju", "parvathipuram manyam", "y.s.r. kadapa",
                          "ysr kadapa"},
    "karnataka":         {"raichur", "yadgir"},
    "kerala":            {"wayanad"},
    "tamil nadu":        {"ramanathapuram", "virudhunagar"},
    "telangana":         {"asifabad", "kumuram bheem", "bhadradri kothagudem",
                          "jayashankar bhupalpally"},
    "arunachal pradesh": {"namsai"},
    "assam":             {"baksa", "barpeta", "darrang", "dhubri", "goalpara",
                          "hailakandi", "udalguri"},
    "manipur":           {"chandel"},
    "meghalaya":         {"ribhoi"},
    "mizoram":           {"mamit"},
    "nagaland":          {"kiphire"},
    "sikkim":            {"soreng", "west sikkim"},
    "tripura":           {"dhalai"},
}


def _is_aspirational(state: str, district: str) -> bool:
    s = str(state).lower().strip()
    d = str(district).lower().strip()
    return d in _ASPIRATIONAL_DISTRICTS.get(s, set())


# Override aspirational_district using the canonical GoI mapping
df["aspirational_district"] = df.apply(
    lambda r: _is_aspirational(r["state"], r["district"]), axis=1
)

# Pre-compute lookup for UI: which states have aspirational districts and which districts
_ASPIR_STATES_TITLE = {s.title(): {d.title() for d in ds} for s, ds in _ASPIRATIONAL_DISTRICTS.items()}

# ── Bind chart_layout and _bar_textfont to current theme ──────────────────────
_theme = dict(dark=_dark, text=_text, text2=_text2, text3=_text3,
              bg2=_bg2, border=_border, border_card=_border_card,
              progress_track=_progress_track)
chart_layout, _bar_textfont = make_chart_layout(_theme)
_chart_text = _text2 if _dark else _text   # mirrors make_chart_layout logic


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

NAV_SECTIONS = [
    "Overview",
    "Phase 1 Targets vs Achieved",
    "State Level Analysis",
    "District Level Analysis",
    "Block-Level Analysis",
    "School Statistics",
    "Class & Subject Analysis",
    "Subject & Gender Coverage by Class Level",
    "Student Multi-Subject Coverage",
    "Pages per Record Distribution",
    "Content Quality",
    "Distributor Stats",
    "Raw Data Explorer",
]

_days_left = (pd.Timestamp("2026-05-31", tz="Asia/Kolkata") - pd.Timestamp.now(tz="Asia/Kolkata")).days

with st.sidebar:
    st.markdown("## OCR-VS")
    st.markdown("Data Collection Monitor")
    st.caption(f"Data: {_data_source}")
    _deadline_color = "#F43F5E" if _days_left <= 14 else "#F59E0B" if _days_left <= 30 else "#10B981"
    st.markdown(
        f'<div style="background:{_bg2}; border:1px solid {_border}; border-radius:10px; padding:10px 14px; margin-bottom:8px;">'
        f'<div style="font-size:0.7rem; text-transform:uppercase; letter-spacing:1px; color:{_text2}; font-weight:600;">Phase 1 Deadline</div>'
        f'<div style="font-size:1.05rem; font-weight:700; color:{_text}; margin-top:2px;">31 May 2026</div>'
        f'<div style="font-size:0.85rem; font-weight:600; color:{_deadline_color}; margin-top:2px;">{_days_left} days remaining</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    col_r1, col_r2 = st.columns(2)
    if col_r1.button("Refresh", use_container_width=True, help="Reload from cache (written by cron every 6 h)"):
        st.cache_data.clear()
        st.rerun()
    if col_r2.button("Recount Pages", use_container_width=True, help="Download PDFs for exact page counts (slow, one-time)"):
        st.cache_data.clear()
        st.session_state["exact_pages"] = True
        st.rerun()
    
    dropdown_links = "".join([f'<a href="#{s.lower().replace(" ", "-").replace("&", "and")}">{s}</a>' for s in NAV_SECTIONS])
    st.html(f"""
    <div class="st-jump-menu">
        <div class="st-jump-btn">Jump to Section...</div>
        <div class="st-jump-content">
            {dropdown_links}
        </div>
    </div>
    """)
    st.markdown("---")

    sel_board  = st.selectbox("Board", ["All"] + sorted(df["board"].unique().tolist()))
    sel_level  = st.selectbox("Class Level", ["All"] + sorted(df["class_level"].unique().tolist()))
    sel_subj   = st.selectbox("Subject Category", ["All"] + sorted(df["subject_category"].unique().tolist()))
    sel_gender = st.selectbox("Gender", ["All"] + sorted(df["gender"].unique().tolist()))
    sel_state  = st.selectbox("State", ["All"] + sorted([s for s in df["state"].unique().tolist() if s and s != "Unknown"]))
    sel_block  = st.selectbox("Block", ["All"] + sorted(df["block"].unique().tolist()))

    st.markdown("---")
    st.markdown("**Date Range**")
    _df_dates = df["date"].dropna()
    _min_date = _df_dates.min().date() if len(_df_dates) else pd.Timestamp("2024-01-01").date()
    _max_date = _df_dates.max().date() if len(_df_dates) else pd.Timestamp.now().date()
    sel_date_from = st.date_input("From", value=_min_date, key="date_from")
    sel_date_to   = st.date_input("To",   value=_max_date, key="date_to")

    st.markdown("---")
    st.caption("Set any filter to 'All' to reset it.")

# Apply filters
filtered = df.copy()
for col, val in [("board", sel_board), ("class_level", sel_level),
                  ("subject_category", sel_subj), ("gender", sel_gender),
                  ("state", sel_state), ("block", sel_block)]:
    if val != "All":
        filtered = filtered[filtered[col] == val]

# Date filter
if filtered["date"].notna().any():
    _from_ts = pd.Timestamp(sel_date_from, tz="UTC")
    _to_ts   = pd.Timestamp(sel_date_to,   tz="UTC") + pd.Timedelta(days=1)
    filtered = filtered[(filtered["date"] >= _from_ts) & (filtered["date"] < _to_ts)]

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

# ── Top-right toggle buttons ─────────────────────────────────────────────────
if "show_sample_checker" not in st.session_state:
    st.session_state["show_sample_checker"] = False
if "show_summary" not in st.session_state:
    st.session_state["show_summary"] = False

_header_col, _btn_col = st.columns([8, 2])
with _header_col:
    st.html("""
<div style="padding: 8px 0 4px 0;">
    <div class="dashboard-title">OCR-VS Dashboard</div>
    <div class="dashboard-subtitle">
        Real-time tracking &amp; monitoring of handwriting data collection across schools.
    </div>
</div>
""")
with _btn_col:
    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    _sc_open  = st.session_state["show_sample_checker"]
    _sum_open = st.session_state["show_summary"]

    # Styles for both buttons
    _sc_bg     = "linear-gradient(135deg, #F43F5E 0%, #E11D48 100%)"  if _sc_open  else "linear-gradient(135deg, #818CF8 0%, #A78BFA 100%)"
    _sc_shadow = ("0 4px 20px rgba(244,63,94,0.5)"                    if _sc_open  else "0 4px 20px rgba(129,140,248,0.5)")
    _sc_border = ("1px solid rgba(244,63,94,0.6)"                     if _sc_open  else "1px solid rgba(129,140,248,0.6)")
    _sc_label  = "✕  Close Checker"                                   if _sc_open  else "🔍  Sample Checker"

    _sm_bg     = "linear-gradient(135deg, #F43F5E 0%, #E11D48 100%)"  if _sum_open else "linear-gradient(135deg, #10B981 0%, #059669 100%)"
    _sm_shadow = ("0 4px 20px rgba(244,63,94,0.5)"                    if _sum_open else "0 4px 20px rgba(16,185,129,0.5)")
    _sm_border = ("1px solid rgba(244,63,94,0.6)"                     if _sum_open else "1px solid rgba(16,185,129,0.6)")
    _sm_label  = "✕  Close Detailed View"                             if _sum_open else "📋  Detailed View"

    st.markdown(f"""
<style>
div[data-testid="stButton"]:has(button[key="toggle_sample_checker"]) button {{
    background: {_sc_bg} !important;
    border: {_sc_border} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important; font-size: 0.85rem !important;
    letter-spacing: 0.03em !important; border-radius: 12px !important;
    padding: 10px 16px !important; box-shadow: {_sc_shadow} !important;
    transition: all 0.2s ease !important; text-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}}
div[data-testid="stButton"]:has(button[key="toggle_summary"]) button {{
    background: {_sm_bg} !important;
    border: {_sm_border} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important; font-size: 0.85rem !important;
    letter-spacing: 0.03em !important; border-radius: 12px !important;
    padding: 10px 16px !important; box-shadow: {_sm_shadow} !important;
    transition: all 0.2s ease !important; text-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}}
div[data-testid="stButton"]:has(button[key="toggle_sample_checker"]) button:hover,
div[data-testid="stButton"]:has(button[key="toggle_summary"]) button:hover {{
    filter: brightness(1.12) !important; transform: translateY(-2px) !important;
}}
</style>
""", unsafe_allow_html=True)
    _b1, _b2 = st.columns(2)
    with _b1:
        if st.button(_sm_label, key="toggle_summary", use_container_width=True):
            st.session_state["show_summary"] = not _sum_open
            st.session_state["show_sample_checker"] = False
            st.rerun()
    with _b2:
        if st.button(_sc_label, key="toggle_sample_checker", use_container_width=True):
            st.session_state["show_sample_checker"] = not _sc_open
            st.session_state["show_summary"] = False
            st.rerun()

# ── Sample Checker Panel ──────────────────────────────────────────────────────
if st.session_state["show_sample_checker"]:
    st.markdown('<div class="section-header">🔍 Sample Checker — PDF Viewer</div>', unsafe_allow_html=True)

    def _build_pdf_key(row) -> str:
        """Reconstruct the S3 PDF key from metadata fields using the known folder hierarchy."""
        def _slug(v):
            return str(v or "").lower().strip().replace(" ", "_")

        uid = str(row.get("unique_file_id") or row.get("student_id") or "").strip()
        if not uid:
            return ""

        state       = _slug(row.get("state", ""))
        district    = _slug(row.get("district", ""))
        block       = _slug(row.get("block", ""))
        board       = _slug(row.get("board", ""))
        curriculum  = _slug(row.get("curriculum_type", ""))
        school      = _slug(row.get("school_name", ""))
        medium      = _slug(row.get("medium_of_instruction", ""))
        # map class_level to folder name — match on raw value (any case/spacing)
        _raw_cl = str(row.get("class_level", "") or "").strip().lower()
        cl_map = {
            "primary (1-5)":           "primary",
            "primary":                 "primary",
            "high school (6-8)":       "high_school",
            "high school":             "high_school",
            "secondary (9-10)":        "secondary",
            "secondary":               "secondary",
            "higher secondary (11-12)":"higher_secondary",
            "higher secondary":        "higher_secondary",
        }
        class_level = cl_map.get(_raw_cl, _slug(_raw_cl))
        subject     = _slug(row.get("subject", ""))
        source_type = _slug(row.get("sample_type", ""))

        folder = (
            f"{MINIO_PREFIX}{state}/{district}/{block}/{board}/"
            f"{curriculum}/{school}/{medium}/{class_level}/{subject}/{source_type}/{uid}"
        )
        return f"{folder}/{uid}.pdf"

    _sc_df = df.copy()
    # Only fill in pdf_key where it's missing (old parquet cache); real keys come from the data loader
    _empty_mask = _sc_df["pdf_key"].isna() | (_sc_df["pdf_key"] == "")
    if _empty_mask.any():
        _sc_df.loc[_empty_mask, "pdf_key"] = _sc_df[_empty_mask].apply(_build_pdf_key, axis=1)

    # ── Filters ───────────────────────────────────────────────────────────
    _sc_f1, _sc_f2, _sc_f3, _sc_f4 = st.columns(4)

    _dist_info = (
        _sc_df[_sc_df["distributor"].notna() & (_sc_df["distributor"] != "Not Mentioned")]
        .groupby("distributor")
        .agg(state=("state", "first"), district=("district", "first"))
        .reset_index()
    )
    _dist_opts_map = {"All": "All"}
    for _, _dr in _dist_info.iterrows():
        _label = f"({_dr['distributor']}, {_dr['state']}, {_dr['district']})"
        _dist_opts_map[_label] = _dr["distributor"]
    _sel_dist_label = _sc_f1.selectbox("Distributor", list(_dist_opts_map.keys()), key="sc_dist")
    _sel_dist = _dist_opts_map[_sel_dist_label]
    if _sel_dist != "All":
        _sc_df = _sc_df[_sc_df["distributor"] == _sel_dist]

    _state_opts = ["All"] + sorted([s for s in _sc_df["state"].unique() if s and s != "Unknown"])
    _sel_sc_state = _sc_f2.selectbox("State", _state_opts, key="sc_state")
    if _sel_sc_state != "All":
        _sc_df = _sc_df[_sc_df["state"] == _sel_sc_state]

    _district_opts = ["All"] + sorted([d for d in _sc_df["district"].unique() if d and d not in ("", "Unknown")])
    _sel_sc_dist = _sc_f3.selectbox("District", _district_opts, key="sc_district")
    if _sel_sc_dist != "All":
        _sc_df = _sc_df[_sc_df["district"] == _sel_sc_dist]

    _block_opts = ["All"] + sorted([b for b in _sc_df["block"].unique() if b and b != "Not Mentioned"])
    _sel_sc_block = _sc_f4.selectbox("Block / City / Village", _block_opts, key="sc_block")
    if _sel_sc_block != "All":
        _sc_df = _sc_df[_sc_df["block"] == _sel_sc_block]

    _sc_f5, _sc_f6, _sc_f7, _sc_f8 = st.columns(4)

    _school_opts = ["All"] + sorted([s for s in _sc_df["school_name"].unique() if s])
    _sel_sc_school = _sc_f5.selectbox("School", _school_opts, key="sc_school")
    if _sel_sc_school != "All":
        _sc_df = _sc_df[_sc_df["school_name"] == _sel_sc_school]

    _gender_opts = ["All"] + sorted(_sc_df["gender"].unique().tolist())
    _sel_sc_gender = _sc_f6.selectbox("Gender", _gender_opts, key="sc_gender")
    if _sel_sc_gender != "All":
        _sc_df = _sc_df[_sc_df["gender"] == _sel_sc_gender]

    _subj_opts = ["All"] + sorted([s for s in _sc_df["subject"].unique() if s])
    _sel_sc_subj = _sc_f7.selectbox("Subject", _subj_opts, key="sc_subj")
    if _sel_sc_subj != "All":
        _sc_df = _sc_df[_sc_df["subject"] == _sel_sc_subj]

    _class_opts = ["All"] + sorted([str(int(c)) for c in _sc_df["class"].dropna().unique()])
    _sel_sc_class = _sc_f8.selectbox("Class", _class_opts, key="sc_class")
    if _sel_sc_class != "All":
        _sc_df = _sc_df[_sc_df["class"] == int(_sel_sc_class)]

    _sc_fa, _sc_fb, _sc_fc, _ = st.columns([1, 1, 1, 1])
    _sc_dates = _sc_df["date"].dropna()
    _sc_min = _sc_dates.min().date() if len(_sc_dates) else pd.Timestamp("2024-01-01").date()
    _sc_max = _sc_dates.max().date() if len(_sc_dates) else pd.Timestamp.now().date()
    _sel_sc_from = _sc_fa.date_input("From", value=_sc_min, key="sc_date_from")
    _sel_sc_to   = _sc_fb.date_input("To",   value=_sc_max, key="sc_date_to")
    if _sc_df["date"].notna().any():
        _sc_df = _sc_df[
            (_sc_df["date"] >= pd.Timestamp(_sel_sc_from, tz="UTC")) &
            (_sc_df["date"] <  pd.Timestamp(_sel_sc_to,   tz="UTC") + pd.Timedelta(days=1))
        ]

    _name_opts = ["All"] + sorted([n for n in _sc_df["student_name"].str.title().unique() if n and n.lower() not in ("", "not mentioned")])
    _sel_sc_name = _sc_fc.selectbox("Student Name", _name_opts, key="sc_name")
    if _sel_sc_name != "All":
        _sc_df = _sc_df[_sc_df["student_name"].str.title() == _sel_sc_name]

    n_total = len(_sc_df)
    _SC_PAGE_SIZE = 10

    if "sc_page" not in st.session_state:
        st.session_state["sc_page"] = 0
    if "sc_view_idx" not in st.session_state:
        st.session_state["sc_view_idx"] = None

    # Reset to page 0 when filters change
    _sc_df_reset = _sc_df.reset_index(drop=True)

    st.markdown(
        f"<div style='color:{_text2};font-size:0.8rem;margin:8px 0 12px;'>"
        f"<b style='color:{_text3};'>{n_total:,}</b> records match</div>",
        unsafe_allow_html=True,
    )

    if n_total == 0:
        st.info("No records match the selected filters.")
    else:
        _n_pages = max(1, (n_total + _SC_PAGE_SIZE - 1) // _SC_PAGE_SIZE)
        _cur_page = min(st.session_state["sc_page"], _n_pages - 1)
        _page_start = _cur_page * _SC_PAGE_SIZE
        _page_rows = _sc_df_reset.iloc[_page_start: _page_start + _SC_PAGE_SIZE]

        # ── PDF viewer (shown above table when a record is selected) ───────
        _view_idx = st.session_state.get("sc_view_idx")
        if _view_idx is not None and _view_idx < n_total:
            _sc_row = _sc_df_reset.iloc[_view_idx]
            _pdf_key_val = _sc_row["pdf_key"]
            _cls_v = int(_sc_row["class"]) if _sc_row["class"] and not pd.isna(_sc_row["class"]) else "?"

            st.markdown(f"<div style='height:1px;background:{_border_card};margin:8px 0 12px;'></div>", unsafe_allow_html=True)
            _pdf_close_col, _ = st.columns([1, 8])
            if _pdf_close_col.button("✕", key="sc_pdf_close", help="Close PDF"):
                st.session_state["sc_view_idx"] = None
                st.rerun()
            st.markdown(f"""
<div style='background:{_bg2};border:1px solid {_border_card};
     border-radius:10px;padding:10px 16px;margin:10px 0;
     display:grid;grid-template-columns:repeat(4,1fr);gap:8px;'>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Student</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{str(_sc_row["student_name"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Class · Subject</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>Class {_cls_v} · {str(_sc_row["subject"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>School</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{str(_sc_row["school_name"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>District · Block</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{_sc_row["district"]} · {str(_sc_row["block"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Gender</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{str(_sc_row["gender"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Pages</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{int(_sc_row["num_pages"])}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Date</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{str(_sc_row["date"])[:10] if pd.notna(_sc_row["date"]) else "—"}</div></div>
  <div><div style='font-size:0.6rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Sample Type</div>
       <div style='font-size:0.82rem;font-weight:600;color:{_text3};'>{str(_sc_row["sample_type"]).title()}</div></div>
</div>
""", unsafe_allow_html=True)

            with st.spinner("Fetching file…"):
                _pdf_url, _pdf_err, _found_ext = _presigned_url(_pdf_key_val, expires=1800)

            if _pdf_url and _found_ext == "pdf":
                st.markdown(f"""
<div style='background:{_bg3};border:1px solid {_border_card};
     border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.15);'>
  <div style='background:{_bg2};padding:8px 14px;display:flex;
       align-items:center;justify-content:space-between;border-bottom:1px solid {_border2};'>
    <span style='font-size:0.75rem;font-weight:600;color:{_text2};'>📄 {_pdf_key_val.split("/")[-1]}</span>
    <a href="{_pdf_url}" target="_blank"
       style='font-size:0.72rem;color:#818CF8;text-decoration:none;font-weight:600;
              background:rgba(129,140,248,0.1);padding:3px 10px;border-radius:6px;
              border:1px solid rgba(129,140,248,0.3);'>↗ Open full screen</a>
  </div>
  <iframe src="{_pdf_url}" width="100%" height="900"
          style="border:none;display:block;background:#fff;"></iframe>
</div>
""", unsafe_allow_html=True)
            elif _pdf_url and _found_ext in ("png", "jpg", "jpeg", "tiff", "tif"):
                st.warning(f"PDF not available — showing image file (.{_found_ext}) instead.")
                st.markdown(f"""
<div style='background:{_bg3};border:1px solid {_border_card};
     border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.15);'>
  <div style='background:{_bg2};padding:8px 14px;display:flex;
       align-items:center;justify-content:space-between;border-bottom:1px solid {_border2};'>
    <span style='font-size:0.75rem;font-weight:600;color:{_text2};'>🖼 {_pdf_key_val.split("/")[-1].replace(".pdf", f".{_found_ext}")}</span>
    <a href="{_pdf_url}" target="_blank"
       style='font-size:0.72rem;color:#818CF8;text-decoration:none;font-weight:600;
              background:rgba(129,140,248,0.1);padding:3px 10px;border-radius:6px;
              border:1px solid rgba(129,140,248,0.3);'>↗ Open full screen</a>
  </div>
  <img src="{_pdf_url}" style="width:100%;display:block;background:#fff;" />
</div>
""", unsafe_allow_html=True)
            else:
                st.error(f"PDF not found. Key: `{_pdf_key_val}`")
                if _pdf_err:
                    st.caption(f"Error: {_pdf_err}")

            st.markdown(f"<div style='height:1px;background:{_border_card};margin:16px 0 12px;'></div>", unsafe_allow_html=True)

        # ── Paginated table ────────────────────────────────────────────────
        _tbl_cols = ["#", "Student", "Class", "Subject", "Pages", "School", "District", "Date", ""]
        _col_widths = [0.4, 1.2, 0.5, 1, 0.4, 1.4, 1, 0.7, 0.5]
        _hdr_cols = st.columns(_col_widths)
        for _ci, _ch in enumerate(_tbl_cols):
            _hdr_cols[_ci].markdown(
                f"<div style='font-size:0.65rem;font-weight:700;color:{_text2};"
                f"text-transform:uppercase;letter-spacing:.07em;padding:4px 0;'>{_ch}</div>",
                unsafe_allow_html=True)
        st.markdown(f"<div style='height:1px;background:{_border_card};margin-bottom:4px;'></div>", unsafe_allow_html=True)

        for _abs_i, _r in zip(range(_page_start, _page_start + len(_page_rows)), _page_rows.iterrows()):
            _r = _r[1]  # iterrows yields (index, Series)
            _rc = st.columns(_col_widths)
            _cl  = int(_r["class"]) if _r["class"] and not pd.isna(_r["class"]) else "?"
            _dt  = str(_r["date"])[:10] if pd.notna(_r["date"]) else "—"
            _rc[0].markdown(f"<div style='font-size:0.78rem;color:{_text2};padding:6px 0;'>{_abs_i+1}</div>", unsafe_allow_html=True)
            _rc[1].markdown(f"<div style='font-size:0.78rem;color:{_text3};font-weight:600;padding:6px 0;'>{str(_r['student_name']).title()}</div>", unsafe_allow_html=True)
            _rc[2].markdown(f"<div style='font-size:0.78rem;color:{_text3};padding:6px 0;'>{_cl}</div>", unsafe_allow_html=True)
            _rc[3].markdown(f"<div style='font-size:0.78rem;color:{_text3};padding:6px 0;'>{str(_r['subject']).title()}</div>", unsafe_allow_html=True)
            _rc[4].markdown(f"<div style='font-size:0.78rem;color:{_text3};padding:6px 0;'>{int(_r['num_pages'])}</div>", unsafe_allow_html=True)
            _rc[5].markdown(f"<div style='font-size:0.78rem;color:{_text3};padding:6px 0;'>{str(_r['school_name']).title()}</div>", unsafe_allow_html=True)
            _rc[6].markdown(f"<div style='font-size:0.78rem;color:{_text3};padding:6px 0;'>{str(_r['district']).title()}</div>", unsafe_allow_html=True)
            _rc[7].markdown(f"<div style='font-size:0.78rem;color:{_text2};padding:6px 0;'>{_dt}</div>", unsafe_allow_html=True)
            if _rc[8].button("View", key=f"sc_view_{_abs_i}", use_container_width=True):
                st.session_state["sc_view_idx"] = _abs_i
                st.rerun()
            st.markdown(f"<div style='height:1px;background:{_border2};'></div>", unsafe_allow_html=True)

        # ── Pagination controls ────────────────────────────────────────────
        _pg_l, _pg_m, _pg_r = st.columns([1, 2, 1])
        if _pg_l.button("← Prev", key="sc_prev", disabled=_cur_page == 0):
            st.session_state["sc_page"] = _cur_page - 1
            st.session_state["sc_view_idx"] = None
            st.rerun()
        _pg_m.markdown(
            f"<div style='text-align:center;font-size:0.8rem;color:{_text2};padding-top:6px;'>"
            f"Page <b style='color:{_text3};'>{_cur_page+1}</b> of <b style='color:{_text3};'>{_n_pages}</b></div>",
            unsafe_allow_html=True)
        if _pg_r.button("Next →", key="sc_next", disabled=_cur_page >= _n_pages - 1):
            st.session_state["sc_page"] = _cur_page + 1
            st.session_state["sc_view_idx"] = None
            st.rerun()


    st.stop()

# Active filters pill
active = {k: v for k, v in {"Board": sel_board, "Level": sel_level,
          "Subject": sel_subj, "Gender": sel_gender,
          "State": sel_state, "Block": sel_block}.items() if v != "All"}
_date_filtered = (sel_date_from != _min_date or sel_date_to != _max_date)
if active or _date_filtered:
    parts = [f"**{k}:** {v}" for k, v in active.items()]
    if _date_filtered:
        parts.append(f"**Date:** {sel_date_from} → {sel_date_to}")
    st.info("Filters active: " + " &nbsp;|&nbsp; ".join(parts))

# ══════════════════════════════════════════════════════════════════════════════
# 1. KPI OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

total_pages = int(filtered["num_pages"].sum())
total_records = len(filtered)
n_students  = filtered["student_id"].nunique()
n_schools   = filtered["school_name"].nunique()
n_subjects       = filtered["subject"].nunique()
n_subject_levels = filtered.groupby(["subject", "class_level"]).ngroups
n_states    = filtered[~filtered["state"].isin(["Not Mentioned", "Unknown", ""])]["state"].nunique()
n_districts = filtered[~filtered["district"].isin(["Not Mentioned", "Unknown", ""])]["district"].nunique()
n_blocks    = filtered[~filtered["block"].isin(["Not Mentioned", "Unknown", ""])]["block"].nunique()

avg_pg_student      = round(total_pages / n_students, 1)  if n_students else 0
avg_pg_school       = round(total_pages / n_schools, 1)   if n_schools  else 0
avg_students_school = round(n_students  / n_schools, 1)   if n_schools  else 0
avg_pg_record       = round(total_pages / total_records, 1) if total_records else 0
avg_subjects_student = round(total_records / n_students, 1) if n_students else 0

_hero_pct = round(total_pages / _PHASE1_TOTAL_PAGES_FULL * 100, 1)
_hero_clr = "#10B981" if _hero_pct >= 100 else "#F59E0B" if _hero_pct >= 60 else "#F43F5E"
_dl_clr   = "#F43F5E" if _days_left <= 14 else "#F59E0B" if _days_left <= 30 else "#10B981"
n_languages = filtered[~filtered["regional_language"].isin(["Unknown", ""])]["regional_language"].nunique()

# ── Homepage ──────────────────────────────────────────────────────────────────

if not st.session_state.get("show_summary"):
    # Hero sentence
    st.markdown(f"""
<div style='margin:28px 0 20px;line-height:1.6;font-size:1.2rem;font-weight:500;
            color:{_text2};font-family:"Inter",sans-serif;'>
  <span style='font-size:2.6rem;font-weight:900;color:#F9A8D4;
               font-family:"Georgia","Times New Roman",serif;
               letter-spacing:-1.5px;text-shadow:0 0 24px #F9A8D455;'>{total_pages:,}</span>
  <span> pages from </span>
  <span style='font-size:2.6rem;font-weight:900;color:#818CF8;
               font-family:"Courier New","Courier",monospace;
               letter-spacing:-1px;text-shadow:0 0 20px #818CF855;'>{n_students:,}</span>
  <span> students across </span>
  <span style='font-size:2.6rem;font-weight:900;color:#34D399;
               font-family:"Georgia","Times New Roman",serif;
               letter-spacing:-1.5px;text-shadow:0 0 20px #34D39955;'>{n_schools:,}</span>
  <span> schools in </span>
  <span style='font-size:2.6rem;font-weight:900;color:#FBBF24;
               font-family:"Courier New","Courier",monospace;
               letter-spacing:-1px;text-shadow:0 0 20px #FBBF2455;'>{n_states}</span>
  <span> states.</span>
</div>
""", unsafe_allow_html=True)

    # Progress bar
    _bar_filled = min(_hero_pct, 100)
    _deadline_str = pd.Timestamp("2026-05-31", tz="Asia/Kolkata").strftime("%d %b %Y")
    st.markdown(f"""
<div style='margin-bottom:28px;'>
  <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;'>
    <span style='font-size:0.78rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>
      Target &nbsp;<span style='color:{_hero_clr};font-size:1rem;'>{_hero_pct}%</span>
      &nbsp;<span style='color:{_text4};font-weight:400;'>— {total_pages:,} of {_PHASE1_TOTAL_PAGES_FULL:,} pages</span>
    </span>
    <span style='font-size:0.78rem;font-weight:600;color:{_dl_clr};'>
      Phase 1 Deadline: {_deadline_str} &nbsp;·&nbsp; {_days_left}d left
    </span>
  </div>
  <div style='background:rgba(255,255,255,0.08);border-radius:8px;height:14px;overflow:hidden;border:1px solid rgba(255,255,255,0.08);'>
    <div style='width:{_bar_filled:.1f}%;background:linear-gradient(90deg,{_hero_clr}cc,{_hero_clr});
                height:100%;border-radius:8px;box-shadow:0 0 12px {_hero_clr}55;
                transition:width 0.4s ease;'></div>
  </div>
</div>
""", unsafe_allow_html=True)

    # 4 overview cards
    _n_subj_unique = filtered["subject"].nunique()
    _c1, _c2, _c3, _c4 = st.columns(4)

    # ── States card ──
    with _c1:
        _state_rows = (
            filtered[~filtered["state"].isin(["Not Mentioned", "Unknown", ""])]
            .groupby("state")
            .agg(Districts=("district", "nunique"), Blocks=("block", "nunique"))
            .reset_index()
            .rename(columns={"state": "State"})
            .sort_values("State")
        )
        st.markdown(f"""
<div style='background:rgba(129,140,248,0.08);border:1px solid rgba(129,140,248,0.2);
            border-radius:14px;padding:16px 18px 10px;margin-bottom:4px;'>
  <div style='font-size:0.7rem;font-weight:700;color:#818CF8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>States</div>
  <div style='font-size:2rem;font-weight:900;color:{_text};line-height:1;'>{n_states}</div>
  <div style='font-size:0.75rem;color:{_text3};margin-top:2px;'>{n_districts} districts · {n_blocks} blocks</div>
</div>""", unsafe_allow_html=True)
        st.dataframe(
            _state_rows,
            hide_index=True, use_container_width=True, height=min(180, 36 + len(_state_rows) * 35),
            column_config={
                "State":     st.column_config.TextColumn("State"),
                "Districts": st.column_config.NumberColumn("Dist.", format="%d"),
                "Blocks":    st.column_config.NumberColumn("Blocks", format="%d"),
            },
        )
        # State selector + Detailed Stats button
        _avail_states = sorted(_state_rows["State"].tolist())
        if "state_detail_open" not in st.session_state:
            st.session_state["state_detail_open"] = None
        _sel_state_detail = st.selectbox(
            "Select state", ["— select a state —"] + _avail_states,
            key="state_detail_select", label_visibility="collapsed",
        )
        _state_detail_btn = st.button(
            "📊 Detailed Stats →", key="state_detail_btn",
            disabled=(_sel_state_detail == "— select a state —"),
            use_container_width=True,
        )
        if _state_detail_btn and _sel_state_detail != "— select a state —":
            st.session_state["state_detail_open"] = _sel_state_detail
            st.rerun()

    # ── Subjects card ──
    with _c2:
        _subj_rows = (
            filtered.groupby("subject")["num_pages"]
            .sum().sort_values(ascending=False)
            .reset_index()
            .rename(columns={"subject": "Subject", "num_pages": "Pages"})
        )
        st.markdown(f"""
<div style='background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.2);
            border-radius:14px;padding:16px 18px 10px;margin-bottom:4px;'>
  <div style='font-size:0.7rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>Subjects</div>
  <div style='font-size:2rem;font-weight:900;color:{_text};line-height:1;'>{_n_subj_unique}</div>
  <div style='font-size:0.75rem;color:{_text3};margin-top:2px;'>{int(filtered["num_pages"].sum()):,} total pages</div>
</div>""", unsafe_allow_html=True)
        st.dataframe(
            _subj_rows,
            hide_index=True, use_container_width=True, height=min(180, 36 + len(_subj_rows) * 35),
            column_config={
                "Subject": st.column_config.TextColumn("Subject"),
                "Pages":   st.column_config.NumberColumn("Pages", format="%d"),
            },
        )
        if "subject_detail_open" not in st.session_state:
            st.session_state["subject_detail_open"] = False
        if st.button("📊 Detailed Stats →", key="subj_detail_btn", use_container_width=True):
            st.session_state["subject_detail_open"] = not st.session_state["subject_detail_open"]
            st.rerun()

    # ── Students card ──
    with _c3:
        _gender_rows = (
            filtered.groupby("gender")["student_id"]
            .nunique().reset_index()
            .rename(columns={"gender": "Gender", "student_id": "Students"})
            .sort_values("Students", ascending=False)
        )
        st.markdown(f"""
<div style='background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.2);
            border-radius:14px;padding:16px 18px 10px;margin-bottom:4px;'>
  <div style='font-size:0.7rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>Students</div>
  <div style='font-size:2rem;font-weight:900;color:{_text};line-height:1;'>{n_students:,}</div>
  <div style='font-size:0.75rem;color:{_text3};margin-top:2px;'>{n_schools} schools · {round(n_students/n_schools,1) if n_schools else 0} avg/school</div>
</div>""", unsafe_allow_html=True)
        st.dataframe(
            _gender_rows,
            hide_index=True, use_container_width=True, height=min(180, 36 + len(_gender_rows) * 35),
            column_config={
                "Gender":   st.column_config.TextColumn("Gender"),
                "Students": st.column_config.NumberColumn("Students", format="%d"),
            },
        )
        if "students_detail_open" not in st.session_state:
            st.session_state["students_detail_open"] = False
        if st.button("📊 Detailed Stats →", key="students_detail_btn", use_container_width=True):
            st.session_state["students_detail_open"] = not st.session_state["students_detail_open"]
            st.rerun()

    # ── Languages card ──
    with _c4:
        _lang_rows = (
            filtered[~filtered["regional_language"].isin(["Unknown", ""])]
            .groupby("regional_language")["num_pages"]
            .sum().sort_values(ascending=False)
            .reset_index()
            .rename(columns={"regional_language": "Language", "num_pages": "Pages"})
        )
        st.markdown(f"""
<div style='background:rgba(192,132,252,0.08);border:1px solid rgba(192,132,252,0.2);
            border-radius:14px;padding:16px 18px 10px;margin-bottom:4px;'>
  <div style='font-size:0.7rem;font-weight:700;color:#C084FC;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>Languages</div>
  <div style='font-size:2rem;font-weight:900;color:{_text};line-height:1;'>{n_languages}</div>
  <div style='font-size:0.75rem;color:{_text3};margin-top:2px;'>regional languages</div>
</div>""", unsafe_allow_html=True)
        st.dataframe(
            _lang_rows,
            hide_index=True, use_container_width=True, height=min(180, 36 + len(_lang_rows) * 35),
            column_config={
                "Language": st.column_config.TextColumn("Language"),
                "Pages":    st.column_config.NumberColumn("Pages", format="%d"),
            },
        )
        if "lang_detail_open" not in st.session_state:
            st.session_state["lang_detail_open"] = False
        if st.button("📊 Detailed Stats →", key="lang_detail_btn", use_container_width=True):
            st.session_state["lang_detail_open"] = not st.session_state["lang_detail_open"]
            st.rerun()

# ── State Detailed Stats Panel ────────────────────────────────────────────────
if not st.session_state.get("show_summary") and st.session_state.get("state_detail_open"):
    _sd_state = st.session_state["state_detail_open"]
    _sd_df = filtered[filtered["state"] == _sd_state].copy()

    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:24px 0 20px;'>", unsafe_allow_html=True)

    # Close button
    _sdcol, _ = st.columns([2, 6])
    with _sdcol:
        st.markdown(f"<div style='font-size:1.1rem;font-weight:800;color:#818CF8;margin-bottom:8px;'>📍 {_sd_state} — Detailed Stats</div>", unsafe_allow_html=True)
    if st.button("✕ Close", key="close_state_detail"):
        st.session_state["state_detail_open"] = None
        st.rerun()

    _STATE_PAGE_TARGET = round(_PHASE1_TOTAL_PAGES_FULL / 8)  # 20L / 8 states

    # ── Section 1: State progress towards goal ────────────────────────────────
    _sd_pages = int(_sd_df["num_pages"].sum())
    _sd_pct   = round(_sd_pages / _STATE_PAGE_TARGET * 100, 1) if _STATE_PAGE_TARGET else 0
    _sd_clr   = "#10B981" if _sd_pct >= 100 else "#F59E0B" if _sd_pct >= 60 else "#F43F5E"
    _sd_bar   = min(_sd_pct, 100)
    st.markdown(f"""
<div style='margin-bottom:24px;background:rgba(129,140,248,0.06);border:1px solid rgba(129,140,248,0.15);
            border-radius:14px;padding:18px 22px;'>
  <div style='font-size:0.72rem;font-weight:700;color:#818CF8;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;'>
    Progress towards state goal
  </div>
  <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;'>
    <span style='font-size:1.8rem;font-weight:900;color:{_sd_clr};'>{_sd_pages:,}</span>
    <span style='font-size:0.85rem;color:{_text3};'>of <b style='color:{_text};'>{_STATE_PAGE_TARGET:,}</b> target pages &nbsp;·&nbsp;
      <b style='color:{_sd_clr};'>{_sd_pct}%</b></span>
  </div>
  <div style='background:rgba(255,255,255,0.07);border-radius:8px;height:12px;overflow:hidden;'>
    <div style='width:{_sd_bar:.1f}%;background:linear-gradient(90deg,{_sd_clr}99,{_sd_clr});
                height:100%;border-radius:8px;box-shadow:0 0 10px {_sd_clr}55;'></div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Section 2: Pages by class + gender split ──────────────────────────────
    st.markdown(f"<div style='font-size:0.85rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:10px;'>📚 Pages by Class — Gender Split</div>", unsafe_allow_html=True)

    _sd_class = (
        _sd_df[_sd_df["class"].notna()]
        .assign(_cls=_sd_df["class"].astype(int))
        .groupby(["_cls", "gender"])["num_pages"].sum()
        .reset_index()
    )
    _sd_class_all = sorted(_sd_class["_cls"].unique())
    _male_pages   = _sd_class[_sd_class["gender"].str.lower() == "male"].set_index("_cls")["num_pages"]
    _female_pages = _sd_class[_sd_class["gender"].str.lower() == "female"].set_index("_cls")["num_pages"]
    _other_pages  = _sd_class[~_sd_class["gender"].str.lower().isin(["male","female"])].groupby("_cls")["num_pages"].sum()

    _fig_cls = go.Figure()
    _fig_cls.add_trace(go.Bar(
        x=_sd_class_all,
        y=[int(_female_pages.get(c, 0)) for c in _sd_class_all],
        name="Female", marker_color="#F9A8D4",
        text=[int(_female_pages.get(c, 0)) for c in _sd_class_all],
        textposition="inside", textfont=dict(size=10, color="#1E1B4B"),
    ))
    _fig_cls.add_trace(go.Bar(
        x=_sd_class_all,
        y=[int(_male_pages.get(c, 0)) for c in _sd_class_all],
        name="Male", marker_color="#60A5FA",
        text=[int(_male_pages.get(c, 0)) for c in _sd_class_all],
        textposition="inside", textfont=dict(size=10, color="#1E1B4B"),
    ))
    if not _other_pages.empty:
        _fig_cls.add_trace(go.Bar(
            x=_sd_class_all,
            y=[int(_other_pages.get(c, 0)) for c in _sd_class_all],
            name="Other / Unknown", marker_color="#A78BFA",
            text=[int(_other_pages.get(c, 0)) for c in _sd_class_all],
            textposition="inside", textfont=dict(size=10, color="#1E1B4B"),
        ))
    _fig_cls.update_layout(**chart_layout(title=f"Total Pages per Class — {_sd_state}", height=340), barmode="stack")
    _fig_cls.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    _fig_cls.update_xaxes(title="Class", tickmode="array", tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
    _fig_cls.update_yaxes(title="Pages")
    st.plotly_chart(_fig_cls, use_container_width=True)

    # ── Section 3: Avg pages per student per class ───────────────────────────
    st.markdown(f"<div style='font-size:0.85rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:10px;'>📈 Avg Pages per Student — by Class</div>", unsafe_allow_html=True)

    _sd_avg = (
        _sd_df[_sd_df["class"].notna()]
        .assign(_cls=_sd_df["class"].astype(int))
        .groupby("_cls")
        .agg(_pages=("num_pages", "sum"), _students=("student_id", "nunique"))
        .reset_index()
    )
    _sd_avg["avg_pages"] = (_sd_avg["_pages"] / _sd_avg["_students"]).round(1)
    _avg_classes = sorted(_sd_avg["_cls"].tolist())

    _fig_avg = go.Figure()
    _fig_avg.add_trace(go.Bar(
        x=_avg_classes,
        y=_sd_avg.set_index("_cls")["avg_pages"].reindex(_avg_classes).tolist(),
        name="Avg pages/student", marker_color="#818CF8",
        text=[f"{v:.1f}" for v in _sd_avg.set_index("_cls")["avg_pages"].reindex(_avg_classes)],
        textposition="outside", textfont=dict(size=11),
    ))
    _fig_avg.add_hline(
        y=50, line_dash="dash", line_color="#F59E0B", line_width=2,
        annotation_text="Target: 50 pages/student",
        annotation_font_color="#F59E0B", annotation_position="top right",
    )
    _fig_avg.update_layout(**chart_layout(title=f"Avg Pages per Student per Class — {_sd_state}", height=320))
    _fig_avg.update_xaxes(title="Class", tickmode="array", tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
    _fig_avg.update_yaxes(title="Avg Pages / Student")
    st.plotly_chart(_fig_avg, use_container_width=True)

    # ── Section 4: Min 25 students per class per school — pass/fail ──────────
    st.markdown(f"<div style='font-size:0.85rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;margin-bottom:10px;'>🏫 School Coverage — Min 25 Students per Class</div>", unsafe_allow_html=True)

    _MIN_STUDENTS = 25
    _sd_school_cls = (
        _sd_df[_sd_df["class"].notna()]
        .assign(_cls=_sd_df["class"].astype(int))
        .groupby(["school_name", "_cls"])["student_id"].nunique()
        .reset_index()
        .rename(columns={"student_id": "students"})
    )
    # A school passes if ALL classes it has recorded meet the threshold
    _school_pass = (
        _sd_school_cls.groupby("school_name")
        .apply(lambda g: (g["students"] >= _MIN_STUDENTS).all())
        .reset_index()
        .rename(columns={0: "passed"})
    )
    _pass_schools = sorted(_school_pass[_school_pass["passed"]]["school_name"].tolist())
    _fail_schools = sorted(_school_pass[~_school_pass["passed"]]["school_name"].tolist())

    st.markdown(f"""
<div style='display:flex;gap:16px;margin-bottom:14px;'>
  <div style='background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:10px;
              padding:10px 18px;font-size:0.8rem;color:#10B981;font-weight:700;'>
    ✅ Passing: {len(_pass_schools)} schools
  </div>
  <div style='background:rgba(244,63,94,0.1);border:1px solid rgba(244,63,94,0.3);border-radius:10px;
              padding:10px 18px;font-size:0.8rem;color:#F43F5E;font-weight:700;'>
    ❌ Failing: {len(_fail_schools)} schools
  </div>
</div>
""", unsafe_allow_html=True)

    _p1, _p2 = st.columns(2)
    with _p1:
        if _pass_schools:
            _sel_pass = st.selectbox("✅ Passing schools", ["— select school —"] + _pass_schools, key="sd_pass_school")
        else:
            st.caption("No passing schools yet.")
            _sel_pass = None
    with _p2:
        if _fail_schools:
            _sel_fail = st.selectbox("❌ Failing schools", ["— select school —"] + _fail_schools, key="sd_fail_school")
        else:
            st.caption("No failing schools.")
            _sel_fail = None

    _sel_school_view = None
    if _sel_pass and _sel_pass != "— select school —":
        _sel_school_view = _sel_pass
    elif _sel_fail and _sel_fail != "— select school —":
        _sel_school_view = _sel_fail

    if _sel_school_view:
        _sch_df = _sd_df[_sd_df["school_name"] == _sel_school_view]
        _sch_cls_students = (
            _sch_df[_sch_df["class"].notna()]
            .assign(_cls=_sch_df["class"].astype(int))
            .groupby("_cls")["student_id"].nunique()
            .reset_index()
            .rename(columns={"student_id": "students"})
        )
        _sch_classes = list(range(1, 13))
        _sch_stu_map = _sch_cls_students.set_index("_cls")["students"]
        _sch_vals    = [int(_sch_stu_map.get(c, 0)) for c in _sch_classes]
        _sch_colors  = ["#10B981" if v >= _MIN_STUDENTS else "#F43F5E" for v in _sch_vals]

        _fig_sch = go.Figure()
        _fig_sch.add_trace(go.Bar(
            x=_sch_classes, y=_sch_vals,
            marker_color=_sch_colors,
            text=_sch_vals, textposition="outside",
            textfont=dict(size=11),
            name="Students",
        ))
        _fig_sch.add_hline(
            y=_MIN_STUDENTS, line_dash="dash", line_color="#F59E0B", line_width=2,
            annotation_text=f"Target: {_MIN_STUDENTS} students/class",
            annotation_font_color="#F59E0B", annotation_position="top right",
        )
        _fig_sch.update_layout(**chart_layout(title=f"{_sel_school_view} — Students per Class", height=300))
        _fig_sch.update_xaxes(title="Class", tickmode="array", tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
        _fig_sch.update_yaxes(title="Unique Students")
        st.plotly_chart(_fig_sch, use_container_width=True)

# ── Subject Detailed Stats Panel ──────────────────────────────────────────────
if not st.session_state.get("show_summary") and st.session_state.get("subject_detail_open"):
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:24px 0 20px;'>", unsafe_allow_html=True)

    # Header + close
    _shdr, _sclose = st.columns([6, 1])
    with _shdr:
        st.markdown(f"<div style='font-size:1.1rem;font-weight:800;color:#34D399;margin-bottom:8px;'>📚 Subject Breakdown — Detailed Stats</div>", unsafe_allow_html=True)
    with _sclose:
        if st.button("✕ Close", key="close_subj_detail"):
            st.session_state["subject_detail_open"] = False
            st.rerun()

    # Filters row — right-aligned
    _sf1, _sf2, _sf3 = st.columns([3, 2, 2])
    with _sf1:
        st.markdown("")  # spacer
    with _sf2:
        _CLASS_LEVELS = ["All Levels", "Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)"]
        _sd_level = st.selectbox("Class Level", _CLASS_LEVELS, key="subj_detail_level", label_visibility="visible")
    with _sf3:
        _sd_class_opts = ["All Classes"] + [str(i) for i in range(1, 13)]
        _sd_class_sel  = st.selectbox("Class", _sd_class_opts, key="subj_detail_class", label_visibility="visible")

    # Apply filters
    _sdf = filtered.copy()
    if _sd_level != "All Levels":
        _sdf = _sdf[_sdf["class_level"] == _sd_level]
    if _sd_class_sel != "All Classes":
        _sdf = _sdf[_sdf["class"].notna() & (_sdf["class"].astype(int) == int(_sd_class_sel))]

    # Filter label
    _filter_label = []
    if _sd_level != "All Levels":
        _filter_label.append(_sd_level)
    if _sd_class_sel != "All Classes":
        _filter_label.append(f"Class {_sd_class_sel}")
    _filter_str = "  ·  ".join(_filter_label) if _filter_label else "All data"
    st.markdown(f"<div style='font-size:0.75rem;color:{_text3};margin-bottom:14px;'>Showing: <b style='color:{_text2};'>{_filter_str}</b> &nbsp;·&nbsp; {len(_sdf):,} records &nbsp;·&nbsp; {int(_sdf['num_pages'].sum()):,} pages</div>", unsafe_allow_html=True)

    # Bar chart — pages per subject
    _subj_bar = (
        _sdf.groupby("subject")["num_pages"]
        .sum().sort_values(ascending=True)
        .reset_index()
    )
    _bar_colors = []
    _canonical_set = {"English", "Mathematics", "Science", "Social Science", "EVS", "Regional Lang"}
    for s in _subj_bar["subject"]:
        _bar_colors.append("#34D399" if s in _canonical_set else "#60A5FA")

    _subj_total_pages = int(_sdf["num_pages"].sum())
    _subj_bar["pct"] = (_subj_bar["num_pages"] / _subj_total_pages * 100).round(1) if _subj_total_pages else 0
    _TARGET_PCT = round(100 / 7, 1)  # 14.3%

    _fig_subj = go.Figure(go.Bar(
        x=_subj_bar["pct"],
        y=_subj_bar["subject"],
        orientation="h",
        marker_color=_bar_colors,
        text=[f"{row['pct']}%<br><span style='font-size:10px'>{row['num_pages']:,}</span>"
              for _, row in _subj_bar.iterrows()],
        textposition="inside",
        textfont=dict(size=11),
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    _fig_subj.add_vline(
        x=_TARGET_PCT,
        line_dash="dash", line_color="#F59E0B", line_width=2,
        annotation_text=f"Target {_TARGET_PCT}%",
        annotation_font_color="#F59E0B",
        annotation_position="top",
    )
    _fig_subj.update_layout(**chart_layout(
        title=f"Subject Share (%) — {_filter_str}",
        height=max(320, len(_subj_bar) * 38),
    ))
    _fig_subj.update_xaxes(title="% of Total Pages", range=[0, max(_subj_bar["pct"].max() * 1.15, _TARGET_PCT * 1.2)])
    _fig_subj.update_yaxes(title="")
    st.plotly_chart(_fig_subj, use_container_width=True)

# ── Students Detailed Stats Panel ─────────────────────────────────────────────
if not st.session_state.get("show_summary") and st.session_state.get("students_detail_open"):
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:24px 0 20px;'>", unsafe_allow_html=True)
    _shdr2, _sclose2 = st.columns([6, 1])
    with _shdr2:
        st.markdown(f"<div style='font-size:1.1rem;font-weight:800;color:#FBBF24;margin-bottom:8px;'>🎓 Students — Detailed Stats</div>", unsafe_allow_html=True)
    with _sclose2:
        if st.button("✕ Close", key="close_students_detail"):
            st.session_state["students_detail_open"] = False
            st.rerun()

    # Filters
    _stf1, _stf2, _stf3 = st.columns([3, 2, 2])
    with _stf2:
        _st_level = st.selectbox("Class Level",
            ["All Levels", "Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)"],
            key="students_detail_level")
    with _stf3:
        _st_class = st.selectbox("Class", ["All Classes"] + [str(i) for i in range(1, 13)],
            key="students_detail_class")

    _stdf = filtered.copy()
    if _st_level != "All Levels":
        _stdf = _stdf[_stdf["class_level"] == _st_level]
    if _st_class != "All Classes":
        _stdf = _stdf[_stdf["class"].notna() & (_stdf["class"].astype(int) == int(_st_class))]

    _st_filter_str = "  ·  ".join([x for x in [
        (_st_level if _st_level != "All Levels" else ""),
        (f"Class {_st_class}" if _st_class != "All Classes" else ""),
    ] if x]) or "All data"
    st.markdown(f"<div style='font-size:0.75rem;color:{_text3};margin-bottom:14px;'>Showing: <b style='color:{_text2};'>{_st_filter_str}</b> &nbsp;·&nbsp; {_stdf['student_id'].nunique():,} students</div>", unsafe_allow_html=True)

    _st_c1, _st_c2 = st.columns(2)

    # Chart 1 — students per class (bar)
    with _st_c1:
        _stu_by_cls = (
            _stdf[_stdf["class"].notna()]
            .assign(_cls=_stdf["class"].astype(int))
            .groupby("_cls")["student_id"].nunique()
            .reindex(range(1, 13), fill_value=0)
            .reset_index()
            .rename(columns={"index": "_cls", "student_id": "students"})
        )
        _fig_stu_cls = go.Figure(go.Bar(
            x=_stu_by_cls["_cls"], y=_stu_by_cls["students"],
            marker_color="#FBBF24",
            text=_stu_by_cls["students"], textposition="outside", textfont=dict(size=10),
        ))
        _fig_stu_cls.update_layout(**chart_layout(title="Students per Class", height=300))
        _fig_stu_cls.update_xaxes(title="Class", tickmode="array",
            tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
        _fig_stu_cls.update_yaxes(title="Unique Students")
        st.plotly_chart(_fig_stu_cls, use_container_width=True)

    # Chart 2 — gender split per class (stacked bar)
    with _st_c2:
        _stu_gend = (
            _stdf[_stdf["class"].notna()]
            .assign(_cls=_stdf["class"].astype(int))
            .groupby(["_cls", "gender"])["student_id"].nunique()
            .reset_index()
        )
        _fig_stu_g = go.Figure()
        for _g, _gc in [("Female", "#F9A8D4"), ("Male", "#60A5FA")]:
            _gd = _stu_gend[_stu_gend["gender"].str.lower() == _g.lower()].set_index("_cls")["student_id"]
            _fig_stu_g.add_trace(go.Bar(
                x=list(range(1, 13)),
                y=[int(_gd.get(c, 0)) for c in range(1, 13)],
                name=_g, marker_color=_gc,
                text=[int(_gd.get(c, 0)) for c in range(1, 13)],
                textposition="inside", textfont=dict(size=9, color="#1E1B4B"),
            ))
        _fig_stu_g.update_layout(**chart_layout(title="Gender Split per Class", height=300), barmode="stack")
        _fig_stu_g.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        _fig_stu_g.update_xaxes(title="Class", tickmode="array",
            tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
        _fig_stu_g.update_yaxes(title="Students")
        st.plotly_chart(_fig_stu_g, use_container_width=True)

    # Chart 3 — avg pages per student per class
    _stu_avg = (
        _stdf[_stdf["class"].notna()]
        .assign(_cls=_stdf["class"].astype(int))
        .groupby("_cls")
        .agg(_pages=("num_pages", "sum"), _students=("student_id", "nunique"))
        .reset_index()
    )
    _stu_avg["avg_pg"] = (_stu_avg["_pages"] / _stu_avg["_students"]).round(1)
    _fig_stu_avg = go.Figure(go.Bar(
        x=_stu_avg["_cls"],
        y=_stu_avg["avg_pg"],
        marker_color="#F97316",
        text=[f"{v:.1f}" for v in _stu_avg["avg_pg"]],
        textposition="outside", textfont=dict(size=10),
    ))
    _fig_stu_avg.add_hline(y=50, line_dash="dash", line_color="#F59E0B", line_width=2,
        annotation_text="Target: 50 pages/student", annotation_font_color="#F59E0B",
        annotation_position="top right")
    _fig_stu_avg.update_layout(**chart_layout(title="Avg Pages per Student per Class", height=300))
    _fig_stu_avg.update_xaxes(title="Class", tickmode="array",
        tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
    _fig_stu_avg.update_yaxes(title="Avg Pages / Student")
    st.plotly_chart(_fig_stu_avg, use_container_width=True)

# ── Language Detailed Stats Panel ─────────────────────────────────────────────
if not st.session_state.get("show_summary") and st.session_state.get("lang_detail_open"):
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:24px 0 20px;'>", unsafe_allow_html=True)
    _lhdr, _lclose = st.columns([6, 1])
    with _lhdr:
        st.markdown(f"<div style='font-size:1.1rem;font-weight:800;color:#C084FC;margin-bottom:8px;'>🌐 Languages — Detailed Stats</div>", unsafe_allow_html=True)
    with _lclose:
        if st.button("✕ Close", key="close_lang_detail"):
            st.session_state["lang_detail_open"] = False
            st.rerun()

    _avail_langs = sorted(
        filtered[~filtered["regional_language"].isin(["Unknown", ""])]["regional_language"].unique().tolist()
    )

    # Overview charts (no language filter needed — show all)
    _ldf_all = filtered[~filtered["regional_language"].isin(["Unknown", ""])].copy()
    _lang_bar = (
        _ldf_all.groupby("regional_language")["num_pages"]
        .sum().sort_values(ascending=True).reset_index()
    )
    _l_total = int(_lang_bar["num_pages"].sum())
    _lang_bar["pct"] = (_lang_bar["num_pages"] / _l_total * 100).round(1) if _l_total else 0
    _n_langs = len(_lang_bar)
    _l_target_pct = round(100 / _n_langs, 1) if _n_langs else 0

    _lo_c1, _lo_c2 = st.columns(2)
    with _lo_c1:
        _fig_lang = go.Figure(go.Bar(
            x=_lang_bar["pct"], y=_lang_bar["regional_language"],
            orientation="h", marker_color="#C084FC",
            text=[f"{row['pct']}%  ({row['num_pages']:,})" for _, row in _lang_bar.iterrows()],
            textposition="inside", textfont=dict(size=11),
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        ))
        if _n_langs > 1:
            _fig_lang.add_vline(x=_l_target_pct, line_dash="dash", line_color="#F59E0B", line_width=2,
                annotation_text=f"Equal share {_l_target_pct}%",
                annotation_font_color="#F59E0B", annotation_position="top")
        _fig_lang.update_layout(**chart_layout(title="Pages Share by Language", height=max(280, _n_langs * 40)))
        _fig_lang.update_xaxes(title="% of Total Pages",
            range=[0, max(_lang_bar["pct"].max() * 1.15, _l_target_pct * 1.2) if _l_total else 100])
        _fig_lang.update_yaxes(title="")
        st.plotly_chart(_fig_lang, use_container_width=True)

    with _lo_c2:
        _lang_stu = (
            _ldf_all.groupby("regional_language")["student_id"]
            .nunique().sort_values(ascending=True).reset_index()
            .rename(columns={"student_id": "students"})
        )
        _fig_lang_stu = go.Figure(go.Bar(
            x=_lang_stu["students"], y=_lang_stu["regional_language"],
            orientation="h", marker_color="#A78BFA",
            text=_lang_stu["students"], textposition="outside", textfont=dict(size=11),
        ))
        _fig_lang_stu.update_layout(**chart_layout(title="Students per Language", height=max(280, _n_langs * 40)))
        _fig_lang_stu.update_xaxes(title="Unique Students")
        _fig_lang_stu.update_yaxes(title="")
        st.plotly_chart(_fig_lang_stu, use_container_width=True)

    # Language selector + drill-down
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.07);margin:16px 0;'>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.85rem;font-weight:700;color:#C084FC;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:8px;'>🔍 Drill Down by Language</div>", unsafe_allow_html=True)

    if "lang_detail_sel" not in st.session_state:
        st.session_state["lang_detail_sel"] = None

    _ld1, _ld2, _ld3, _ld4 = st.columns([2, 2, 2, 2])
    with _ld1:
        _sel_lang = st.selectbox("Select language", ["— select —"] + _avail_langs, key="lang_detail_select")
        _lang_drill_btn = st.button("View Stats →", key="lang_drill_btn",
            disabled=(_sel_lang == "— select —"), use_container_width=True)
        if _lang_drill_btn and _sel_lang != "— select —":
            st.session_state["lang_detail_sel"] = _sel_lang
            st.rerun()
    with _ld2:
        _ll_level = st.selectbox("Class Level",
            ["All Levels", "Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)"],
            key="lang_detail_level")
    with _ld3:
        _ll_class = st.selectbox("Class", ["All Classes"] + [str(i) for i in range(1, 13)],
            key="lang_detail_class")
    with _ld4:
        if st.session_state.get("lang_detail_sel"):
            st.markdown(f"<div style='padding-top:28px;font-size:0.8rem;color:#C084FC;font-weight:700;'>📍 {st.session_state['lang_detail_sel']}</div>", unsafe_allow_html=True)

    if st.session_state.get("lang_detail_sel"):
        _ll_lang = st.session_state["lang_detail_sel"]
        _lldf = filtered[filtered["regional_language"] == _ll_lang].copy()
        if _ll_level != "All Levels":
            _lldf = _lldf[_lldf["class_level"] == _ll_level]
        if _ll_class != "All Classes":
            _lldf = _lldf[_lldf["class"].notna() & (_lldf["class"].astype(int) == int(_ll_class))]

        _ll_filter_str = "  ·  ".join([x for x in [
            _ll_lang,
            (_ll_level if _ll_level != "All Levels" else ""),
            (f"Class {_ll_class}" if _ll_class != "All Classes" else ""),
        ] if x])
        st.markdown(f"<div style='font-size:0.75rem;color:{_text3};margin:8px 0 14px;'>Showing: <b style='color:{_text2};'>{_ll_filter_str}</b> &nbsp;·&nbsp; {_lldf['student_id'].nunique():,} students &nbsp;·&nbsp; {int(_lldf['num_pages'].sum()):,} pages</div>", unsafe_allow_html=True)

        _ll_c1, _ll_c2 = st.columns(2)

        # Pages per class
        with _ll_c1:
            _ll_cls_pg = (
                _lldf[_lldf["class"].notna()]
                .assign(_cls=_lldf["class"].astype(int))
                .groupby("_cls")["num_pages"].sum()
                .reindex(range(1, 13), fill_value=0).reset_index()
            )
            _fig_ll_pg = go.Figure(go.Bar(
                x=_ll_cls_pg["_cls"], y=_ll_cls_pg["num_pages"],
                marker_color="#C084FC",
                text=_ll_cls_pg["num_pages"], textposition="outside", textfont=dict(size=10),
            ))
            _fig_ll_pg.update_layout(**chart_layout(title=f"Pages per Class — {_ll_lang}", height=300))
            _fig_ll_pg.update_xaxes(title="Class", tickmode="array",
                tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
            _fig_ll_pg.update_yaxes(title="Pages")
            st.plotly_chart(_fig_ll_pg, use_container_width=True)

        # Students per class
        with _ll_c2:
            _ll_cls_stu = (
                _lldf[_lldf["class"].notna()]
                .assign(_cls=_lldf["class"].astype(int))
                .groupby("_cls")["student_id"].nunique()
                .reindex(range(1, 13), fill_value=0).reset_index()
            )
            _fig_ll_stu = go.Figure(go.Bar(
                x=_ll_cls_stu["_cls"], y=_ll_cls_stu["student_id"],
                marker_color="#A78BFA",
                text=_ll_cls_stu["student_id"], textposition="outside", textfont=dict(size=10),
            ))
            _fig_ll_stu.add_hline(y=25, line_dash="dash", line_color="#F59E0B", line_width=2,
                annotation_text="Target: 25 students/class",
                annotation_font_color="#F59E0B", annotation_position="top right")
            _fig_ll_stu.update_layout(**chart_layout(title=f"Students per Class — {_ll_lang}", height=300))
            _fig_ll_stu.update_xaxes(title="Class", tickmode="array",
                tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
            _fig_ll_stu.update_yaxes(title="Unique Students")
            st.plotly_chart(_fig_ll_stu, use_container_width=True)

        # Avg pages per student per class
        _ll_avg = (
            _lldf[_lldf["class"].notna()]
            .assign(_cls=_lldf["class"].astype(int))
            .groupby("_cls")
            .agg(_pages=("num_pages", "sum"), _students=("student_id", "nunique"))
            .reset_index()
        )
        _ll_avg["avg_pg"] = (_ll_avg["_pages"] / _ll_avg["_students"]).round(1)
        _fig_ll_avg = go.Figure(go.Bar(
            x=_ll_avg["_cls"], y=_ll_avg["avg_pg"],
            marker_color="#F9A8D4",
            text=[f"{v:.1f}" for v in _ll_avg["avg_pg"]],
            textposition="outside", textfont=dict(size=10),
        ))
        _fig_ll_avg.add_hline(y=50, line_dash="dash", line_color="#F59E0B", line_width=2,
            annotation_text="Target: 50 pages/student",
            annotation_font_color="#F59E0B", annotation_position="top right")
        _fig_ll_avg.update_layout(**chart_layout(title=f"Avg Pages per Student — {_ll_lang}", height=300))
        _fig_ll_avg.update_xaxes(title="Class", tickmode="array",
            tickvals=list(range(1, 13)), ticktext=[str(i) for i in range(1, 13)])
        _fig_ll_avg.update_yaxes(title="Avg Pages / Student")
        st.plotly_chart(_fig_ll_avg, use_container_width=True)

# ── Detailed View Panel (full-page) ─────────────────────────────────────────────
if st.session_state.get("show_summary"):
    _close_c, _ = st.columns([1, 5])
    with _close_c:
        if st.button("✕  Close Detailed View", key="close_summary_top"):
            st.session_state["show_summary"] = False
            st.rerun()

    # ── Hero strip: tier 1 — target progress + key geo/collection counts ──
    st.markdown(f"""
    <div style='display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:12px;margin-bottom:12px;'>

      <!-- Total Pages — primary hero -->
      <div style='background:linear-gradient(135deg,rgba(129,140,248,0.12),rgba(167,139,250,0.06));
                  border:1px solid rgba(129,140,248,0.3);border-radius:14px;padding:18px 22px;
                  display:flex;flex-direction:column;justify-content:space-between;'>
        <div style='font-size:0.7rem;font-weight:700;color:#818CF8;text-transform:uppercase;letter-spacing:0.1em;'>
          Total Pages Collected
        </div>
        <div style='font-size:2.6rem;font-weight:900;color:{_text};letter-spacing:-1px;line-height:1.1;margin-top:6px;'>
          {total_pages:,}
        </div>
        <div style='margin-top:10px;'>
          <div style='display:flex;justify-content:space-between;margin-bottom:4px;'>
            <span style='font-size:0.72rem;color:{_text4};'>of {_PHASE1_TOTAL_PAGES_FULL:,} target</span>
            <span style='font-size:0.72rem;font-weight:700;color:{_hero_clr};'>{_hero_pct}%</span>
          </div>
          <div style='background:{_progress_track};border-radius:6px;height:8px;overflow:hidden;'>
            <div style='width:{min(_hero_pct,100):.1f}%;background:{_hero_clr};height:100%;border-radius:6px;
                        box-shadow:0 0 10px {_hero_clr}66;'></div>
          </div>
        </div>
      </div>

      <!-- Students -->
      <div style='background:rgba(52,211,153,0.07);border:1px solid rgba(52,211,153,0.2);
                  border-radius:14px;padding:18px 20px;'>
        <div style='font-size:0.7rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:0.1em;'>Students</div>
        <div style='font-size:2rem;font-weight:800;color:{_text};margin-top:8px;line-height:1;'>{n_students:,}</div>
        <div style='font-size:0.72rem;color:{_text2};margin-top:6px;'>{avg_pg_student} pages/student avg</div>
      </div>

      <!-- Schools -->
      <div style='background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);
                  border-radius:14px;padding:18px 20px;'>
        <div style='font-size:0.7rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:0.1em;'>Schools</div>
        <div style='font-size:2rem;font-weight:800;color:{_text};margin-top:8px;line-height:1;'>{n_schools:,}</div>
        <div style='font-size:0.72rem;color:{_text2};margin-top:6px;'>{avg_students_school} students/school avg</div>
      </div>

      <!-- Deadline -->
      <div style='background:rgba(244,63,94,0.07);border:1px solid rgba(244,63,94,0.2);
                  border-radius:14px;padding:18px 20px;'>
        <div style='font-size:0.7rem;font-weight:700;color:#F43F5E;text-transform:uppercase;letter-spacing:0.1em;'>Deadline</div>
        <div style='font-size:2rem;font-weight:800;color:{_dl_clr};margin-top:8px;line-height:1;'>{_days_left}</div>
        <div style='font-size:0.72rem;color:{_text2};margin-top:6px;'>days · 31 May 2026</div>
      </div>

    </div>

    <!-- Tier 2: Geographic coverage + collection depth -->
    <div style='display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:16px;'>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>States</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{n_states}</div>
      </div>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>Districts</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{n_districts}</div>
      </div>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>Blocks</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{n_blocks}</div>
      </div>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>Records</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{total_records:,}</div>
      </div>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>Subjects</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{n_subjects}</div>
      </div>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>Pages / Record</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{avg_pg_record}</div>
      </div>
      <div style='background:{_bg2};border:1px solid {_border_card};border-radius:10px;padding:10px 12px;text-align:center;'>
        <div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>Subjects / Student</div>
        <div style='font-size:1.35rem;font-weight:800;color:{_text3};margin-top:4px;'>{avg_subjects_student}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # 2. TARGETS vs ACHIEVED (Phase 1)
    # ══════════════════════════════════════════════════════════════════════════════

    section("Phase 1 Targets vs Achieved")

    # ── Target definitions (overall total comes from targets.json) ──
    PHASE1_TOTAL_PAGES = _PHASE1_TOTAL_PAGES_FULL
    PHASE1_DEADLINE = pd.Timestamp("2026-05-31", tz="Asia/Kolkata")

    # Overall class-level targets: 20L split equally across 4 class levels → 5L each
    _overall_lvl_pages = round(_PHASE1_TOTAL_PAGES_FULL / 4)  # 5,00,000
    CLASS_LEVEL_TARGETS = {
        lvl: {
            "pages": _overall_lvl_pages,
            "participants": round(_overall_lvl_pages / _PG_PER[lvl]),  # 6,66,667 / 50 = 13,333
            "pg_per_participant": _PG_PER[lvl],
        }
        for lvl in ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)")
    }

    GENDER_TARGETS = {"Female": 45.0, "Male": 45.0}  # at least % each

    # Subject targets are computed dynamically as 100 / n_subjects per class level (see rendering code)

    MIN_STUDENTS_PER_CLASS_PER_SCHOOL = 25
    MIN_SUBJECTS_COVERAGE = 5  # 4-5 main subjects
    REGIONAL_MEDIUM_TARGET = 50.0  # at least 50%

    # Use unfiltered df for target tracking (targets are project-wide)
    all_tgt_df = df.copy()

    # Language-specific targets are the constant LANGUAGE_SPECIFIC_TARGETS defined above.

    # Add India (Overall) to language options
    found_langs = sorted([lg for lg in all_tgt_df["regional_language"].unique() if lg != "Unknown"])
    lang_options = ["India (Overall)"] + found_langs

    def badge(label, passed):
        cls = "badge-pass" if passed else "badge-fail"
        return f'<span class="{cls}">{label}</span>'

    def progress_bar_html(label, current, target, fmt_current="", fmt_target="", override_color=None, target_pct=None):
        pct = min(current / target * 100, 100) if target else 0
        if override_color:
            color = override_color
        else:
            color = C_GREEN if pct >= 100 else C_AMBER if pct >= 60 else C_RED

        fc = fmt_current or f"{current:,.0f}"
        ft = fmt_target or f"{target:,.0f}"
        _target_line = ""
        if target_pct is not None:
            _target_line = (
                f"<div style='position:absolute;left:{target_pct}%;top:0;bottom:0;width:0;"
                f"border-left:2px dashed #F59E0B;z-index:2;'></div>"
                f"<div style='position:absolute;left:calc({target_pct}% + 4px);top:-16px;"
                f"color:#F59E0B;font-size:0.68rem;font-weight:600;white-space:nowrap;z-index:2;'>{target_pct}%</div>"
            )
        return (
    f'<div style="margin-bottom:12px;">'
    f'<div class="progress-label"><span>{label}</span>'
    f'<span class="pct" style="color:{color}">{pct:.1f}%</span></div>'
    f'<div style="position:relative;padding-top:{16 if target_pct is not None else 0}px;">'
    f'{_target_line}'
    f'<div style="background:{_progress_track};border-radius:8px;height:14px;overflow:hidden;">'
    f'<div style="width:{pct:.1f}%;background:{color};height:100%;border-radius:8px;transition:width 0.5s;"></div>'
    f'</div></div>'
    f'<div style="display:flex;justify-content:space-between;margin-top:2px;">'
    f'<span style="color:{_text2};font-size:0.75rem;">{fc} collected</span>'
    f'<span style="color:{_text2};font-size:0.75rem;">{ft}</span>'
    f'</div></div>'
        )


    lang_tabs = st.tabs(lang_options)

    for lang_tab, current_lang in zip(lang_tabs, lang_options):
        with lang_tab:
            if current_lang == "India (Overall)":
                tgt_df = all_tgt_df.copy()
                regional_lang_check = "Unknown"
                cur_phase1_total = PHASE1_TOTAL_PAGES
                cur_class_targets = CLASS_LEVEL_TARGETS
            else:
                tgt_df = all_tgt_df[all_tgt_df["regional_language"] == current_lang].copy()
                regional_lang_check = current_lang

                if current_lang in LANGUAGE_SPECIFIC_TARGETS:
                    l_tgt = LANGUAGE_SPECIFIC_TARGETS[current_lang]
                    cur_phase1_total = l_tgt["total"]
                    cur_class_targets = {
                        lvl: l_tgt[lvl]
                        for lvl in ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)")
                    }
                else:
                    # Language has data in bucket but no enrollment target defined yet
                    cur_phase1_total = 0
                    cur_class_targets = CLASS_LEVEL_TARGETS

            if len(tgt_df) == 0 and current_lang != "India (Overall)":
                st.info(f"No data for {current_lang}")
                continue

            # ── 2a. Overall Phase 1 Progress ──
            total_pg = int(tgt_df["num_pages"].sum())
            overall_pct = min(total_pg / cur_phase1_total * 100, 100) if cur_phase1_total else 0
            _ov_clr = "#10B981" if overall_pct >= 100 else "#F59E0B" if overall_pct >= 60 else "#F43F5E"
            total_students_overall = tgt_df["student_id"].nunique()

            st.markdown(f"""
    <div style='background:{_bg2};border:1px solid {_border_card};
                border-radius:12px;padding:16px 20px;margin-bottom:16px;'>
      <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;'>
        <div>
          <div style='font-size:0.72rem;font-weight:600;color:{_text2};text-transform:uppercase;letter-spacing:0.07em;'>
            Overall Page Collection
          </div>
          <div style='font-size:1.9rem;font-weight:800;color:{_text3};line-height:1.15;margin-top:2px;'>
            {total_pg:,}
            <span style='font-size:1rem;font-weight:500;color:{_text2};'>&nbsp;/ {cur_phase1_total:,} pages</span>
          </div>
        </div>
        <div style='text-align:right;'>
          <div style='font-size:2rem;font-weight:900;color:{_ov_clr};'>{overall_pct:.1f}%</div>
          <div style='font-size:0.72rem;color:{_text2};margin-top:1px;'>{total_students_overall:,} students</div>
        </div>
      </div>
      <div style='background:{_progress_track};border-radius:8px;height:10px;overflow:hidden;'>
        <div style='width:{overall_pct:.1f}%;background:{_ov_clr};height:100%;border-radius:8px;
                    box-shadow:0 0 8px {_ov_clr}55;transition:width 0.6s;'></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

            # ── 2b. Class-Level Page & Participant Targets ──
            _lvl_colors = {"Primary (1-5)": "#818CF8", "High School (6-8)": "#34D399", "Secondary (9-10)": "#F472B6", "Higher Secondary (11-12)": "#FBBF24"}
            _lvl_short  = {"Primary (1-5)": "Primary", "High School (6-8)": "High School", "Secondary (9-10)": "Secondary", "Higher Secondary (11-12)": "Higher Sec."}

            tg1, tg2 = st.columns(2)

            with tg1:
                st.markdown(f"<div style='font-size:0.72rem;font-weight:700;color:{_text2};text-transform:uppercase;"
                            "letter-spacing:0.07em;margin-bottom:8px;'>Pages by Class Level</div>",
                            unsafe_allow_html=True)
                for lvl, targets in cur_class_targets.items():
                    lvl_pages = int(tgt_df[tgt_df["class_level"] == lvl]["num_pages"].sum())
                    _pct = min(lvl_pages / targets["pages"] * 100, 100) if targets["pages"] else 0
                    _clr = "#10B981" if _pct >= 100 else "#F59E0B" if _pct >= 60 else "#F43F5E"
                    _ac  = _lvl_colors.get(lvl, "{_text2}")
                    st.markdown(f"""
    <div style='background:{_bg2};border:1px solid {_border_card};
                border-left:3px solid {_ac};border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
      <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;'>
        <span style='font-size:0.82rem;font-weight:600;color:{_text3};'>{_lvl_short[lvl]}</span>
        <span style='font-size:0.9rem;font-weight:700;color:{_clr};'>{_pct:.1f}%</span>
      </div>
      <div style='background:{_progress_track};border-radius:4px;height:6px;overflow:hidden;margin-bottom:5px;'>
        <div style='width:{_pct:.1f}%;background:{_clr};height:100%;border-radius:4px;'></div>
      </div>
      <div style='display:flex;justify-content:space-between;'>
        <span style='font-size:0.72rem;color:{_text2};'>{lvl_pages:,} collected</span>
        <span style='font-size:0.72rem;color:{_text2};'>Target: {targets["pages"]:,}</span>
      </div>
    </div>""", unsafe_allow_html=True)

            with tg2:
                st.markdown(f"<div style='font-size:0.72rem;font-weight:700;color:{_text2};text-transform:uppercase;"
                            "letter-spacing:0.07em;margin-bottom:8px;'>Participants by Class Level</div>",
                            unsafe_allow_html=True)
                for lvl, targets in cur_class_targets.items():
                    lvl_students = tgt_df[tgt_df["class_level"] == lvl]["student_id"].nunique()
                    _pct = min(lvl_students / targets["participants"] * 100, 100) if targets["participants"] else 0
                    _clr = "#10B981" if _pct >= 100 else "#F59E0B" if _pct >= 60 else "#F43F5E"
                    _ac  = _lvl_colors.get(lvl, "{_text2}")
                    st.markdown(f"""
    <div style='background:{_bg2};border:1px solid {_border_card};
                border-left:3px solid {_ac};border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
      <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;'>
        <span style='font-size:0.82rem;font-weight:600;color:{_text3};'>{_lvl_short[lvl]}</span>
        <span style='font-size:0.9rem;font-weight:700;color:{_clr};'>{_pct:.1f}%</span>
      </div>
      <div style='background:{_progress_track};border-radius:4px;height:6px;overflow:hidden;margin-bottom:5px;'>
        <div style='width:{_pct:.1f}%;background:{_clr};height:100%;border-radius:4px;'></div>
      </div>
      <div style='display:flex;justify-content:space-between;'>
        <span style='font-size:0.72rem;color:{_text2};'>{lvl_students:,} students</span>
        <span style='font-size:0.72rem;color:{_text2};'>Target: {targets["participants"]:,}</span>
      </div>
    </div>""", unsafe_allow_html=True)

            # ── Demographics ──────────────────────────────────────────────────────────
            section("Demographics")

            _DEM_H = 270
            _DEM_M = dict(l=5, r=5, t=32, b=5)

            def _pie(labels, values, colors, *, min_pct=3.0):
                """Return a go.Pie with outside labels only for slices ≥ min_pct %."""
                total = sum(values) or 1
                pcts  = [v / total * 100 for v in values]
                texts = [f"{l}<br>{p:.1f}%" if p >= min_pct else "" for l, p in zip(labels, pcts)]
                return go.Pie(
                    labels=labels, values=values,
                    hole=0.52,
                    marker=dict(colors=colors),
                    text=texts,
                    textinfo="text",
                    textposition="outside",
                    textfont=dict(size=10, family="Inter"),
                    hovertemplate="%{label}<br>%{value:,} · %{percent}<extra></extra>",
                    automargin=True,
                )

            _cl_label_map = {
                "Primary (1-5)": "Class 1-5",
                "High School (6-8)": "Class 6-8",
                "Secondary (9-10)": "Class 9-10",
                "Higher Secondary (11-12)": "Class 11-12",
            }
            _CLASS_COLORS = [C_INDIGO, C_GREEN, C_VIOLET, C_AMBER]
            _board_label_map = {v: v for v in BOARD_MAP.values()}
            _board_label_map["Not Mentioned"] = "N/A"

            # Row 1: Class Level, Gender, Medium of Instruction, Sample Type
            _dem_r1 = st.columns(4, gap="small")
            with _dem_r1[0]:
                _counts = tgt_df["class_level"].value_counts()
                _cl_labels = [_cl_label_map.get(l, l) for l in _counts.index]
                _fig = go.Figure(_pie(_cl_labels, _counts.values, _CLASS_COLORS))
                _fig.update_layout(**chart_layout(title="Class Level Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_class_{current_lang}")

            with _dem_r1[1]:
                _counts = tgt_df["gender"].value_counts()
                _g_color_map_d = {"Female": C_FEMALE, "Male": C_MALE}
                _g_colors_d = [_g_color_map_d.get(l, C_GREY) for l in _counts.index]
                _fig = go.Figure(_pie(list(_counts.index), _counts.values, _g_colors_d))
                _fig.update_layout(**chart_layout(title="Gender Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_gender_{current_lang}")

            with _dem_r1[2]:
                _med_d = tgt_df[tgt_df["medium_of_instruction"] != "Not Mentioned"]
                if len(_med_d):
                    _med_counts = _med_d["medium_of_instruction"].value_counts()
                    _fig = go.Figure(_pie(list(_med_counts.index), _med_counts.values, COLORS))
                    _fig.update_layout(**chart_layout(title="Medium of Instruction", showlegend=False, height=_DEM_H, margin=_DEM_M))
                    st.plotly_chart(_fig, use_container_width=True, key=f"dem_medium_{current_lang}")
                else:
                    st.info("No medium data.")

            with _dem_r1[3]:
                _samp_d = tgt_df[tgt_df["sample_type"] != "Not Mentioned"]
                if len(_samp_d):
                    _samp_counts = _samp_d["sample_type"].value_counts()
                    _fig = go.Figure(_pie(list(_samp_counts.index), _samp_counts.values, COLORS[3:]))
                    _fig.update_layout(**chart_layout(title="Sample Type", showlegend=False, height=_DEM_H, margin=_DEM_M))
                    st.plotly_chart(_fig, use_container_width=True, key=f"dem_sample_{current_lang}")
                else:
                    st.info("No sample data.")

            # Row 2: Board, State, Rural/Urban, School Type
            _dem_r2 = st.columns(4, gap="small")
            with _dem_r2[0]:
                _counts = tgt_df["board"].value_counts()
                _board_labels = [_board_label_map.get(b, b) for b in _counts.index]
                _fig = go.Figure(_pie(_board_labels, _counts.values, COLORS))
                _fig.update_layout(**chart_layout(title="Board Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_board_{current_lang}")

            with _dem_r2[1]:
                _state_counts = tgt_df[~tgt_df["state"].isin(["Unknown", ""])]["state"].value_counts()
                _fig = go.Figure(_pie(list(_state_counts.index), _state_counts.values, COLORS))
                _fig.update_layout(**chart_layout(title="State Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_state_{current_lang}")

            with _dem_r2[2]:
                _ru_counts = tgt_df["rural_urban"].replace("", "Not Mentioned").value_counts()
                _ru_colors_d = [{"Rural": C_RURAL, "Urban": C_URBAN}.get(l, C_GREY) for l in _ru_counts.index]
                _fig = go.Figure(_pie(list(_ru_counts.index), _ru_counts.values, _ru_colors_d))
                _fig.update_layout(**chart_layout(title="Rural / Urban", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_ru_{current_lang}")
                _ru_total = _ru_counts.sum()
                _rural_pct = round(_ru_counts.get("Rural", 0) / _ru_total * 100, 1) if _ru_total else 0
                _ru_ok = _rural_pct >= 50
                st.markdown(
                    f"<div style='text-align:center;font-size:0.75rem;color:{_text2};margin-top:-8px;'>"
                    f"Target: ≥50% Rural &nbsp;·&nbsp; "
                    f"<span style='color:{'#10B981' if _ru_ok else '#F43F5E'};font-weight:600;'>"
                    f"{'✓' if _ru_ok else '✗'} {_rural_pct}% Rural</span></div>",
                    unsafe_allow_html=True)

            with _dem_r2[3]:
                _st_counts = tgt_df["school_type"].replace("", "Not Mentioned").value_counts()
                _st_colors_d = [{"government": C_GOVT, "government_aided": C_AIDED, "private": C_PRIVATE}.get(str(l).lower(), C_GREY) for l in _st_counts.index]
                _fig = go.Figure(_pie(list(_st_counts.index), _st_counts.values, _st_colors_d))
                _fig.update_layout(**chart_layout(title="School Type", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_st_{current_lang}")
                _st_total = _st_counts.sum()
                _govt_pct = round(
                    (_st_counts.reindex([l for l in _st_counts.index if "government" in str(l).lower()]).sum()) / _st_total * 100, 1
                ) if _st_total else 0
                _st_ok = _govt_pct >= 60
                st.markdown(
                    f"<div style='text-align:center;font-size:0.75rem;color:{_text2};margin-top:-8px;'>"
                    f"Target: ≥60% Govt &nbsp;·&nbsp; "
                    f"<span style='color:{'#10B981' if _st_ok else '#F43F5E'};font-weight:600;'>"
                    f"{'✓' if _st_ok else '✗'} {_govt_pct}% Govt</span></div>",
                    unsafe_allow_html=True)

            # ── 2c. Avg Pages per Participant ──
            st.markdown("")
            pp_col = st.container()

            with pp_col:
                st.markdown(f"<div style='font-size:0.72rem;font-weight:700;color:{_text2};text-transform:uppercase;"
                            "letter-spacing:0.07em;margin-bottom:8px;'>Avg Pages per Participant vs Target</div>",
                            unsafe_allow_html=True)
                _pp_html = "<div style='display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;'>"
                for lvl, targets in cur_class_targets.items():
                    lvl_df = tgt_df[tgt_df["class_level"] == lvl]
                    lvl_students = lvl_df["student_id"].nunique()
                    lvl_pages = int(lvl_df["num_pages"].sum())
                    actual_pp = round(lvl_pages / lvl_students, 1) if lvl_students else 0
                    target_pp = targets["pg_per_participant"]
                    passed = actual_pp >= target_pp
                    _pc = "#10B981" if passed else "#F43F5E"
                    _ac = _lvl_colors.get(lvl, _text2)
                    _pp_html += (
                        f"<div style='background:{_bg2};border:1px solid {_border_card};"
                        f"border-top:2px solid {_ac};border-radius:6px;padding:8px 10px;text-align:center;'>"
                        f"<div style='font-size:0.65rem;font-weight:600;color:{_text2};text-transform:uppercase;"
                        f"letter-spacing:0.06em;margin-bottom:4px;'>{_lvl_short[lvl]}</div>"
                        f"<div style='font-size:1.2rem;font-weight:800;color:{_pc};'>{actual_pp}</div>"
                        f"<div style='font-size:0.65rem;color:{_text2};margin-top:2px;'>pg/student · target {target_pp}</div>"
                        f"<div style='margin-top:4px;'>{badge('PASS' if passed else 'FAIL', passed)}</div>"
                        f"</div>"
                    )
                _pp_html += "</div>"
                st.markdown(_pp_html, unsafe_allow_html=True)


            # pre-compute combo_pct for compliance summary
            school_class_counts = tgt_df.dropna(subset=["class"]).groupby(
                ["school_name", "class"])["student_id"].nunique().reset_index()
            school_class_counts.columns = ["school", "class", "students"]
            meeting = len(school_class_counts[school_class_counts["students"] >= MIN_STUDENTS_PER_CLASS_PER_SCHOOL])
            total_combos = len(school_class_counts)
            combo_pct = round(meeting / total_combos * 100, 1) if total_combos else 0

            # pre-compute regional_pct for compliance summary
            total_students_in_tab = len(tgt_df)
            if total_students_in_tab > 0:
                if regional_lang_check == "Unknown":
                    regional_count = len(tgt_df[~tgt_df["medium_of_instruction"].str.lower().isin(["english", "not mentioned"])])
                else:
                    regional_count = len(tgt_df[tgt_df["medium_of_instruction"].str.lower() == regional_lang_check.lower()])
                regional_pct = round(regional_count / total_students_in_tab * 100, 1)
            else:
                regional_pct = 0.0

            # ── 2e. Compute compliance values (needed for summary) ──
            _total_n = len(tgt_df)
            _govt_total_pct = 0.0
            _rural_pct = 0.0
            _aspir_pct = 0.0
            _aspir_state_n = 0
            _left_pct = 0.0
            _total_handed = 0
            if _total_n > 0:
                _st_vals = tgt_df["school_type"].str.lower().str.strip()
                _govt_n  = int((_st_vals == "government").sum())
                _aided_n = int((_st_vals == "government_aided").sum())
                _govt_total_pct = round((_govt_n + _aided_n) / _total_n * 100, 1)
                _ru_vals = tgt_df["rural_urban"].str.lower().str.strip()
                _rural_pct = round(int((_ru_vals == "rural").sum()) / _total_n * 100, 1)

            # ── 2f. Aspirational Districts & Left-handedness ──
            st.markdown("")
            al1, al2 = st.columns(2)

            with al1:
                _aspir_pct = 0.0
                _aspir_state_n = 0
                _aspir_n = 0
                if _total_n > 0:
                    # Use GoI mapping to find states with aspirational districts
                    _known_aspir_states = {s.title() for s in _ASPIRATIONAL_DISTRICTS}
                    _aspir_state_df = tgt_df[tgt_df["state"].isin(_known_aspir_states)]
                    _aspir_state_n  = len(_aspir_state_df)
                    _aspir_n        = int((tgt_df["aspirational_district"] == True).sum())
                    _aspir_pct      = round(_aspir_n / _aspir_state_n * 100, 1) if _aspir_state_n else 0.0
                    _aspir_passed   = _aspir_pct >= 15
                st.markdown("**Regional Medium of Instruction (Target: ≥50%)**")
                if total_students_in_tab > 0:
                    _rm_passed = regional_pct >= REGIONAL_MEDIUM_TARGET
                    st.markdown(progress_bar_html(
                        label="Regional Medium",
                        current=regional_count,
                        target=total_students_in_tab,
                        fmt_current=f"{regional_count} / {total_students_in_tab} records ({regional_pct}%)",
                        fmt_target=f"≥{REGIONAL_MEDIUM_TARGET}%",
                        override_color="#10B981" if _rm_passed else "#F43F5E",
                        target_pct=50
                    ), unsafe_allow_html=True)
                    st.markdown(f"&nbsp;&nbsp;{badge('PASS' if _rm_passed else 'FAIL', _rm_passed)}", unsafe_allow_html=True)
                else:
                    st.info("No data available.")

            with al2:
                _left_pct = 0.0
                if "handedness" in tgt_df.columns and _total_n > 0:
                    _handed_df    = tgt_df[tgt_df["handedness"].isin(["left", "right"])]
                    _total_handed = len(_handed_df)
                    _left_n       = int((tgt_df["handedness"] == "left").sum())
                    _left_pct     = round(_left_n / _total_handed * 100, 1) if _total_handed else 0.0
                st.markdown("**Aspirational Districts (Target: ≥15%)**")
                if _total_n > 0 and _aspir_state_n > 0:
                    st.markdown(progress_bar_html(
                        label="Aspirational Districts",
                        current=_aspir_n,
                        target=_aspir_state_n,
                        fmt_current=f"{_aspir_n} / {_aspir_state_n} records ({_aspir_pct}%)",
                        fmt_target="≥15%",
                        override_color="#10B981" if _aspir_pct >= 15 else "#F43F5E",
                        target_pct=15
                    ), unsafe_allow_html=True)
                    st.markdown(f"&nbsp;&nbsp;{badge('PASS' if _aspir_pct >= 15 else 'FAIL', _aspir_pct >= 15)}", unsafe_allow_html=True)
                elif _total_n > 0:
                    st.caption("No records from states with aspirational districts in current filter.")

            # ── 2g. Pre-compute multi-subject stats for summary line ──
            # "All 5 core" = English + Mathematics + Regional (Hindi/Regional or Sanskrit)
            #                + any 2 of (EVS, Social Science, Science)
            _CORE_POOL = {"EVS", "Social Science", "Science"}
            _REGIONAL_CATS = {"Hindi / Regional", "Sanskrit"}
            # Each entry: (display label, set of subject_category values that count)
            _SPECIFIC_SUBJECTS = [
                ("English",          {"English"}),
                ("Mathematics",      {"Mathematics"}),
                ("Regional Lang",    _REGIONAL_CATS),
                ("EVS",              {"EVS"}),
                ("Social Science",   {"Social Science"}),
                ("Science",          {"Science"}),
            ]
            _ms_parts = []
            for lvl in ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)"):
                lvl_df = tgt_df[tgt_df["class_level"] == lvl]
                lvl_students = lvl_df["student_id"].nunique()
                if lvl_students == 0:
                    continue
                stu_cats = lvl_df.groupby("student_id")["subject_category"].apply(set)
                def _has_all5(cats):
                    has_eng      = "English" in cats
                    has_math     = "Mathematics" in cats
                    has_regional = bool(cats & _REGIONAL_CATS)
                    pool_hit     = len(cats & _CORE_POOL)
                    return has_eng and has_math and has_regional and pool_hit >= 2
                all5_n   = int(stu_cats.apply(_has_all5).sum())
                all5_pct = round(all5_n / lvl_students * 100, 1)
                subj_counts = {}
                for label, cats_set in _SPECIFIC_SUBJECTS:
                    n_with = int(stu_cats.apply(lambda s, cs=cats_set: bool(s & cs)).sum())
                    subj_counts[label] = n_with
                _ms_parts.append((lvl, lvl_students, all5_n, all5_pct, subj_counts))

            # ── 2h. Overall Compliance Summary (full-width, 2-col grid) ──
            _gc_total = len(tgt_df[tgt_df["gender"].isin(["Male", "Female"])])
            _female_n = len(tgt_df[tgt_df["gender"] == "Female"])
            _male_n   = len(tgt_df[tgt_df["gender"] == "Male"])
            _female_pct    = round(_female_n / _gc_total * 100, 1) if _gc_total else 0
            _male_pct      = round(_male_n   / _gc_total * 100, 1) if _gc_total else 0
            _female_passed = _female_pct >= 45
            _male_passed   = _male_pct   >= 45

            st.markdown("")
            checks = []
            checks.append((f"Total Pages ≥ {cur_phase1_total:,}", total_pg >= cur_phase1_total))
            checks.append((f"Female ≥ 45% ({_female_pct}%)", _female_passed))
            checks.append((f"Male ≥ 45% ({_male_pct}%)", _male_passed))
            if total_students_in_tab > 0:
                checks.append(("Regional Medium ≥ 50%", regional_pct >= 50))
            for lvl, targets in cur_class_targets.items():
                lvl_d = tgt_df[tgt_df["class_level"] == lvl]
                ns = lvl_d["student_id"].nunique()
                pp = (int(lvl_d["num_pages"].sum()) / ns) if ns else 0
                checks.append((f"{lvl} ≥ {targets['pg_per_participant']} pg/student", pp >= targets["pg_per_participant"]))
            checks.append((f"≥{MIN_STUDENTS_PER_CLASS_PER_SCHOOL} students/class/school ({combo_pct}%)", combo_pct >= 80))
            checks.append((f"Government Schools ≥60% ({_govt_total_pct}%)", _govt_total_pct >= 60))
            checks.append((f"Rural Participants ≥50% ({_rural_pct}%)", _rural_pct >= 50))
            checks.append((f"Aspirational Districts ≥15% ({_aspir_pct}%)", _aspir_pct >= 15))
            checks.append((f"Left-handed ≥5% ({_left_pct}%)", _left_pct >= 5))

            n_pass = sum(1 for _, p in checks if p)
            n_fail = len(checks) - n_pass
            overall_ok = n_fail == 0

            # Split checks into two halves for side-by-side columns
            mid = (len(checks) + 1) // 2
            left_checks  = checks[:mid]
            right_checks = checks[mid:]

            def _check_card(label, passed):
                icon  = "✓" if passed else "✗"
                c_bg  = "rgba(16,185,129,0.07)" if passed else "rgba(244,63,94,0.07)"
                c_bdr = "rgba(16,185,129,0.25)" if passed else "rgba(244,63,94,0.25)"
                c_ic  = "#10B981" if passed else "#F43F5E"
                c_ib  = "rgba(16,185,129,0.15)" if passed else "rgba(244,63,94,0.15)"
                return (
                    f"<div style='display:flex;align-items:center;gap:10px;background:{c_bg};"
                    f"border:1px solid {c_bdr};border-radius:8px;padding:8px 12px;margin-bottom:6px;'>"
                    f"<span style='font-size:0.85rem;font-weight:700;color:{c_ic};background:{c_ib};"
                    f"border-radius:5px;padding:2px 8px;'>{icon}</span>"
                    f"<span style='font-size:0.82rem;color:{_text3};'>{label}</span></div>"
                )

            summary_html = f"""
    <div style='margin-bottom:12px;'>
      <div style='text-align:center;margin-bottom:12px;'>
        <div style='font-size:1.05rem;font-weight:700;color:{_text3};letter-spacing:0.02em;margin-bottom:8px;'>
          Overall Compliance Summary
        </div>
        <div style='display:inline-flex;align-items:center;background:{_bg3};border:1px solid {_border};border-radius:8px;overflow:hidden;'>
          <div style='padding:5px 18px;border-right:1px solid {_border};'>
            <span style='font-size:1.1rem;font-weight:800;color:{_text3};'>{n_pass}</span>
            <span style='font-size:0.72rem;color:{_text2};margin-left:4px;text-transform:uppercase;letter-spacing:0.06em;'>Pass</span>
          </div>
          <div style='padding:5px 18px;'>
            <span style='font-size:1.1rem;font-weight:800;color:{_text3};'>{n_fail}</span>
            <span style='font-size:0.72rem;color:{_text2};margin-left:4px;text-transform:uppercase;letter-spacing:0.06em;'>Fail</span>
          </div>
        </div>
      </div>
    </div>
    <div style='display:grid;grid-template-columns:1fr 1fr;gap:0 16px;'>
      <div>{"".join(_check_card(l, p) for l, p in left_checks)}</div>
      <div>{"".join(_check_card(l, p) for l, p in right_checks)}</div>
    </div>
    """
            st.markdown(summary_html, unsafe_allow_html=True)

            # ── Multi-subject summary row ──
            if _ms_parts:
                _legend = (
                    f"<div style='font-size:0.72rem;color:{_text2};margin-bottom:10px;line-height:1.6;'>"
                    f"<b style='color:{_text3};'>All 5 Core Subjects</b> = "
                    f"<span style='background:rgba(99,102,241,0.12);color:#818CF8;border-radius:4px;padding:1px 6px;font-weight:600;'>English</span>&nbsp;"
                    f"<span style='background:rgba(52,211,153,0.12);color:#34D399;border-radius:4px;padding:1px 6px;font-weight:600;'>Mathematics</span>&nbsp;"
                    f"<span style='background:rgba(251,191,36,0.12);color:#FBBF24;border-radius:4px;padding:1px 6px;font-weight:600;'>Regional Language</span>"
                    f"<span style='color:{_text2};font-size:0.67rem;'> (Hindi, Sanskrit, or any Indic)</span>&nbsp;"
                    f"+ any 2 of&nbsp;"
                    f"<span style='background:rgba(244,63,94,0.12);color:#F472B6;border-radius:4px;padding:1px 6px;font-weight:600;'>EVS</span>&nbsp;"
                    f"<span style='background:rgba(244,63,94,0.12);color:#F472B6;border-radius:4px;padding:1px 6px;font-weight:600;'>Social Science</span>&nbsp;"
                    f"<span style='background:rgba(244,63,94,0.12);color:#F472B6;border-radius:4px;padding:1px 6px;font-weight:600;'>Science</span>"
                    f"</div>"
                )
                _ms_cards = ""
                for lvl, n, all5_n, all5_pct, subj_counts in _ms_parts:
                    a_ok   = all5_pct >= 30
                    a_clr  = "#10B981" if a_ok else "#F43F5E"
                    _lvl_s = _lvl_short.get(lvl, lvl)
                    _subj_rows = ""
                    for label, _ in _SPECIFIC_SUBJECTS:
                        cnt = subj_counts.get(label, 0)
                        pct = round(cnt / n * 100, 1) if n else 0
                        _bar_w = min(pct, 100)
                        _s_ok  = pct >= 30
                        _s_clr = "#10B981" if _s_ok else "#F43F5E"
                        _s_ico = "✓" if _s_ok else "✗"
                        _subj_rows += (
                            f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:5px;'>"
                            f"  <div style='font-size:0.68rem;color:{_text2};width:82px;flex-shrink:0;white-space:nowrap;"
                            f"overflow:hidden;text-overflow:ellipsis;'>{label}</div>"
                            f"  <div style='flex:1;background:{_progress_track};border-radius:3px;height:6px;overflow:hidden;'>"
                            f"    <div style='width:{_bar_w}%;background:{_s_clr};height:100%;border-radius:3px;'></div></div>"
                            f"  <div style='font-size:0.68rem;color:{_text3};width:52px;text-align:right;flex-shrink:0;'>"
                            f"    {cnt:,} <span style='color:{_text2};'>({pct}%)</span></div>"
                            f"  <div style='font-size:0.68rem;font-weight:700;color:{_s_clr};width:12px;flex-shrink:0;'>{_s_ico}</div>"
                            f"</div>"
                        )
                    _ms_cards += (
                        f"<div style='flex:1;background:{_bg2};border:1px solid {_border_card};"
                        f"border-radius:10px;padding:12px 14px;min-width:0;'>"
                        f"<div style='font-size:0.73rem;font-weight:700;color:{_text2};text-transform:uppercase;"
                        f"letter-spacing:0.06em;margin-bottom:4px;'>{_lvl_s}</div>"
                        f"<div style='font-size:0.82rem;font-weight:600;color:{_text3};margin-bottom:6px;'>{n:,} students</div>"
                        f"<div style='height:1px;background:{_border};margin-bottom:8px;'></div>"
                        f"<div style='margin-bottom:8px;'>"
                        f"  <div style='font-size:0.68rem;color:{_text2};margin-bottom:2px;'>With all 5 core subjects</div>"
                        f"  <div style='font-size:1.05rem;font-weight:800;color:{a_clr};line-height:1.2;'>{all5_n:,}"
                        f"    <span style='font-size:0.7rem;font-weight:500;color:{_text2};'> / {n:,} ({all5_pct}%)</span>"
                        f"    &nbsp;{badge('PASS' if a_ok else 'FAIL', a_ok)}</div>"
                        f"</div>"
                        f"<div style='height:1px;background:{_border};margin-bottom:8px;'></div>"
                        f"<div style='font-size:0.68rem;font-weight:600;color:{_text2};text-transform:uppercase;"
                        f"letter-spacing:0.05em;margin-bottom:6px;'>Students with data per subject</div>"
                        f"{_subj_rows}"
                        f"</div>"
                    )
                st.markdown(
                    f"<div style='margin-top:14px;'>"
                    f"<div style='font-size:0.72rem;font-weight:700;color:{_text2};text-transform:uppercase;"
                    f"letter-spacing:0.07em;margin-bottom:8px;'>Subject Coverage per Student &nbsp;·&nbsp; Target ≥30% with all 5 core</div>"
                    f"{_legend}"
                    f"<div style='display:flex;gap:10px;'>{_ms_cards}</div></div>",
                    unsafe_allow_html=True,
                )


    # ══════════════════════════════════════════════════════════════════════════════
    # SUBJECT COVERAGE BY CLASS LEVEL (dynamic target = 100 / n_subjects)
    # ══════════════════════════════════════════════════════════════════════════════

    rm1, rm2 = st.columns(2)

    with rm1:
        _rm1_aspir_pct = 0.0
        _rm1_total_n = len(filtered)
        _rm1_aspir_state_n = 0
        _rm1_aspir_n = 0
        if _rm1_total_n > 0:
            _known_aspir_states_rm1 = {s.title() for s in _ASPIRATIONAL_DISTRICTS}
            _rm1_aspir_state_df = filtered[filtered["state"].isin(_known_aspir_states_rm1)]
            _rm1_aspir_state_n  = len(_rm1_aspir_state_df)
            _rm1_aspir_n        = int((filtered["aspirational_district"] == True).sum())
            _rm1_aspir_pct      = round(_rm1_aspir_n / _rm1_aspir_state_n * 100, 1) if _rm1_aspir_state_n else 0.0
            _rm1_aspir_passed   = _rm1_aspir_pct >= 15

    with rm2:
        _rm2_scc = filtered.dropna(subset=["class"]).groupby(
            ["school_name", "class"])["student_id"].nunique().reset_index()
        _rm2_scc.columns = ["school", "class", "students"]
        _rm2_meeting = len(_rm2_scc[_rm2_scc["students"] >= MIN_STUDENTS_PER_CLASS_PER_SCHOOL])
        _rm2_total   = len(_rm2_scc)
        if _rm2_meeting > 0:
            st.markdown(f"**Min Students per Class per School (Target: ≥{MIN_STUDENTS_PER_CLASS_PER_SCHOOL})**")
            st.markdown(progress_bar_html(
                "School-Class combos meeting target", _rm2_meeting, _rm2_total,
                f"{_rm2_meeting} / {_rm2_total}", f"≥{MIN_STUDENTS_PER_CLASS_PER_SCHOOL} students each"
            ), unsafe_allow_html=True)

    section("State Level Analysis")

    _state_data = filtered[~filtered["state"].isin(["Unknown", ""])]

    # ── State summary bar ──
    state_stats = _state_data.groupby("state").agg(
        pages=("num_pages", "sum"),
        students=("student_id", "nunique"),
        schools=("school_name", "nunique"),
        districts=("district", "nunique"),
    ).reset_index().sort_values("pages", ascending=False)

    sl1, sl2 = st.columns(2)
    with sl1:
        _fig = go.Figure(go.Bar(
            x=state_stats["state"], y=state_stats["pages"],
            marker_color=C_INDIGO,
            text=[f"{p:,}" for p in state_stats["pages"]], textposition="outside", textfont=_bar_textfont,
        ))
        _fig.update_layout(**chart_layout(title="Pages by State"))
        st.plotly_chart(_fig, use_container_width=True)

    with sl2:
        _fig = go.Figure(go.Bar(
            name="Students", x=state_stats["state"], y=state_stats["students"],
            marker_color=COLORS[1], text=state_stats["students"], textposition="outside", textfont=_bar_textfont,
        ))
        _fig.update_layout(**chart_layout(title="Students by State"))
        st.plotly_chart(_fig, use_container_width=True)

    sl3, sl4 = st.columns(2)
    with sl3:
        _fig = go.Figure(go.Bar(
            name="Schools", x=state_stats["state"], y=state_stats["schools"],
            marker_color=COLORS[2], text=state_stats["schools"], textposition="outside", textfont=_bar_textfont,
        ))
        _fig.update_layout(**chart_layout(title="Schools by State"))
        st.plotly_chart(_fig, use_container_width=True)

    with sl4:
        _fig = go.Figure(go.Bar(
            name="Districts", x=state_stats["state"], y=state_stats["districts"],
            marker_color=COLORS[3], text=state_stats["districts"], textposition="outside", textfont=_bar_textfont,
        ))
        _fig.update_layout(**chart_layout(title="Districts by State"))
        st.plotly_chart(_fig, use_container_width=True)

    # ── Treemap: State → District → Block ──
    _tree_hier = _state_data[~_state_data["district"].isin(["", "Unknown"])].copy()
    _tree_hier["block_clean"] = _tree_hier["block"].replace("Not Mentioned", "Unknown Block")
    _tree_agg = _tree_hier.groupby(["state", "district", "block_clean"])["num_pages"].sum().reset_index()
    _fig_tree = px.treemap(
        _tree_agg, path=["state", "district", "block_clean"], values="num_pages",
        color="num_pages", color_continuous_scale="Purples",
        title="State → District → Block (Pages)",
    )
    _fig_tree.update_layout(**chart_layout(title="State → District → Block (Pages)", height=480))
    st.plotly_chart(_fig_tree, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # DISTRICT LEVEL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════════

    section("District Level Analysis")

    _dist_data = filtered[~filtered["district"].isin(["", "Unknown"])]

    # State selector for district drill-down
    _state_options = ["All"] + sorted(_state_data["state"].dropna().unique().tolist())
    _sel_state_drill = st.selectbox("Filter by State", _state_options, key="state_drill_sel")
    _drill_df = _dist_data if _sel_state_drill == "All" else _dist_data[_dist_data["state"] == _sel_state_drill]

    if len(_drill_df) == 0:
        st.info("No district data for current selection.")
    else:
        dist_stats = _drill_df.groupby("district").agg(
            pages=("num_pages", "sum"),
            students=("student_id", "nunique"),
            schools=("school_name", "nunique"),
            blocks=("block", "nunique"),
            records=("num_pages", "count"),
            state=("state", "first"),
        ).reset_index().sort_values("pages", ascending=False)
        dist_stats["pg_per_student"] = (dist_stats["pages"] / dist_stats["students"]).round(1)

        # KPI strip
        _d_total_pages    = int(dist_stats["pages"].sum())
        _d_total_students = int(dist_stats["students"].sum())
        _d_n_districts    = len(dist_stats)
        _d_top_dist       = dist_stats.iloc[0]["district"] if len(dist_stats) else "—"
        _d_top_pages      = int(dist_stats.iloc[0]["pages"]) if len(dist_stats) else 0

        st.markdown(f"""
    <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;'>
      <div style='background:rgba(129,140,248,0.08);border:1px solid rgba(129,140,248,0.25);border-radius:10px;padding:12px 16px;'>
        <div style='font-size:0.65rem;font-weight:700;color:#818CF8;text-transform:uppercase;letter-spacing:.08em;'>Districts</div>
        <div style='font-size:1.6rem;font-weight:800;color:{_text3};line-height:1.1;margin-top:4px;'>{_d_n_districts}</div>
      </div>
      <div style='background:rgba(52,211,153,0.07);border:1px solid rgba(52,211,153,0.2);border-radius:10px;padding:12px 16px;'>
        <div style='font-size:0.65rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:.08em;'>Pages</div>
        <div style='font-size:1.6rem;font-weight:800;color:{_text3};line-height:1.1;margin-top:4px;'>{_d_total_pages:,}</div>
      </div>
      <div style='background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);border-radius:10px;padding:12px 16px;'>
        <div style='font-size:0.65rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:.08em;'>Students</div>
        <div style='font-size:1.6rem;font-weight:800;color:{_text3};line-height:1.1;margin-top:4px;'>{_d_total_students:,}</div>
      </div>
      <div style='background:rgba(192,132,252,0.07);border:1px solid rgba(192,132,252,0.2);border-radius:10px;padding:12px 16px;'>
        <div style='font-size:0.65rem;font-weight:700;color:#C084FC;text-transform:uppercase;letter-spacing:.08em;'>Top District</div>
        <div style='font-size:1.1rem;font-weight:800;color:{_text3};line-height:1.1;margin-top:4px;'>{_d_top_dist}</div>
        <div style='font-size:0.65rem;color:{_text2};margin-top:2px;'>{_d_top_pages:,} pages</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

        # Charts row 1: pages + students/schools
        dd1, dd2 = st.columns(2)
        with dd1:
            _fig = go.Figure(go.Bar(
                x=dist_stats["district"], y=dist_stats["pages"],
                marker_color=C_GREEN,
                text=[f"{p:,}" for p in dist_stats["pages"]], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Pages by District"))
            st.plotly_chart(_fig, use_container_width=True)

        with dd2:
            _fig = go.Figure(go.Bar(
                name="Students", x=dist_stats["district"], y=dist_stats["students"],
                marker_color=COLORS[1], text=dist_stats["students"], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Students by District"))
            st.plotly_chart(_fig, use_container_width=True)

        # Charts row 1b: schools + blocks by district
        dd1b, dd2b = st.columns(2)
        with dd1b:
            _fig = go.Figure(go.Bar(
                name="Schools", x=dist_stats["district"], y=dist_stats["schools"],
                marker_color=COLORS[2], text=dist_stats["schools"], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Schools by District"))
            st.plotly_chart(_fig, use_container_width=True)

        with dd2b:
            _fig = go.Figure(go.Bar(
                name="Blocks", x=dist_stats["district"], y=dist_stats["blocks"],
                marker_color=COLORS[3], text=dist_stats["blocks"], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Blocks by District"))
            st.plotly_chart(_fig, use_container_width=True)

        # Charts row 2: pg/student bar + rural/urban breakdown per district
        dd3, dd4 = st.columns(2)
        with dd3:
            _pps = dist_stats.sort_values("pg_per_student", ascending=True)
            _fig = go.Figure(go.Bar(
                x=_pps["pg_per_student"], y=_pps["district"],
                orientation="h",
                marker_color=[C_GREEN if v >= 50 else C_RED for v in _pps["pg_per_student"]],
                text=[f"{v}" for v in _pps["pg_per_student"]], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.add_vline(x=50, line_dash="dash", line_color=C_AMBER,
                annotation_text="50 pg target", annotation_position="top right",
                annotation_font_color=C_AMBER)
            _fig.update_layout(**chart_layout(title="Avg Pages / Student by District",
                height=max(300, min(len(_pps) * 28, 500)),
                xaxis_title="Pages/Student",
                yaxis=dict(showgrid=False, zeroline=False, showline=False, color=_chart_text,
                           tickfont=dict(color=_chart_text))))
            st.plotly_chart(_fig, use_container_width=True)

        with dd4:
            # School type breakdown per district (stacked)
            _st_dist = _drill_df.groupby(["district", "school_type"])["student_id"].count().reset_index()
            _st_dist.columns = ["district", "school_type", "count"]
            _st_pivot = _st_dist.pivot(index="district", columns="school_type", values="count").fillna(0)
            _fig = go.Figure()
            _st_cmap = {"government": C_GOVT, "government_aided": C_AIDED, "private": C_PRIVATE}
            for _stype in _st_pivot.columns:
                _fig.add_trace(go.Bar(
                    name=_stype.title().replace("_", " "),
                    x=_st_pivot.index,
                    y=_st_pivot[_stype],
                    marker_color=_st_cmap.get(str(_stype).lower(), C_GREY),
                ))
            _fig.update_layout(**chart_layout(title="School Type Mix by District", barmode="stack"))
            st.plotly_chart(_fig, use_container_width=True)

        # Charts row 3: rural/urban breakdown per district
        dd5, dd6 = st.columns(2)
        with dd5:
            _ru_dist = _drill_df.groupby(["district", "rural_urban"])["student_id"].count().reset_index()
            _ru_dist.columns = ["district", "rural_urban", "count"]
            _ru_dist["rural_urban"] = _ru_dist["rural_urban"].replace("", "Not Mentioned")
            _ru_pivot = _ru_dist.pivot(index="district", columns="rural_urban", values="count").fillna(0)
            _fig = go.Figure()
            _ru_cmap = {"Rural": C_RURAL, "Urban": C_URBAN}
            for _rtype in _ru_pivot.columns:
                _fig.add_trace(go.Bar(
                    name=str(_rtype),
                    x=_ru_pivot.index,
                    y=_ru_pivot[_rtype],
                    marker_color=_ru_cmap.get(str(_rtype), C_GREY),
                ))
            _fig.update_layout(**chart_layout(title="Rural / Urban Mix by District", barmode="stack"))
            st.plotly_chart(_fig, use_container_width=True)

        with dd6:
            _bd_dist = _drill_df[_drill_df["board"] != "Other"].groupby(["district", "board"])["student_id"].count().reset_index()
            _bd_dist.columns = ["district", "board", "count"]
            _bd_pivot = _bd_dist.pivot(index="district", columns="board", values="count").fillna(0)
            _fig = go.Figure()
            for _bi, _bname in enumerate(_bd_pivot.columns):
                _fig.add_trace(go.Bar(
                    name=str(_bname),
                    x=_bd_pivot.index,
                    y=_bd_pivot[_bname],
                    marker_color=COLORS[_bi % len(COLORS)],
                ))
            _fig.update_layout(**chart_layout(title="Board Mix by District", barmode="stack"))
            st.plotly_chart(_fig, use_container_width=True)

        # District treemap: district → block
        _dtree_data = _drill_df[_drill_df["block"] != "Not Mentioned"].groupby(
            ["district", "block"])["num_pages"].sum().reset_index()
        if len(_dtree_data):
            _fig_dt = px.treemap(_dtree_data, path=["district", "block"], values="num_pages",
                color="num_pages", color_continuous_scale="Purples")
            _fig_dt.update_layout(**chart_layout(title="District → Block Treemap", height=480))
            st.plotly_chart(_fig_dt, use_container_width=True)

        with st.expander("District Statistics Table", expanded=False):
            st.dataframe(
                dist_stats[["district", "state", "pages", "students", "schools", "blocks", "pg_per_student", "records"]],
                hide_index=True, use_container_width=True,
                column_config={
                    "district": "District", "state": "State",
                    "pages": st.column_config.NumberColumn("Pages", format="%d"),
                    "students": "Students", "schools": "Schools", "blocks": "Blocks",
                    "pg_per_student": st.column_config.NumberColumn("Pg/Student", format="%.1f"),
                    "records": "Records",
                })

    # ══════════════════════════════════════════════════════════════════════════════
    # 8. BLOCK-LEVEL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════════

    section("Block-Level Analysis")

    block_data = filtered[filtered["block"] != "Not Mentioned"]
    block_stats = block_data.groupby("block").agg(
        pages=("num_pages", "sum"), students=("student_id", "nunique"),
        schools=("school_name", "nunique"), records=("num_pages", "count"),
    ).reset_index().sort_values("pages", ascending=False)
    block_stats["pg_per_student"] = (block_stats["pages"] / block_stats["students"]).round(1)

    b1, b2 = st.columns(2)
    with b1:
        fig = go.Figure(go.Bar(
            x=block_stats["block"], y=block_stats["pages"],
            marker_color=C_VIOLET,
            text=[f"{p:,}" for p in block_stats["pages"]], textposition="outside", textfont=_bar_textfont,
        ))
        fig.update_layout(**chart_layout(title="Pages by Block"))
        st.plotly_chart(fig, use_container_width=True)

    with b2:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Unique Students", x=block_stats["block"], y=block_stats["students"],
            marker_color=COLORS[1], text=block_stats["students"], textposition="outside", textfont=_bar_textfont,
        ))
        fig.add_trace(go.Bar(
            name="Unique Schools", x=block_stats["block"], y=block_stats["schools"],
            marker_color=COLORS[2], text=block_stats["schools"], textposition="outside", textfont=_bar_textfont,
        ))
        fig.update_layout(**chart_layout(title="Students & Schools per Block", barmode="group"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Treemap: block → school → pages
    tree_data = block_data.groupby(["block", "school_name"])["num_pages"].sum().reset_index()
    fig = px.treemap(tree_data, path=["block", "school_name"], values="num_pages",
                     color="num_pages", color_continuous_scale="Purples")
    fig.update_layout(**chart_layout(title="Block > School Treemap"))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Block Statistics Table", expanded=False):
        st.dataframe(block_stats, hide_index=True, use_container_width=True,
                     column_config={
                         "block": "Block", "pages": st.column_config.NumberColumn("Pages", format="%d"),
                         "students": "Students", "schools": "Schools",
                         "pg_per_student": st.column_config.NumberColumn("Pg/Student", format="%.1f"),
                         "records": "Records",
                     })

    # ══════════════════════════════════════════════════════════════════════════════
    # PAGES PER RECORD DISTRIBUTION
    # ══════════════════════════════════════════════════════════════════════════════

    section("School Statistics")

    school_stats = filtered.groupby("school_name").agg(
        pages=("num_pages", "sum"), records=("num_pages", "count"),
        students=("student_id", "nunique"), subjects=("subject", "nunique"),
        block=("block", "first"), board=("board", "first"),
        classes=("class", "nunique"),
    ).reset_index().sort_values("pages", ascending=False)
    school_stats["pg_per_student"] = (school_stats["pages"] / school_stats["students"]).round(1)

    # _sch1, _sch2 = st.columns(2)
    # with _sch1:
    #     _top_schools = school_stats.head(15)
    #     _fig = go.Figure(go.Bar(
    #         x=_top_schools["school_name"], y=_top_schools["pages"],
    #         marker_color=COLORS[2],
    #         text=[f"{p:,}" for p in _top_schools["pages"]], textposition="outside", textfont=_bar_textfont,
    #     ))
    #     _fig.update_layout(**chart_layout(title="Top 15 Schools by Pages Collected",
    #                                       xaxis=dict(tickangle=-35, showgrid=False, zeroline=False,
    #                                                  showline=False, color=_text2)))
    #     st.plotly_chart(_fig, use_container_width=True)

    # with _sch2:
    #     _pps = school_stats.sort_values("pg_per_student", ascending=True).head(15)
    #     _fig = go.Figure(go.Bar(
    #         x=_pps["pg_per_student"], y=_pps["school_name"],
    #         orientation="h",
    #         marker_color=[C_GREEN if v >= 50 else C_RED for v in _pps["pg_per_student"]],
    #         text=[f"{v}" for v in _pps["pg_per_student"]], textposition="outside", textfont=_bar_textfont,
    #     ))
    #     _fig.add_vline(x=50, line_dash="dash", line_color=C_AMBER,
    #         annotation_text="50 pg target", annotation_position="top right",
    #         annotation_font_color=C_AMBER)
    #     _fig.update_layout(**chart_layout(title="Avg Pages / Student by School",
    #         height=max(370, len(_pps) * 28),
    #         xaxis_title="Pages/Student",
    #         yaxis=dict(showgrid=False, zeroline=False, showline=False, color=_text2)))
    #     st.plotly_chart(_fig, use_container_width=True)

    with st.expander("View Detailed School Statistics", expanded=False):
        st.dataframe(
            school_stats[["school_name", "block", "board", "pages",
                           "students", "classes", "subjects", "pg_per_student", "records"]],
            hide_index=True, use_container_width=True,
            column_config={
                "school_name": "School", "block": "Block", "board": "Board",
                "pages": st.column_config.NumberColumn("Pages", format="%d"),
                "students": "Students", "classes": "Classes Covered", "subjects": "Subjects",
                "pg_per_student": st.column_config.NumberColumn("Pg/Student", format="%.1f"),
                "records": "Records",
            }
        )

    # ══════════════════════════════════════════════════════════════════════════════
    # STATE LEVEL ANALYSIS  (State → District → Block hierarchy)
    # ══════════════════════════════════════════════════════════════════════════════

    section("Class & Subject Analysis")

    tab1, tab2, tab3 = st.tabs(["By Class", "By Subject", "Heatmap"])

    with tab1:
        class_data = filtered.dropna(subset=["class"])
        c1, c2 = st.columns(2)
        with c1:
            class_pages = class_data.groupby("class")["num_pages"].sum().sort_index().reset_index()
            class_pages["class"] = class_pages["class"].astype(int).astype(str)
            fig = go.Figure(go.Bar(
                x=class_pages["class"], y=class_pages["num_pages"],
                marker_color=COLORS[0], text=class_pages["num_pages"], textposition="outside", textfont=_bar_textfont,
            ))
            fig.update_layout(**chart_layout(title="Total Pages by Class"))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            class_students = class_data.groupby("class")["student_id"].nunique().sort_index().reset_index()
            class_students["class"] = class_students["class"].astype(int).astype(str)
            fig = go.Figure(go.Bar(
                x=class_students["class"], y=class_students["student_id"],
                marker_color=COLORS[1], text=class_students["student_id"], textposition="outside", textfont=_bar_textfont,
            ))
            fig.update_layout(**chart_layout(title="Unique Students by Class"))
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        s1, s2 = st.columns(2)
        with s1:
            subj_pages = filtered.groupby("subject")["num_pages"].sum().sort_values(ascending=True).reset_index()
            _canonical_set = {"English", "Mathematics", "Science", "Social Science", "EVS", "Regional Lang"}
            _colors = [COLORS[2] if s in _canonical_set else COLORS[4] for s in subj_pages["subject"]]
            fig = go.Figure(go.Bar(
                x=subj_pages["num_pages"], y=subj_pages["subject"],
                orientation="h", marker_color=_colors,
                text=[f"{p:,}" for p in subj_pages["num_pages"]], textposition="outside", textfont=_bar_textfont,
            ))
            fig.update_layout(**chart_layout(title="Pages by Subject", height=max(380, len(subj_pages) * 26)))
            st.plotly_chart(fig, use_container_width=True)
        with s2:
            cat_counts = filtered["subject_category"].value_counts()
            fig = go.Figure(go.Pie(
                labels=cat_counts.index, values=cat_counts.values, hole=0.5,
                marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside",
                textfont=dict(color=_chart_text, family="Inter", size=11),
            ))
            fig.update_layout(**chart_layout(title="Subject Category Breakdown", showlegend=False))
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        heat = filtered.groupby(["class_level", "subject_category"])["num_pages"].sum().unstack(fill_value=0)
        fig = go.Figure(go.Heatmap(
            z=heat.values, x=heat.columns.tolist(), y=heat.index.tolist(),
            colorscale=[[0, "#1E1B4B"], [0.3, "#4338CA"], [0.6, "#818CF8"], [1.0, "#C7D2FE"]],
            text=heat.values, texttemplate="%{text:,}",
            textfont=dict(color=_text, size=11),
        ))
        fig.update_layout(**chart_layout(title="Pages Heatmap: Class Level × Subject Category", height=380))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # 6b. STUDENT MULTI-SUBJECT COVERAGE
    # ══════════════════════════════════════════════════════════════════════════════

    section("Subject & Gender Coverage by Class Level")

    # Gender × Class Level pages bar
    _gc_df = filtered.groupby(["class_level", "gender"])["num_pages"].sum().unstack(fill_value=0)
    _gc_df = _gc_df.reindex([l for l in _LEVELS if l in _gc_df.index])
    _fig_gcbar = go.Figure()
    _g_bar_cm = {"Female": C_FEMALE, "Male": C_MALE}
    for _g in _gc_df.columns:
        _fig_gcbar.add_trace(go.Bar(name=_g, x=_gc_df.index, y=_gc_df[_g],
                                    marker_color=_g_bar_cm.get(_g, C_GREY),
                                    textfont=_bar_textfont))
    _fig_gcbar.update_layout(**chart_layout(title="Pages Collected: Gender × Class Level", barmode="group"))
    st.plotly_chart(_fig_gcbar, use_container_width=True, key="gcbar_main")

    _sc_lvl_sel = st.selectbox(
        "Select Class Level",
        ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)", "Higher Secondary (11-12)"),
        key="sc_lvl_sel_main"
    )

    _sc_lvl_df = df[df["class_level"] == _sc_lvl_sel]
    _sc_total_pages = int(_sc_lvl_df["num_pages"].sum())

    if _sc_total_pages == 0:
        st.info(f"No data for {_sc_lvl_sel}")
    else:
        # All subject categories present in this level
        _sc_subj_pages = _sc_lvl_df.groupby("subject_category")["num_pages"].sum()
        _sc_all_subjects = sorted(_sc_subj_pages.index.tolist())
        _sc_n = len(_sc_all_subjects)
        _sc_target_pct = round(100 / _sc_n, 1) if _sc_n else 0

        _sc_tbl = []
        for subj in _sc_all_subjects:
            actual_pages = int(_sc_subj_pages.get(subj, 0))
            actual_pct = round(actual_pages / _sc_total_pages * 100, 1)
            passed = actual_pct >= _sc_target_pct
            _sc_tbl.append({
                "Subject": subj, "Pages": f"{actual_pages:,}",
                "Actual %": actual_pct, "Target %": _sc_target_pct,
                "Status": "Pass" if passed else "Fail",
            })

        st.markdown(f"**{_sc_lvl_sel}** — Total Pages: **{_sc_total_pages:,}** &nbsp;|&nbsp; Target per subject: **≥{_sc_target_pct}%** (100 ÷ {_sc_n} subjects)")
        _sc_html = f"<table style='width:100%; color:{_text3}; font-size:0.85rem;'>"
        _sc_html += f"<tr style='border-bottom:1px solid {_border_card};'>"
        for h in ["Subject", "Pages", "Actual %", "Target %", "Status"]:
            align = "left" if h == "Subject" else "right" if h != "Status" else "center"
            _sc_html += f"<th style='text-align:{align}; padding:8px;'>{h}</th>"
        _sc_html += "</tr>"
        for r in _sc_tbl:
            _sc_html += f"<tr style='border-bottom:1px solid {_border2};'>"
            _sc_html += f"<td style='padding:8px;'>{r['Subject']}</td>"
            _sc_html += f"<td style='text-align:right; padding:8px;'>{r['Pages']}</td>"
            _sc_html += f"<td style='text-align:right; padding:8px;'>{r['Actual %']}%</td>"
            _sc_html += f"<td style='text-align:right; padding:8px;'>≥{r['Target %']}%</td>"
            _sc_html += f"<td style='text-align:center; padding:8px;'>{badge(r['Status'], r['Status'] == 'Pass')}</td>"
            _sc_html += "</tr>"
        _sc_html += "</table>"
        st.markdown(_sc_html, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # 5. CLASS & SUBJECT ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════════

    section("Student Multi-Subject Coverage")

    student_subj_count = filtered.groupby("student_id")["subject_category"].nunique().reset_index()
    student_subj_count.columns = ["student_id", "num_subjects"]
    subj_dist = student_subj_count["num_subjects"].value_counts().sort_index().reset_index()
    subj_dist.columns = ["Subjects Covered", "Students"]

    ms1, ms2 = st.columns(2)
    with ms1:
        fig = go.Figure(go.Bar(
            x=subj_dist["Subjects Covered"].astype(str), y=subj_dist["Students"],
            marker_color=COLORS[1], text=subj_dist["Students"], textposition="outside", textfont=_bar_textfont,
        ))
        fig.update_layout(**chart_layout(title="How Many Subjects Do Students Cover?",
                                         xaxis_title="Number of Subject Categories", yaxis_title="Number of Students"))
        st.plotly_chart(fig, use_container_width=True)

    with ms2:
        # Bucket into meaningful groups
        def coverage_label(n):
            if n == 1: return "1 subject only"
            if n <= 3: return "2-3 subjects"
            return "4+ subjects (broad)"
        student_subj_count["coverage"] = student_subj_count["num_subjects"].apply(coverage_label)
        cov_counts = student_subj_count["coverage"].value_counts()
        _cov_color_map = {
            "1 subject only":      COLORS[3],
            "2-3 subjects":        COLORS[1],
            "4+ subjects (broad)": "#F97316",  # orange
        }
        _cov_colors = [_cov_color_map.get(lbl, COLORS[6]) for lbl in cov_counts.index]
        fig = go.Figure(go.Pie(
            labels=cov_counts.index, values=cov_counts.values, hole=0.5,
            marker=dict(colors=_cov_colors),
            textinfo="label+percent+value", textposition="outside",
            textfont=dict(color=_chart_text, family="Inter", size=11),
        ))
        fig.update_layout(**chart_layout(title="Student Coverage Breadth", showlegend=False))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # 6c. PAGES PER RECORD DISTRIBUTION
    # ══════════════════════════════════════════════════════════════════════════════

    section("Pages per Record Distribution")

    bp1, bp2 = st.columns(2)
    with bp1:
        fig = go.Figure()
        fig.add_trace(go.Box(
            y=filtered["num_pages"], name="All",
            marker_color=COLORS[0], boxmean=True,
        ))
        for i, lvl in enumerate([l for l in _LEVELS if l in filtered["class_level"].unique()]):
            lvl_data = filtered[filtered["class_level"] == lvl]["num_pages"]
            fig.add_trace(go.Box(
                y=lvl_data, name=lvl,
                marker_color=COLORS[i + 1], boxmean=True,
            ))
        fig.update_layout(**chart_layout(title="Pages per Record by Class Level",
                                         yaxis_title="Pages", height=400))
        st.plotly_chart(fig, use_container_width=True)

    with bp2:
        fig = go.Figure()
        for i, cat in enumerate(sorted(filtered["subject_category"].unique())):
            cat_data = filtered[filtered["subject_category"] == cat]["num_pages"]
            fig.add_trace(go.Box(
                y=cat_data, name=cat,
                marker_color=COLORS[i % len(COLORS)], boxmean=True,
            ))
        fig.update_layout(**chart_layout(title="Pages per Record by Subject Category",
                                         yaxis_title="Pages", height=400))
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════════
    # CONTENT QUALITY
    # ══════════════════════════════════════════════════════════════════════════════

    section("Content Quality")

    _cq_cols = st.columns(4, gap="small")
    _cq_H = 260
    _cq_M = dict(l=5, r=5, t=32, b=5)

    def _cq_pie(df_col, values, title, color_yes, color_no, key):
        _counts = df_col[df_col.isin(values)].value_counts()
        if not len(_counts):
            st.caption(f"No {title.lower()} data.")
            return
        _colors = []
        for _l in _counts.index:
            if _l in ("yes", "default"):
                _colors.append(color_yes)
            else:
                _colors.append(color_no)
        _labels = [{"upside_down": "Upside Down", "counterclockwise": "Counter-CW",
                    "clockwise": "Clockwise"}.get(_l, _l.title()) for _l in _counts.index]
        _fig = go.Figure(_pie(_labels, _counts.values, _colors))
        _fig.update_layout(**chart_layout(title=title, showlegend=False, height=_cq_H, margin=_cq_M))
        st.plotly_chart(_fig, use_container_width=True, key=key)

    with _cq_cols[0]:
        _cq_pie(filtered["handwritten_or_handdrawn"], ["yes", "no"],
                "Handwritten / Drawn", "#34D399", "#F87171", "cq_hw")

    with _cq_cols[1]:
        _cq_pie(filtered["printed"], ["yes", "no"],
                "Printed Content", "#818CF8", "#94A3B8", "cq_pr")

    with _cq_cols[2]:
        _cq_pie(filtered["mixed_content"], ["yes", "no"],
                "Mixed Content", "#FBBF24", "#6B7280", "cq_mc")

    with _cq_cols[3]:
        _cq_pie(filtered["rotation"],
                ["default", "upside_down", "clockwise", "counterclockwise"],
                "Page Rotation", "#34D399", "#F87171", "cq_rot")

    # ══════════════════════════════════════════════════════════════════════════════
    # DISTRIBUTOR STATS
    # ══════════════════════════════════════════════════════════════════════════════

    section("Distributor Stats")

    _dist_df = filtered[filtered["distributor"] != "Not Mentioned"].copy()

    if len(_dist_df) == 0:
        st.info("No distributor data in current selection.")
    else:
        _dist_stats = _dist_df.groupby("distributor").agg(
            pages=("num_pages", "sum"),
            students=("student_id", "nunique"),
            schools=("school_name", "nunique"),
            districts=("district", "nunique"),
            records=("num_pages", "count"),
        ).reset_index().sort_values("pages", ascending=False)
        _dist_stats["pg_per_student"] = (_dist_stats["pages"] / _dist_stats["students"]).round(1)

        # KPI row
        _dkpi1, _dkpi2, _dkpi3, _dkpi4 = st.columns(4)
        _dkpi1.metric("Distributors", f"{len(_dist_stats):,}")
        _dkpi2.metric("Total Pages", f"{int(_dist_stats['pages'].sum()):,}")
        _dkpi3.metric("Total Students", f"{int(_dist_stats['students'].sum()):,}")
        _dkpi4.metric("Avg Pages/Student", f"{(_dist_stats['pages'].sum() / _dist_stats['students'].sum()).round(1) if _dist_stats['students'].sum() else 0}")

        # Charts row 1: pages + students by distributor
        _dc1, _dc2 = st.columns(2)
        with _dc1:
            _fig = go.Figure(go.Bar(
                x=_dist_stats["distributor"], y=_dist_stats["pages"],
                marker_color=C_INDIGO,
                text=[f"{p:,}" for p in _dist_stats["pages"]], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Pages by Distributor"))
            st.plotly_chart(_fig, use_container_width=True)

        with _dc2:
            _fig = go.Figure(go.Bar(
                x=_dist_stats["distributor"], y=_dist_stats["students"],
                marker_color=COLORS[1],
                text=_dist_stats["students"], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Students by Distributor"))
            st.plotly_chart(_fig, use_container_width=True)

        # Charts row 2: schools + districts by distributor
        _dc3, _dc4 = st.columns(2)
        with _dc3:
            _fig = go.Figure(go.Bar(
                x=_dist_stats["distributor"], y=_dist_stats["schools"],
                marker_color=COLORS[2],
                text=_dist_stats["schools"], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Schools by Distributor"))
            st.plotly_chart(_fig, use_container_width=True)

        with _dc4:
            _fig = go.Figure(go.Bar(
                x=_dist_stats["distributor"], y=_dist_stats["districts"],
                marker_color=COLORS[3],
                text=_dist_stats["districts"], textposition="outside", textfont=_bar_textfont,
            ))
            _fig.update_layout(**chart_layout(title="Districts by Distributor"))
            st.plotly_chart(_fig, use_container_width=True)

        # Avg pages/student horizontal bar
        _pps_d = _dist_stats.sort_values("pg_per_student", ascending=True)
        _fig = go.Figure(go.Bar(
            x=_pps_d["pg_per_student"], y=_pps_d["distributor"],
            orientation="h",
            marker_color=[C_GREEN if v >= 50 else C_RED for v in _pps_d["pg_per_student"]],
            text=[f"{v}" for v in _pps_d["pg_per_student"]], textposition="outside", textfont=_bar_textfont,
        ))
        _fig.add_vline(x=50, line_dash="dash", line_color=C_AMBER,
            annotation_text="50 pg target", annotation_position="top right",
            annotation_font_color=C_AMBER)
        _fig.update_layout(**chart_layout(title="Avg Pages / Student by Distributor",
            height=max(300, min(len(_pps_d) * 28, 500)),
            xaxis_title="Pages/Student",
            yaxis=dict(showgrid=False, zeroline=False, showline=False, color=_chart_text,
                       tickfont=dict(color=_chart_text))))
        st.plotly_chart(_fig, use_container_width=True)

        with st.expander("Distributor Statistics Table", expanded=False):
            st.dataframe(
                _dist_stats[["distributor", "pages", "students", "schools", "districts", "pg_per_student", "records"]],
                hide_index=True, use_container_width=True,
            )

    # ══════════════════════════════════════════════════════════════════════════════

    section("Raw Data Explorer")

    with st.expander("View & download filtered data", expanded=False):
        _show_pdf_key = st.toggle("Show pdf_key column", value=False, key="raw_show_pdf_key")
        _raw_cols = [c for c in filtered.columns if c != "pdf_key"]
        if _show_pdf_key:
            _raw_cols = _raw_cols + ["pdf_key"]
        st.dataframe(filtered[_raw_cols], use_container_width=True, height=400)

        csv = filtered[_raw_cols].to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "ocr_vs_filtered_data.csv", "text/csv")

    st.stop()
