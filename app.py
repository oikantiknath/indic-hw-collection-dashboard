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
import sqlite3
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

import fitz  # pymupdf — page-to-image rendering for flagged page preview

load_dotenv()



urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OCR-VS Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling — warm paper palette ─────────────────────────────────────────────
_dark            = False        # kept for chart_helpers compat
_bg              = "#f6f4f1"   # warm off-white canvas
_bg2             = "#ffffff"   # surfaces / cards
_bg3             = "#fdfcfb"   # slightly raised
_bg4             = "#f0ebe6"   # hover / striped rows
_border          = "#e4ddd6"   # hairline borders
_border2         = "#ede8e3"
_border_card     = "#e4ddd6"
_text            = "#1a1714"   # near-black
_text2           = "#6b5f56"   # warm gray secondary
_text3           = "#3d3530"   # mid text
_text4           = "#a8998e"   # muted tertiary
_input_bg        = "#ffffff"
_input_border    = "#e4ddd6"
_card_hover_border = "#c8bfb8"
_tab_border      = "#e4ddd6"
_sidebar_bg      = "#ffffff"
_sidebar_hr      = "#e4ddd6"
_jump_bg         = "#ffffff"
_jump_content_bg = "#fdfcfb"
_alert_border    = "#e4ddd6"
_progress_track  = "#f0ebe6"
_btn_bg          = "#ffffff"
_btn_bg_hover    = "#f6f4f1"
_btn_color       = "#1a1714"
_btn_border      = "#e4ddd6"
_accent          = "#d4500a"   # burnt orange — single accent
_accent_bg       = "rgba(212,80,10,0.08)"
_accent_border   = "rgba(212,80,10,0.3)"
_error_color     = "#c0392b"
_shadow          = "rgba(0,0,0,0.06)"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* ── Streamlit root theme tokens — controls canvas dataframe colours ── */
    :root {{
        --background-color: {_bg2};
        --secondary-background-color: {_bg3};
        --text-color: {_text};
        --font: 'Inter', sans-serif;
        /* Glide-data-grid CSS vars — must be on :root for canvas tables to pick up */
        --gdg-text-dark:               {_text};
        --gdg-text-medium:             {_text2};
        --gdg-text-light:              {_text4};
        --gdg-bg-cell:                 {_bg2};
        --gdg-bg-cell-medium:          {_bg3};
        --gdg-bg-header:               {_bg3};
        --gdg-bg-header-has-focus:     {_bg4};
        --gdg-bg-header-hovered:       {_bg4};
        --gdg-border-color:            {_border};
        --gdg-horizontal-border-color: {_border};
        --gdg-accent-color:            {_accent};
        --gdg-accent-light:            {_accent_bg};
    }}

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp > header {{ display: none !important; }}
    .stApp {{
        background-color: {_bg} !important;
    }}
    .main .block-container {{ padding-top: 0rem !important; margin-top: -5.5rem !important; max-width: 1400px; }}

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
        font-size: 2.2rem; font-weight: 800;
        color: {_text} !important;
        margin-bottom: 0; letter-spacing: -1px; line-height: 1.2;
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
        background: {_accent}; border-radius: 4px;
    }}

    /* ── KPI cards ── */
    div[data-testid="metric-container"] {{
        background: {_bg2} !important;
        border: 1px solid {_border_card} !important;
        border-radius: 16px; padding: 20px 24px;
        box-shadow: 0 1px 4px {_shadow};
        transition: all 0.2s ease;
    }}
    div[data-testid="metric-container"]:hover {{
        border-color: {_card_hover_border} !important;
        box-shadow: 0 4px 12px {_shadow};
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
        box-shadow: 0 4px 16px {_shadow} !important;
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
        background-color: {_accent_bg} !important;
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
        border-color: {_accent} !important;
        box-shadow: 0 0 0 2px {_accent_bg} !important;
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
        --gdg-accent-color:        {_accent} !important;
        --gdg-accent-light:        {_accent_bg} !important;
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
        background-color: {_accent_bg} !important;
        color: {_text} !important;
        border: 1px solid {_accent_border} !important;
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
        min-width: 100%; box-shadow: 0 4px 16px {_shadow};
        z-index: 10000; border: 1px solid {_accent}; border-radius: 8px;
        margin-top: 4px; max-height: 400px; overflow-y: auto;
    }}
    .st-jump-content a {{
        color: {_text2}; padding: 12px 16px; text-decoration: none;
        display: block; font-size: 0.85rem; font-weight: 500;
        border-bottom: 1px solid {_border2};
    }}
    .st-jump-content a:last-child {{ border-bottom: none; }}
    .st-jump-content a:hover {{
        background-color: {_accent_bg}; color: {_text};
    }}
    .st-jump-menu:hover .st-jump-content {{ display: block; }}
    .st-jump-menu:hover .st-jump-btn {{ border-color: {_accent}; }}

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
        border-color: {_accent} !important;
        box-shadow: 0 0 0 2px {_accent_bg} !important;
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
        border-bottom: 2px solid {_accent} !important;
        background: transparent !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background-color: transparent !important;
        padding-top: 16px;
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
    box-shadow: 0 4px 16px {_shadow} !important;
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
    background-color: {_accent_bg} !important;
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
    background-color: {_accent_bg} !important;
    color: {_text} !important;
    border: 1px solid {_accent_border} !important;
}}
body span[data-baseweb="tag"] span {{ color: {_text} !important; }}
</style>
""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html(f"""
<script>
    const parentDoc = window.parent.document;
    const observer = new MutationObserver(() => {{
        const buttons = parentDoc.querySelectorAll('button');
        buttons.forEach(btn => {{
            const testid = btn.getAttribute('data-testid');
            const ariaLabel = btn.getAttribute('aria-label');
            if (testid === 'collapsedControl' || testid === 'stSidebarCollapsedControl' || 
               (ariaLabel && ariaLabel.toLowerCase().includes('sidebar'))) {{
                
                if (!btn.querySelector('.custom-filter-text')) {{
                    const svg = btn.querySelector('svg');
                    if (svg) svg.style.display = 'none';
                    
                    const span = parentDoc.createElement('span');
                    span.className = 'custom-filter-text';
                    span.innerText = 'Filters';
                    span.style.fontWeight = '600';
                    span.style.fontSize = '0.9rem';
                    span.style.color = '{_text}';
                    span.style.padding = '6px 16px';
                    span.style.background = '{_bg2}';
                    span.style.borderRadius = '8px';
                    span.style.border = '1px solid {_border_card}';
                    span.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                    span.style.display = 'block';
                    
                    btn.appendChild(span);
                    btn.style.background = 'transparent';
                    btn.style.border = 'none';
                    btn.style.width = 'auto';
                    btn.style.padding = '0';
                    btn.style.position = 'fixed';
                    btn.style.top = '14px';
                    btn.style.left = '16px';
                    btn.style.zIndex = '999999';
                    
                    btn.addEventListener('mouseover', () => {{
                        span.style.background = '{_bg3}';
                        span.style.borderColor = '{_accent}';
                        span.style.color = '{_accent}';
                    }});
                    btn.addEventListener('mouseout', () => {{
                        span.style.background = '{_bg2}';
                        span.style.borderColor = '{_border_card}';
                        span.style.color = '{_text}';
                    }});
                }}
            }}
        }});
    }});
    observer.observe(parentDoc.body, {{ childList: true, subtree: true }});
</script>
""", height=0, width=0)



# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING & CLEANING
# ══════════════════════════════════════════════════════════════════════════════

_APPROVED_CSV  = Path(os.environ["APPROVED_CSV_PATH"])
_ANNOTATION_DB = Path(os.environ["ANNOTATION_DB_PATH"])


@st.cache_data(ttl=1800, show_spinner=False)
def render_pdf_page_as_png(pdf_key: str, page_number: int) -> bytes | None:
    """Download a PDF from MinIO and render a single page as PNG bytes.

    page_number is 1-indexed (matches PDF page labels).
    Returns None on any error so callers can fall back gracefully.
    """
    try:
        s3 = _s3()
        buf = io.BytesIO()
        s3.download_fileobj(MINIO_BUCKET, pdf_key, buf)
        buf.seek(0)
        doc = fitz.open(stream=buf.read(), filetype="pdf")
        idx = page_number - 1
        if idx < 0 or idx >= len(doc):
            return None
        pix = doc[idx].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        return pix.tobytes("jpeg", jpg_quality=82)
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def render_all_flagged_pages(pdf_key: str, page_numbers: tuple) -> dict:
    """Download PDF once, render all flagged pages in parallel. Returns {page_num: jpeg_bytes}."""
    import concurrent.futures
    try:
        s3 = _s3()
        buf = io.BytesIO()
        s3.download_fileobj(MINIO_BUCKET, pdf_key, buf)
        pdf_bytes = buf.getvalue()

        # 1.5× zoom — still sharp at display width, ~2× faster than 2.0×
        mat = fitz.Matrix(1.5, 1.5)

        def _render(pg: int) -> tuple:
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                idx = pg - 1
                if idx < 0 or idx >= len(doc):
                    return pg, None
                pix = doc[idx].get_pixmap(matrix=mat, alpha=False)
                # JPEG: ~5× smaller than PNG, renders faster in browser
                return pg, pix.tobytes("jpeg", jpg_quality=82)
            except Exception:
                return pg, None

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = dict(pool.map(_render, page_numbers))

        return {pg: data for pg, data in results.items() if data}
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def get_presigned_url_cached(pdf_key: str) -> tuple:
    """Cache presigned URL so it isn't re-fetched on every rerun."""
    return _presigned_url(pdf_key, expires=1800)


@st.cache_data(ttl=300, show_spinner=False)
def load_annotation_data() -> pd.DataFrame:
    """Load review decisions and page-level issues from annotation.db.

    Returns a DataFrame indexed by unique_file_id with columns:
      reject_stage, review_flag, issues_vs, flagged_pages_vs
    """
    if not _ANNOTATION_DB.exists():
        return pd.DataFrame(columns=["unique_file_id", "reject_stage", "review_flag",
                                     "issues_vs", "flagged_pages_vs", "corrections_ok"])
    conn = sqlite3.connect(str(_ANNOTATION_DB))
    rows_out = []
    try:
        cur = conn.execute(
            "SELECT unique_file_id, pdf_decision, page_rejections, corrections_ok FROM pdf_annotations"
        )
        for uid, decision, page_rej_raw, corrections_ok in cur.fetchall():
            decision = (decision or "").strip().lower()

            if decision == "rejected":
                reject_stage = "reject_stage_vs"
                review_flag  = "stage_vs"
            elif decision == "accepted":
                reject_stage = "null"
                review_flag  = "stage_vs"
            else:
                reject_stage = "null"
                review_flag  = "pending"

            issues_vs        = []
            flagged_pages_vs = []
            page_issues_map_vs: dict[int, list[str]] = {}
            try:
                page_rejections = _json.loads(page_rej_raw or "[]")
                for entry in page_rejections:
                    pg   = entry.get("page")
                    iss  = [i for i in (entry.get("issues") or []) if i]
                    if iss:
                        issues_vs.extend(iss)
                        if pg is not None:
                            pg_int = int(pg)
                            flagged_pages_vs.append(pg_int)
                            page_issues_map_vs.setdefault(pg_int, []).extend(iss)
            except Exception:
                pass

            rows_out.append({
                "unique_file_id":    uid,
                "reject_stage":      reject_stage,
                "review_flag":       review_flag,
                "issues_vs":         issues_vs,
                "flagged_pages_vs":  flagged_pages_vs,
                "page_issues_map_vs": page_issues_map_vs,
                "corrections_ok":    (corrections_ok or "").strip().lower(),
            })
    finally:
        conn.close()

    return pd.DataFrame(rows_out)


@st.cache_data(ttl=300, show_spinner=False)
def load_raw_counts() -> dict:
    """Total uploads from approved_uploads.csv (all reviewed PDFs)."""
    if not _APPROVED_CSV.exists():
        return {"total": 0}
    raw = pd.read_csv(_APPROVED_CSV, usecols=["id"])
    return {"total": len(raw)}


@st.cache_data(ttl=300, show_spinner=False)
def load_qa_counts() -> dict:
    """QA review decisions from annotation.db.

    Returns accepted (clean + w/issues), rejected, pending counts
    relative to the full approved_uploads.csv list.
    """
    empty = {"total": 0, "reviewed": 0, "clean": 0, "with_issues": 0,
             "approved": 0, "rejected": 0, "rejected_vs": 0, "rejected_bodhan": 0,
             "pending": 0, "done_today": 0}
    if not _APPROVED_CSV.exists() or not _ANNOTATION_DB.exists():
        return empty

    total = len(pd.read_csv(_APPROVED_CSV, usecols=["id"]))

    conn = sqlite3.connect(str(_ANNOTATION_DB))
    try:
        rows = conn.execute(
            "SELECT unique_file_id, pdf_decision, page_rejections, reviewer FROM pdf_annotations"
        ).fetchall()
    finally:
        conn.close()

    clean = with_issues = rejected = rejected_vs = rejected_bodhan = 0
    for uid, decision, page_rej_raw, reviewer in rows:
        decision = (decision or "").strip().lower()
        if decision == "accepted":
            has_issues = False
            try:
                pages = _json.loads(page_rej_raw or "[]")
                has_issues = any(len(p.get("issues", [])) > 0 for p in pages)
            except Exception:
                pass
            if has_issues:
                with_issues += 1
            else:
                clean += 1
        elif decision == "rejected":
            rejected += 1
            rev = (reviewer or "").lower()
            if "bodhan" in rev:
                rejected_bodhan += 1
            else:
                rejected_vs += 1

    approved = clean + with_issues
    reviewed = approved + rejected
    pending  = max(total - reviewed, 0)

    # done today = annotations created today (IST)
    try:
        conn2 = sqlite3.connect(str(_ANNOTATION_DB))
        today_str = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
        done_today = conn2.execute(
            "SELECT COUNT(*) FROM pdf_annotations "
            "WHERE pdf_decision IN ('accepted','rejected') AND created_at LIKE ?",
            (today_str + "%",)
        ).fetchone()[0]
        conn2.close()
    except Exception:
        done_today = 0

    return {
        "total": total, "reviewed": reviewed,
        "clean": clean, "with_issues": with_issues,
        "approved": approved, "rejected": rejected,
        "rejected_vs": rejected_vs, "rejected_bodhan": rejected_bodhan,
        "pending": pending, "done_today": done_today,
    }

@st.cache_data(ttl=300, show_spinner="Loading approved data…")
def load_bucket_data(exact_pages: bool = False) -> pd.DataFrame:
    """Load all approved student records from approved_uploads.csv.

    Metadata comes from the CSV; PDFs live under data_hw_collection_approved_vs/.
    exact_pages is accepted for API compatibility but ignored (pageCount is in the CSV).
    """
    raw = pd.read_csv(_APPROVED_CSV)

    def _grade_num(val):
        try:
            return int(str(val).replace("Grade", "").strip())
        except Exception:
            return None

    def _normalise(val, default="not mentioned"):
        v = str(val or "").lower().strip()
        return default if v in ("", "unknown", "none", "null", "nan") else v

    rows = []
    for _, r in raw.iterrows():
        grade = _grade_num(r.get("classGrade"))
        state_raw = str(r.get("state") or "").lower().strip().replace(" ", "_")
        medium = str(r.get("medium") or "not mentioned").strip().title()
        distributor_raw = str(r.get("uploadedByUserId") or "Not Mentioned").strip()
        distributor = distributor_raw.split("@")[0].strip() if "@" in distributor_raw else distributor_raw

        pdf_key = MINIO_PREFIX + str(r.get("s3Key") or "")

        rows.append({
            "student_name":             "not mentioned",
            "student_id":               str(r.get("studentId") or ""),
            "unique_file_id":           str(r.get("id") or ""),
            "school_id":                str(r.get("schoolId") or ""),
            "gender":                   str(r.get("gender") or "not mentioned").lower().strip(),
            "class":                    grade,
            "class_level":              CLASS_LEVEL_FROM_GRADE.get(grade, "Unknown") if grade else "Unknown",
            "school_name":              str(r.get("schoolName") or "").strip(),
            "school_type":              "",
            "board":                    _normalise(r.get("board")),
            "block":                    _normalise(r.get("block")),
            "district":                 str(r.get("district") or "").strip().title(),
            "state":                    state_raw.replace("_", " ").title() or "Unknown",
            "regional_language":        medium if medium not in ("Not Mentioned", "") else STATE_TO_LANGUAGE.get(state_raw, "Unknown"),
            "medium_of_instruction":    medium,
            "subject":                  str(r.get("subject") or "").lower().strip(),
            "sample_type":              str(r.get("sampleType") or "").lower().strip(),
            "num_pages":                int(r.get("pageCount") or 1),
            "date":                     pd.to_datetime(r.get("createdAt"), errors="coerce", utc=True),
            "rural_urban":              "",
            "aspirational_district":    bool(r.get("aspirationalDistrict", False)),
            "curriculum_type":          "",
            "performance_group":        "Not Mentioned",
            "capture_device":           str(r.get("captureDevice") or "").strip(),
            "orientation":              str(r.get("orientation") or "").strip(),
            "handedness":               _normalise(r.get("dominantHand")),
            "handwritten_or_handdrawn": str(r.get("handwritten") or "").lower().strip(),
            "printed":                  str(r.get("printed") or "").lower().strip(),
            "mixed_content":            str(r.get("mixedContent") or "").lower().strip(),
            "rotation":                 str(r.get("rotation") or "").lower().strip(),
            "distributor":              distributor,
            "pdf_key":                  pdf_key,
            "place":                    str(r.get("place") or "").strip().title(),
            "file_number":              int(r.get("fileNumber") or 0),
            "reviewed_at":              pd.to_datetime(r.get("reviewedAt"), errors="coerce", utc=True),
            "generate_metadata":        bool(r.get("generateMetadata", False)),
            "data_bucket":              bool(r.get("data_bucket", False)),
            "reject_stage":             "null",
            "review_flag":              "stage_vs",
            "issues_vs":                [],
            "issues_bodhan":            [],
            "flagged_pages_vs":         [],
            "flagged_pages_bodhan":     [],
            "page_issues_map_vs":       {},
        })

    if not rows:
        cols = ["student_name", "gender", "class", "class_level", "school_name",
                "board", "block", "district", "state", "regional_language",
                "medium_of_instruction", "subject", "sample_type", "num_pages",
                "date", "subject_category"]
        return pd.DataFrame(columns=cols)

    data = pd.DataFrame(rows)

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
    data["block"] = (
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

# ── State-wise page targets (Phase 1, source: State Wise Project Tracker.xlsx) ─
# Each entry: (display_label, [matching state names in df], target_pages)
# AP & Telangana share a single 200k target in the tracker.
_STATE_TARGET_ROWS = [
    ("Tamil Nadu",     ["Tamil Nadu"],                   200_000),
    ("AP & Telangana", ["Andhra Pradesh", "Telangana"],  200_000),
    ("Uttar Pradesh",  ["Uttar Pradesh"],                200_000),
    ("Karnataka",      ["Karnataka"],                    200_000),
    ("Maharashtra",    ["Maharashtra"],                  200_000),
    ("Odisha",         ["Odisha"],                       200_000),
    ("Kerala",         ["Kerala"],                       200_000),
    ("West Bengal",    ["West Bengal"],                  200_000),
    ("Gujarat",        ["Gujarat"],                      200_000),
    ("Punjab",         ["Punjab"],                       200_000),
]


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


# Load full upload counts (approved + unapproved) from raw CSV
_raw_counts = load_raw_counts()
_qa_counts  = load_qa_counts()

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

for _col in ("reject_stage", "review_flag", "corrections_ok"):
    if _col not in df.columns:
        df[_col] = "null" if _col == "reject_stage" else ("pending" if _col == "review_flag" else "")
for _col in ("issues_vs", "issues_bodhan", "flagged_pages_vs", "flagged_pages_bodhan"):
    if _col not in df.columns:
        df[_col] = [[] for _ in range(len(df))]
if "page_issues_map_vs" not in df.columns:
    df["page_issues_map_vs"] = [{} for _ in range(len(df))]

# ── Merge annotation DB data into df ─────────────────────────────────────────
_ann = load_annotation_data()
if not _ann.empty and "unique_file_id" in df.columns:
    _ann = _ann.set_index("unique_file_id")
    for _idx in df.index:
        _uid = df.at[_idx, "unique_file_id"]
        if _uid in _ann.index:
            _row = _ann.loc[_uid]
            df.at[_idx, "reject_stage"]        = _row["reject_stage"]
            df.at[_idx, "review_flag"]         = _row["review_flag"]
            df.at[_idx, "issues_vs"]           = _row["issues_vs"]
            df.at[_idx, "flagged_pages_vs"]    = _row["flagged_pages_vs"]
            df.at[_idx, "page_issues_map_vs"]  = _row.get("page_issues_map_vs", {})
            df.at[_idx, "corrections_ok"]      = _row.get("corrections_ok", "")

for _col in ("place", "generate_metadata", "data_bucket"):
    if _col not in df.columns:
        df[_col] = "" if _col == "place" else False
if "file_number" not in df.columns:
    df["file_number"] = 0
if "reviewed_at" not in df.columns:
    df["reviewed_at"] = pd.NaT

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

# ── Derive quality_status from reject_stage / review_flag / issues ────────────
def _quality_status(row) -> str:
    rs = str(row.get("reject_stage", "null")).lower().strip()
    if rs in ("reject_stage_vs",):
        return "Rejected (VS)"
    if rs in ("reject_stage_bodhan",):
        return "Rejected (Bodhan)"
    iv = row.get("issues_vs") or []
    ib = row.get("issues_bodhan") or []
    if iv or ib:
        return "Accepted w/ Issues"
    rv = str(row.get("review_flag", "pending")).lower().strip()
    if "stage_vs" in rv or "stage_bodhan" in rv:
        return "Clean"
    return "Pending"

df["quality_status"] = df.apply(_quality_status, axis=1)

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



_days_left = (pd.Timestamp("2026-07-05", tz="Asia/Kolkata") - pd.Timestamp.now(tz="Asia/Kolkata")).days

with st.sidebar:
    st.markdown("## OCR-VS")
    st.markdown("Data Collection Monitor")
    st.caption(f"Data: {_data_source}")
    _deadline_color = "#F43F5E" if _days_left <= 14 else "#F59E0B" if _days_left <= 30 else "#10B981"
    st.markdown(
        f'<div style="background:{_bg2}; border:1px solid {_border}; border-radius:10px; padding:10px 14px; margin-bottom:8px;">'
        f'<div style="font-size:0.7rem; text-transform:uppercase; letter-spacing:1px; color:{_text2}; font-weight:600;">Phase 1 Deadline</div>'
        f'<div style="font-size:1.05rem; font-weight:700; color:{_text}; margin-top:2px;">5 Jul 2026</div>'
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
    

    st.markdown("---")

    sel_board  = st.selectbox("Board", ["All"] + sorted(df["board"].unique().tolist()))
    sel_level  = st.selectbox("Class Level", ["All"] + sorted(df["class_level"].unique().tolist()))
    sel_subj   = st.selectbox("Subject Category", ["All"] + sorted(df["subject_category"].unique().tolist()))
    sel_gender = st.selectbox("Gender", ["All"] + sorted(df["gender"].unique().tolist()))
    sel_lang   = st.selectbox("Language", ["All"] + sorted([l for l in df["regional_language"].unique().tolist() if l and l != "Unknown"]))
    sel_state  = st.selectbox("State", ["All"] + sorted([s for s in df["state"].unique().tolist() if s and s != "Unknown"]))
    sel_block  = st.selectbox("Block", ["All"] + sorted(df["block"].unique().tolist()))
    sel_school = st.selectbox("School", ["All"] + sorted([s for s in df["school_name"].unique().tolist() if s]))

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
                  ("regional_language", sel_lang), ("state", sel_state),
                  ("block", sel_block), ("school_name", sel_school)]:
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
<div style="margin-top: -16px; padding-bottom: 4px;">
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
    _sc_bg     = "linear-gradient(135deg, #F43F5E 0%, #E11D48 100%)"  if _sc_open  else "linear-gradient(135deg, #d4500a 0%, #c04000 100%)"
    _sc_shadow = ("0 4px 20px rgba(244,63,94,0.4)"                    if _sc_open  else "0 4px 20px rgba(212,80,10,0.4)")
    _sc_border = ("1px solid rgba(244,63,94,0.6)"                     if _sc_open  else "1px solid rgba(212,80,10,0.6)")
    _sc_label  = "✕  Close Checker"                                   if _sc_open  else "🔍  Sample Checker"

    _sm_bg     = "linear-gradient(135deg, #F43F5E 0%, #E11D48 100%)"  if _sum_open else "linear-gradient(135deg, #10B981 0%, #059669 100%)"
    _sm_shadow = ("0 4px 20px rgba(244,63,94,0.4)"                    if _sum_open else "0 4px 20px rgba(16,185,129,0.4)")
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
    transition: all 0.2s ease !important; text-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
}}
div[data-testid="stButton"]:has(button[key="toggle_summary"]) button {{
    background: {_sm_bg} !important;
    border: {_sm_border} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important; font-size: 0.85rem !important;
    letter-spacing: 0.03em !important; border-radius: 12px !important;
    padding: 10px 16px !important; box-shadow: {_sm_shadow} !important;
    transition: all 0.2s ease !important; text-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
}}
div[data-testid="stButton"]:has(button[key="toggle_sample_checker"]) button:hover,
div[data-testid="stButton"]:has(button[key="toggle_summary"]) button:hover {{
    filter: brightness(1.1) !important; transform: translateY(-1px) !important;
}}
</style>
""", unsafe_allow_html=True)
    _b1, _b2 = st.columns([1, 1])
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

# ── Issue color palette (shared: sample checker, quality chart, popup) ────────
_ISSUE_COLORS = {
    "reject_bleed_through":            "#FB923C",  # orange       (warm)
    "reject_blur":                     "#2563eb",  # blue         (cool)
    "reject_lighting":                 "#FBBF24",  # amber        (warm)
    "reject_sparsity":                 "#06B6D4",  # cyan         (cool)
    "reject_rotation_mismatch":        "#E879F9",  # fuchsia      (vibrant)
    "reject_subject_content_mismatch": "#F472B6",  # pink         (vibrant)
    "reject_source_type_mismatch":     "#38BDF8",  # sky blue     (cool)
    "reject_cutoff":                   "#7c3aed",  # purple       (cool)
    "pii_flag":                        "#FCD34D",  # gold         (warm neutral)
}

def _issue_color(raw_key: str) -> str:
    return _ISSUE_COLORS.get(raw_key.lower(), "#94A3B8")


@st.dialog("PDF Viewer", width="large")
def _sc_pdf_dialog(sc_row, pg_issue_map, flagged_pages, issue_counts, pdf_key_val,
                   qs_label, qs_c, text, text2, text4, bg3, border_card, accent, accent_bg, accent_border):
    # ── header + issues shown immediately, caching happens in parallel ────
    cls_v = int(sc_row["class"]) if sc_row["class"] and not pd.isna(sc_row["class"]) else "?"
    st.markdown(f"""
<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px;'>
  <span style='background:{qs_c};color:#fff;font-size:0.7rem;font-weight:700;
               padding:3px 12px;border-radius:10px;'>{qs_label}</span>
  <span style='font-size:0.82rem;font-weight:700;color:{text};font-family:monospace;'>{sc_row["student_id"]}</span>
  <span style='font-size:0.72rem;color:{text2};'>· Class {cls_v} · {str(sc_row["subject"]).title()} · {int(sc_row["num_pages"])} pages</span>
  <span style='margin-left:auto;font-size:0.68rem;color:{text2};'>{str(sc_row["school_name"]).title()} · {sc_row["district"]}</span>
</div>""", unsafe_allow_html=True)

    if issue_counts:
        st.markdown("<div style='font-size:0.6rem;font-weight:700;color:" + text2 +
                    ";text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;'>Issues</div>",
                    unsafe_allow_html=True)
        st.markdown(
            "<div style='display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;'>" +
            "".join(
                f"<span style='background:{_issue_color(k)}33;color:{_issue_color(k)};"
                f"font-size:0.78rem;font-weight:700;padding:5px 14px;border-radius:10px;"
                f"border:1.5px solid {_issue_color(k)}66;'>"
                f"{k.replace('reject_','').replace('_',' ').title()}"
                f"<span style='background:{_issue_color(k)};color:#000;border-radius:6px;"
                f"padding:1px 7px;margin-left:8px;font-size:0.68rem;font-weight:800;'>{v}</span></span>"
                for k, v in sorted(issue_counts.items(), key=lambda x: -x[1])
            ) + "</div>",
            unsafe_allow_html=True,
        )

    # ── "Flagged Pages" label + inline cache spinner side by side ─────────
    if flagged_pages:
        _fp_label_col, _fp_spin_col = st.columns([3, 5])
        _fp_label_col.markdown(
            f"<div style='font-size:0.6rem;font-weight:700;color:{text2};"
            f"text-transform:uppercase;letter-spacing:0.08em;padding-top:6px;'>Flagged Pages</div>",
            unsafe_allow_html=True,
        )
        # fetch URL (cached after first call)
        _d_url, _d_err, _d_ext = get_presigned_url_cached(pdf_key_val)
        # cache all pages — spinner shows only in the right column, rest of dialog already visible
        with _fp_spin_col:
            with st.spinner(f"Caching {len(flagged_pages)} page(s)…"):
                _pages_cache = render_all_flagged_pages(pdf_key_val, tuple(sorted(flagged_pages)))
    else:
        _d_url, _d_err, _d_ext = get_presigned_url_cached(pdf_key_val)
        _pages_cache = {}

    # ── flagged page buttons + images ─────────────────────────────────────
    if flagged_pages:

        def _pg_color(pg):
            issues = pg_issue_map.get(pg, [])
            return _issue_color(issues[0]) if issues else "#94A3B8"

        # target buttons by their st-key-{key} wrapper class — reliable in Streamlit 1.38+
        _all_btn_css = "<style>"
        for _pg in flagged_pages:
            _c = _pg_color(_pg)
            _active_now = (st.session_state.get("dlg_show_page") == _pg)
            _bg     = f"{_c}44" if _active_now else f"{_c}18"
            _border = f"{_c}cc" if _active_now else f"{_c}aa"
            _all_btn_css += (
                f".st-key-dlg_pg_{_pg} button {{"
                f"background:{_bg}!important;border:1.5px solid {_border}!important;"
                f"color:{_c}!important;font-weight:700!important;border-radius:8px!important;}}"
                f".st-key-dlg_pg_{_pg} button:hover {{"
                f"background:{_c}33!important;border-color:{_c}!important;}}"
            )
        _all_btn_css += "</style>"
        st.markdown(_all_btn_css, unsafe_allow_html=True)

        # page buttons row
        _max_per_row = 12
        for _row_start in range(0, len(flagged_pages), _max_per_row):
            _row_pgs = flagged_pages[_row_start: _row_start + _max_per_row]
            _pb_cols = st.columns(len(_row_pgs))
            for _ci, _pg in enumerate(_row_pgs):
                _active = (st.session_state.get("dlg_show_page") == _pg)
                if _pb_cols[_ci].button(f"p.{_pg}", key=f"dlg_pg_{_pg}", use_container_width=True,
                                        help=", ".join(i.replace("_"," ").title() for i in pg_issue_map.get(_pg, []))):
                    st.session_state["dlg_show_page"] = None if _active else _pg
                    st.session_state["dlg_show_full_pdf"] = False
                    st.rerun()

        # show selected page image
        _sel_pg = st.session_state.get("dlg_show_page")
        if _sel_pg:
            _pg_issues_sel = pg_issue_map.get(_sel_pg, [])
            _sel_chips = "".join(
                f"<span style='background:{_issue_color(i)}33;color:{_issue_color(i)};"
                f"font-size:0.65rem;font-weight:600;padding:2px 9px;border-radius:8px;"
                f"border:1px solid {_issue_color(i)}66;'>{i.replace('reject_','').replace('_',' ').title()}</span>"
                for i in dict.fromkeys(_pg_issues_sel)
            ) or f"<span style='font-size:0.62rem;color:{text4};'>No issue label</span>"
            _pg_color_sel = _pg_color(_sel_pg)
            _hdr_col, _close_col = st.columns([8, 1])
            _hdr_col.markdown(f"""
<div style='border:1px solid {_pg_color_sel}44;border-radius:10px;overflow:hidden;margin:10px 0 8px;'>
  <div style='background:{_pg_color_sel}11;padding:8px 14px;border-bottom:1px solid {_pg_color_sel}33;
              display:flex;align-items:center;gap:10px;flex-wrap:wrap;'>
    <span style='font-size:0.72rem;font-weight:700;color:{_pg_color_sel};'>Page {_sel_pg}</span>
    {_sel_chips}
  </div>
</div>""", unsafe_allow_html=True)
            if _close_col.button("✕", key="dlg_close_img", help="Close image"):
                st.session_state["dlg_show_page"] = None
                st.rerun()
            _png = _pages_cache.get(_sel_pg)
            if _png:
                st.image(_png, use_container_width=True)
            else:
                with st.spinner(f"Rendering page {_sel_pg}…"):
                    _png = render_pdf_page_as_png(pdf_key_val, _sel_pg)
                if _png:
                    st.image(_png, use_container_width=True)
                else:
                    st.warning(f"Could not render page {_sel_pg}.")

    # ── View Full PDF toggle ──────────────────────────────────────────────
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _show_full = st.session_state.get("dlg_show_full_pdf", False)
    if st.button("📄  View Full PDF" if not _show_full else "▲  Hide Full PDF",
                 key="dlg_toggle_pdf", use_container_width=False):
        st.session_state["dlg_show_full_pdf"] = not _show_full
        st.rerun()

    if st.session_state.get("dlg_show_full_pdf") and _d_url and _d_ext == "pdf":
        _jump = st.session_state.get("dlg_show_page")
        _src = f"{_d_url}#page={_jump}" if _jump else _d_url
        st.markdown(f"""
<div style='border:1px solid {border_card};border-radius:10px;overflow:hidden;margin-top:8px;'>
  <div style='background:#1E1E2E;padding:6px 14px;display:flex;align-items:center;
              justify-content:space-between;border-bottom:1px solid {border_card};'>
    <span style='font-size:0.72rem;color:{text2};font-weight:600;'>{pdf_key_val.split("/")[-1]}</span>
    <a href="{_d_url}" target="_blank"
       style='font-size:0.7rem;color:{accent};font-weight:600;text-decoration:none;
              background:{accent_bg};padding:2px 10px;border-radius:6px;
              border:1px solid {accent_border};'>↗ Open in new tab</a>
  </div>
  <iframe src="{_src}" width="100%" height="860" style="border:none;display:block;"></iframe>
</div>""", unsafe_allow_html=True)
    elif st.session_state.get("dlg_show_full_pdf") and _d_err:
        st.error(f"Could not load PDF: {_d_err}")


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

    _sc_fa, _sc_fb, _sc_fc, _sc_fd = st.columns([1, 1, 1, 1])
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

    # Quality status filter (honours deeplink preset from Quality Analysis panel)
    _quality_status_opts = ["All", "Pending", "Clean", "Accepted w/ Issues", "Rejected (VS)", "Rejected (Bodhan)"]
    _preset = st.session_state.pop("sc_quality_preset", None)
    _preset_map = {
        "rejected": "Rejected (VS)",
        "flagged": "Accepted w/ Issues",
        "clean": "Clean"  # For viewing accepted samples
    }
    _quality_default = _preset_map.get(_preset, "All")
    _quality_default_idx = _quality_status_opts.index(_quality_default) if _quality_default in _quality_status_opts else 0
    _sel_sc_quality = _sc_fd.selectbox(
        "Quality Status", _quality_status_opts,
        index=_quality_default_idx, key="sc_quality",
    )
    if _sel_sc_quality == "Rejected (VS)" or _sel_sc_quality == "Rejected (Bodhan)":
        _sc_df = _sc_df[_sc_df["quality_status"] == _sel_sc_quality]
    elif _sel_sc_quality != "All":
        _sc_df = _sc_df[_sc_df["quality_status"] == _sel_sc_quality]

    _sc_fe, _sc_ff, _sc_fg, _sc_fh = st.columns(4)

    _board_opts_sc = ["All"] + sorted([b for b in _sc_df["board"].unique() if b and b not in ("Other", "")])
    _sel_sc_board = _sc_fe.selectbox("Board", _board_opts_sc, key="sc_board")
    if _sel_sc_board != "All":
        _sc_df = _sc_df[_sc_df["board"] == _sel_sc_board]

    # Issues: show only rows that have at least one flagged issue vs "No Issues"
    _issues_opts = ["All", "Has Issues", "No Issues"]
    _sel_sc_issues = _sc_ff.selectbox("Issues", _issues_opts, key="sc_issues")
    if _sel_sc_issues == "Has Issues":
        _sc_df = _sc_df[_sc_df["issues_vs"].apply(lambda x: bool(x and len(x) > 0))]
    elif _sel_sc_issues == "No Issues":
        _sc_df = _sc_df[_sc_df["issues_vs"].apply(lambda x: not (x and len(x) > 0))]

    _corr_vals = sorted([v for v in _sc_df["corrections_ok"].dropna().unique() if v != ""])
    _corr_opts = ["All"] + _corr_vals
    _sel_sc_corr = _sc_fg.selectbox("Corrections OK", _corr_opts, key="sc_corrections_ok")
    if _sel_sc_corr != "All":
        _sc_df = _sc_df[_sc_df["corrections_ok"] == _sel_sc_corr]

    _lang_opts_sc = ["All"] + sorted([l for l in _sc_df["regional_language"].unique() if l and l != "Unknown"])
    _sel_sc_lang = _sc_fh.selectbox("Language", _lang_opts_sc, key="sc_lang")
    if _sel_sc_lang != "All":
        _sc_df = _sc_df[_sc_df["regional_language"] == _sel_sc_lang]

    n_total = len(_sc_df)
    _SC_PAGE_SIZE = 10

    if "sc_page" not in st.session_state:
        st.session_state["sc_page"] = 0
    if "sc_view_idx" not in st.session_state:
        st.session_state["sc_view_idx"] = None
    if "sc_popup_pdf_url" not in st.session_state:
        st.session_state["sc_popup_pdf_url"] = None
    if "sc_popup_ext" not in st.session_state:
        st.session_state["sc_popup_ext"] = None
    if "sc_popup_show_page" not in st.session_state:
        st.session_state["sc_popup_show_page"] = None

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

        # ── Open dialog overlay when a row's View button is clicked ─────
        _view_idx = st.session_state.get("sc_view_idx")
        if _view_idx is not None and _view_idx < n_total:
            _sc_row      = _sc_df_reset.iloc[_view_idx]
            _pdf_key_val = _sc_row["pdf_key"]
            _row_qs      = str(_sc_row.get("quality_status", "Pending"))
            _pg_issue_map_vs = _sc_row.get("page_issues_map_vs") or {}
            _popup_issue_counts: dict[str, int] = {}
            for _piss in _pg_issue_map_vs.values():
                for _iss in _piss:
                    _popup_issue_counts[_iss] = _popup_issue_counts.get(_iss, 0) + 1
            _row_fp_vs  = list(_sc_row.get("flagged_pages_vs")  or [])
            _row_fp_bo  = list(_sc_row.get("flagged_pages_bodhan") or [])
            _row_fp_all = sorted(set([int(p) for p in (_row_fp_vs + _row_fp_bo) if isinstance(p, (int, float))]))
            _qs_c_map = {
                "Clean":             "#34D399",
                "Accepted w/ Issues":"#FBBF24",
                "Rejected (VS)":     "#F43F5E",
                "Rejected (Bodhan)": "#F43F5E",
                "Pending":           "#6B7280",
            }
            _qs_c     = _qs_c_map.get(_row_qs, "#6B7280")
            _qs_label = "Rejected" if "Rejected" in _row_qs else _row_qs
            # reset dialog-internal state only when a different row is opened
            if st.session_state.get("_dlg_last_idx") != _view_idx:
                st.session_state["dlg_show_page"]     = None
                st.session_state["dlg_show_full_pdf"] = False
                st.session_state["_dlg_last_idx"]     = _view_idx
            _sc_pdf_dialog(
                sc_row=_sc_row,
                pg_issue_map=_pg_issue_map_vs,
                flagged_pages=_row_fp_all,
                issue_counts=_popup_issue_counts,
                pdf_key_val=_pdf_key_val,
                qs_label=_qs_label,
                qs_c=_qs_c,
                text=_text, text2=_text2, text4=_text4,
                bg3=_bg3, border_card=_border_card,
                accent=_accent, accent_bg=_accent_bg, accent_border=_accent_border,
            )

        # ── Paginated table ────────────────────────────────────────────────
        _tbl_cols   = ["#", "Student", "Cls", "Subject", "Pgs", "Status", "Issues", "Date", ""]
        _col_widths = [0.3, 1.1, 0.4, 0.9, 0.35, 0.9, 1.4, 0.65, 0.45]
        _hdr_cols = st.columns(_col_widths)
        for _ci, _ch in enumerate(_tbl_cols):
            _hdr_cols[_ci].markdown(
                f"<div style='font-size:0.65rem;font-weight:700;color:{_text2};"
                f"text-transform:uppercase;letter-spacing:.07em;padding:4px 0;'>{_ch}</div>",
                unsafe_allow_html=True)
        st.markdown(f"<div style='height:1px;background:{_border_card};margin-bottom:4px;'></div>", unsafe_allow_html=True)

        _STATUS_BADGE = {
            "Clean":             ("<span style='background:#34D399;color:#000;font-size:0.6rem;font-weight:700;"
                                  "padding:2px 7px;border-radius:10px;white-space:nowrap;'>✓ Clean</span>"),
            "Accepted w/ Issues":("<span style='background:#FBBF24;color:#000;font-size:0.6rem;font-weight:700;"
                                  "padding:2px 7px;border-radius:10px;white-space:nowrap;'>⚠ Issues</span>"),
            "Rejected (VS)":     ("<span style='background:#F43F5E;color:#fff;font-size:0.6rem;font-weight:700;"
                                  "padding:2px 7px;border-radius:10px;white-space:nowrap;'>✕ Rejected</span>"),
            "Rejected (Bodhan)": ("<span style='background:#F43F5E;color:#fff;font-size:0.6rem;font-weight:700;"
                                  "padding:2px 7px;border-radius:10px;white-space:nowrap;'>✕ Rejected</span>"),
            "Pending":           ("<span style='background:#6B7280;color:#fff;font-size:0.6rem;font-weight:700;"
                                  "padding:2px 7px;border-radius:10px;white-space:nowrap;'>… Pending</span>"),
        }

        for _abs_i, _r in zip(range(_page_start, _page_start + len(_page_rows)), _page_rows.iterrows()):
            _r = _r[1]  # iterrows yields (index, Series)
            _rc = st.columns(_col_widths)
            _cl  = int(_r["class"]) if _r["class"] and not pd.isna(_r["class"]) else "?"
            _dt  = str(_r["date"])[:10] if pd.notna(_r["date"]) else "—"
            _qs  = str(_r.get("quality_status", "Pending"))
            _badge_html = _STATUS_BADGE.get(_qs, _STATUS_BADGE["Pending"])

            # Build issue count chips for this row
            _row_pg_map = _r.get("page_issues_map_vs") or {}
            _row_issue_counts: dict[str, int] = {}
            for _piss in _row_pg_map.values():
                for _iss in _piss:
                    _row_issue_counts[_iss] = _row_issue_counts.get(_iss, 0) + 1
            if _row_issue_counts:
                _issue_chips_tbl = " ".join(
                    f"<span style='background:{_issue_color(k)}22;color:{_issue_color(k)};"
                    f"font-size:0.58rem;font-weight:700;padding:1px 6px;border-radius:6px;"
                    f"border:1px solid {_issue_color(k)}55;white-space:nowrap;'>"
                    f"{k.replace('reject_','').replace('_',' ').title()} "
                    f"<b style='background:{_issue_color(k)};color:#000;border-radius:4px;padding:0 4px;'>{v}</b></span>"
                    for k, v in sorted(_row_issue_counts.items(), key=lambda x: -x[1])
                )
            else:
                _issue_chips_tbl = f"<span style='color:{_text2};font-size:0.65rem;'>—</span>"

            _rc[0].markdown(f"<div style='font-size:0.75rem;color:{_text2};padding:7px 0;'>{_abs_i+1}</div>", unsafe_allow_html=True)
            _rc[1].markdown(f"<div style='font-size:0.72rem;color:{_text3};font-weight:600;padding:7px 0;font-family:monospace;'>{str(_r['student_id'])}</div>", unsafe_allow_html=True)
            _rc[2].markdown(f"<div style='font-size:0.75rem;color:{_text3};padding:7px 0;'>{_cl}</div>", unsafe_allow_html=True)
            _rc[3].markdown(f"<div style='font-size:0.75rem;color:{_text3};padding:7px 0;'>{str(_r['subject']).title()}</div>", unsafe_allow_html=True)
            _rc[4].markdown(f"<div style='font-size:0.75rem;color:{_text3};padding:7px 0;'>{int(_r['num_pages'])}</div>", unsafe_allow_html=True)
            _rc[5].markdown(f"<div style='padding:5px 0;'>{_badge_html}</div>", unsafe_allow_html=True)
            _rc[6].markdown(f"<div style='padding:5px 0;line-height:1.8;'>{_issue_chips_tbl}</div>", unsafe_allow_html=True)
            _rc[7].markdown(f"<div style='font-size:0.75rem;color:{_text2};padding:7px 0;'>{_dt}</div>", unsafe_allow_html=True)
            if _rc[8].button("View", key=f"sc_view_{_abs_i}", use_container_width=True):
                st.session_state["sc_view_idx"]       = _abs_i
                st.session_state["sc_jump_page"]       = None
                st.session_state["sc_popup_pdf_url"]   = None
                st.session_state["sc_popup_ext"]       = None
                st.session_state["sc_popup_show_page"] = None
                st.session_state["dlg_show_page"]      = None
                st.session_state["dlg_show_full_pdf"]  = False
                render_all_flagged_pages.clear()
                render_pdf_page_as_png.clear()
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
# page counts per quality bucket — for the main progress bar
_accepted_pages = int(_qa_counts["approved"] * total_pages / max(_qa_counts["reviewed"], 1)) if _qa_counts["reviewed"] else 0
# use actual page sums from filtered where annotation data is joined
_accepted_pages = int(filtered[filtered["quality_status"].isin(["Clean", "Accepted w/ Issues"])]["num_pages"].sum())
_rejected_pages = int(filtered[filtered["quality_status"].isin(["Rejected (VS)", "Rejected (Bodhan)"])]["num_pages"].sum())
_pending_pages  = total_pages - _accepted_pages - _rejected_pages
_acc_pct  = round(_accepted_pages / _PHASE1_TOTAL_PAGES_FULL * 100, 1)
_rej_pct  = round(_rejected_pages / _PHASE1_TOTAL_PAGES_FULL * 100, 1)
_pend_pct = round(_pending_pages  / _PHASE1_TOTAL_PAGES_FULL * 100, 1)
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
  <span style='font-size:2.6rem;font-weight:900;color:#d4500a;
               font-family:"Courier New","Courier",monospace;
               letter-spacing:-1px;text-shadow:0 0 20px rgba(212,80,10,0.25);'>{n_students:,}</span>
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
    _deadline_str = pd.Timestamp("2026-07-05", tz="Asia/Kolkata").strftime("%d %b %Y")
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
  <div style='background:rgba(255,255,255,0.08);border-radius:8px;height:14px;overflow:hidden;border:1px solid rgba(255,255,255,0.08);display:flex;'>
    <div style='width:{_acc_pct:.1f}%;background:linear-gradient(90deg,#10B98199,#10B981);height:100%;
                box-shadow:0 0 10px #10B98155;transition:width 0.4s ease;flex-shrink:0;'></div>
    <div style='width:{_rej_pct:.1f}%;background:linear-gradient(90deg,#F43F5E99,#F43F5E);height:100%;
                box-shadow:0 0 10px #F43F5E55;transition:width 0.4s ease;flex-shrink:0;'></div>
    <div style='width:{_pend_pct:.1f}%;background:linear-gradient(90deg,#F59E0B99,#F59E0B);height:100%;
                box-shadow:0 0 10px #F59E0B55;transition:width 0.4s ease;flex-shrink:0;'></div>
  </div>
  <div style='display:flex;gap:16px;margin-top:6px;flex-wrap:wrap;'>
    <span style='font-size:0.7rem;font-weight:600;color:#10B981;'>
      ● Accepted &nbsp;{_accepted_pages:,} <span style='color:{_text4};font-weight:400;'>({_acc_pct}%)</span>
    </span>
    <span style='font-size:0.7rem;font-weight:600;color:#F43F5E;'>
      ● Rejected &nbsp;{_rejected_pages:,} <span style='color:{_text4};font-weight:400;'>({_rej_pct}%)</span>
    </span>
    <span style='font-size:0.7rem;font-weight:600;color:#F59E0B;'>
      ● Pending &nbsp;{_pending_pages:,} <span style='color:{_text4};font-weight:400;'>({_pend_pct}%)</span>
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── State-wise Progress toggle ────────────────────────────────────────────
    if "show_state_targets" not in st.session_state:
        st.session_state["show_state_targets"] = False
    _stp_open = st.session_state["show_state_targets"]
    _stp_label = "▲ Hide State Targets" if _stp_open else "▼ State-wise Targets"
    st.markdown(f"""
<style>
div[data-testid="stButton"]:has(button[key="toggle_state_targets"]) button {{
    background: {_accent_bg if _stp_open else _bg2} !important;
    border: 1px solid {_accent_border if _stp_open else _border_card} !important;
    color: {_accent if _stp_open else _text2} !important;
    font-size: 0.72rem !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: 0.08em !important;
    border-radius: 8px !important; padding: 5px 14px !important;
    width: 100% !important;
}}
</style>""", unsafe_allow_html=True)
    if st.button(_stp_label, key="toggle_state_targets"):
        st.session_state["show_state_targets"] = not _stp_open
        st.rerun()

    if st.session_state["show_state_targets"]:
        st.markdown(f"""
<div style='font-size:0.65rem;font-weight:500;color:{_text4};letter-spacing:0;
            margin:6px 0 10px;'>Phase 1 · 2,00,000 pages / state · Jul 5 2026</div>
""", unsafe_allow_html=True)
        _st_cols_a = st.columns(5)
        _st_cols_b = st.columns(5)
        for _si, (_slabel, _snames, _starget) in enumerate(_STATE_TARGET_ROWS):
            _scol = _st_cols_a[_si] if _si < 5 else _st_cols_b[_si - 5]
            _spages = int(df[df["state"].isin(_snames)]["num_pages"].sum())
            _spct   = min(_spages / _starget * 100, 100) if _starget else 0
            _sclr   = "#10B981" if _spct >= 100 else "#F59E0B" if _spct >= 60 else "#F43F5E"
            _scol.markdown(f"""
<div style='background:{_bg2};border:1px solid {_border_card};border-radius:12px;
            padding:10px 12px 8px;margin-bottom:12px;'>
  <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px;'>
    <div style='font-size:0.72rem;font-weight:700;color:{_text3};white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis;max-width:80%;'>{_slabel}</div>
    <div style='font-size:0.68rem;font-weight:800;color:{_sclr};margin-left:4px;'>{_spct:.0f}%</div>
  </div>
  <div style='background:{_progress_track};border-radius:5px;height:6px;overflow:hidden;'>
    <div style='width:{_spct:.1f}%;background:linear-gradient(90deg,{_sclr}bb,{_sclr});
                height:100%;border-radius:5px;box-shadow:0 0 6px {_sclr}44;'></div>
  </div>
  <div style='font-size:0.6rem;color:{_text4};margin-top:4px;'>
    {_spages:,} / {_starget:,}
  </div>
</div>""", unsafe_allow_html=True)

    # ── Left / Right split: Collection | Quality Analysis ──
    _n_subj_unique = filtered["subject"].nunique()
    _col_left, _col_sep, _col_right = st.columns([1, 0.02, 1], gap="small")

    # ════════════════════════════════════════════════════════
    # LEFT — COLLECTION
    # ════════════════════════════════════════════════════════
    with _col_left:
        st.markdown(f"""
<div style='font-size:0.72rem;font-weight:700;color:#d4500a;text-transform:uppercase;
            letter-spacing:0.12em;margin-bottom:12px;display:flex;align-items:center;gap:8px;'>
  <span style='display:inline-block;width:4px;height:16px;background:#d4500a;border-radius:3px;'></span>
  Collection
</div>""", unsafe_allow_html=True)

        _c1, _c2 = st.columns(2)

        # ── States card ──
        with _c1:
            _state_rows = (
                filtered[~filtered["state"].isin(["Not Mentioned", "Unknown", ""])]
                .groupby("state")
                .agg(Districts=("district", "nunique"), Blocks=("block", "nunique"), Pages=("num_pages", "sum"))
                .reset_index()
                .rename(columns={"state": "State"})
                .sort_values("Pages", ascending=True)
            )
            st.markdown(f"""
<div style='background:rgba(212,80,10,0.06);border:1px solid rgba(212,80,10,0.2);
            border-radius:14px;padding:14px 16px 10px;margin-bottom:6px;'>
  <div style='font-size:0.65rem;font-weight:700;color:#d4500a;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>States</div>
  <div style='font-size:1.8rem;font-weight:900;color:{_text};line-height:1;'>{n_states}</div>
  <div style='font-size:0.7rem;color:{_text3};margin-top:2px;'>{n_districts} districts · {n_blocks} blocks</div>
</div>""", unsafe_allow_html=True)
            if not _state_rows.empty:
                if "states_chart_open" not in st.session_state:
                    st.session_state["states_chart_open"] = False
                if st.toggle("Show chart", key="states_chart_toggle", value=st.session_state["states_chart_open"]):
                    st.session_state["states_chart_open"] = True
                    _state_rows = _state_rows.sort_values("Pages", ascending=False)
                    _fig_states = go.Figure(go.Bar(
                        x=_state_rows["State"],
                        y=_state_rows["Pages"],
                        marker_color="#d4500a",
                        text=[f"{int(v):,}" for v in _state_rows["Pages"]],
                        textposition="outside",
                        textfont=dict(size=10, color=_chart_text),
                    ))
                    _fig_states.update_layout(**chart_layout(height=220))
                    _fig_states.update_layout(margin=dict(l=4, r=4, t=20, b=4))
                    _fig_states.update_yaxes(visible=False)
                    _fig_states.update_xaxes(tickfont=dict(size=10))
                    st.plotly_chart(_fig_states, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.session_state["states_chart_open"] = False
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
        # ── Languages card (top-right) ──
        with _c2:
            _lang_rows = (
                filtered[~filtered["regional_language"].isin(["Unknown", ""])]
                .groupby("regional_language")["num_pages"]
                .sum().sort_values(ascending=True)
                .reset_index()
                .rename(columns={"regional_language": "Language", "num_pages": "Pages"})
            )
            st.markdown(f"""
<div style='background:rgba(192,132,252,0.08);border:1px solid rgba(192,132,252,0.2);
            border-radius:14px;padding:14px 16px 10px;margin-bottom:6px;'>
  <div style='font-size:0.65rem;font-weight:700;color:#C084FC;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>Languages</div>
  <div style='font-size:1.8rem;font-weight:900;color:{_text};line-height:1;'>{n_languages}</div>
  <div style='font-size:0.7rem;color:{_text3};margin-top:2px;'>regional languages</div>
</div>""", unsafe_allow_html=True)
            if not _lang_rows.empty:
                if "langs_chart_open" not in st.session_state:
                    st.session_state["langs_chart_open"] = False
                if st.toggle("Show chart", key="langs_chart_toggle", value=st.session_state["langs_chart_open"]):
                    st.session_state["langs_chart_open"] = True
                    _lang_rows = _lang_rows.sort_values("Pages", ascending=False)
                    _fig_lang = go.Figure(go.Bar(
                        x=_lang_rows["Language"].str.title(),
                        y=_lang_rows["Pages"],
                        marker_color="#C084FC",
                        text=[f"{int(v):,}" for v in _lang_rows["Pages"]],
                        textposition="outside",
                        textfont=dict(size=10, color=_chart_text),
                    ))
                    _fig_lang.update_layout(**chart_layout(height=220))
                    _fig_lang.update_layout(margin=dict(l=4, r=4, t=20, b=4))
                    _fig_lang.update_yaxes(visible=False)
                    _fig_lang.update_xaxes(tickfont=dict(size=10))
                    st.plotly_chart(_fig_lang, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.session_state["langs_chart_open"] = False
            if "lang_detail_open" not in st.session_state:
                st.session_state["lang_detail_open"] = False
            if st.button("📊 Detailed Stats →", key="lang_detail_btn", use_container_width=True):
                st.session_state["lang_detail_open"] = not st.session_state["lang_detail_open"]
                st.rerun()

        _c3, _c4 = st.columns(2)

        # ── Students card ──
        with _c3:
            _class_page_rows = (
                filtered[filtered["class"].notna()]
                .groupby("class")["num_pages"]
                .sum().reset_index()
                .rename(columns={"class": "Class", "num_pages": "Pages"})
                .sort_values("Class")
            )
            _class_page_rows["Class"] = _class_page_rows["Class"].astype(int)
            st.markdown(f"""
<div style='background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.2);
            border-radius:14px;padding:14px 16px 10px;margin-bottom:6px;'>
  <div style='font-size:0.65rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>Students</div>
  <div style='font-size:1.8rem;font-weight:900;color:{_text};line-height:1;'>{n_students:,}</div>
  <div style='font-size:0.7rem;color:{_text3};margin-top:2px;'>{n_schools} schools · {round(n_students/n_schools,1) if n_schools else 0} avg/school</div>
</div>""", unsafe_allow_html=True)
            if not _class_page_rows.empty:
                _fig_cls = go.Figure(go.Bar(
                    x=[f"Cls {c}" for c in _class_page_rows["Class"]],
                    y=_class_page_rows["Pages"],
                    marker_color="#FBBF24",
                    text=[f"{int(v):,}" for v in _class_page_rows["Pages"]],
                    textposition="outside",
                    textfont=dict(size=10, color=_chart_text),
                ))
                _fig_cls.update_layout(**chart_layout(height=220))
                _fig_cls.update_layout(margin=dict(l=4, r=4, t=20, b=4))
                _fig_cls.update_yaxes(visible=False)
                _fig_cls.update_xaxes(tickfont=dict(size=10))
                st.plotly_chart(_fig_cls, use_container_width=True, config={"displayModeBar": False})
            if "students_detail_open" not in st.session_state:
                st.session_state["students_detail_open"] = False
            if st.button("📊 Detailed Stats →", key="students_detail_btn", use_container_width=True):
                st.session_state["students_detail_open"] = not st.session_state["students_detail_open"]
                st.rerun()

        # ── Subjects card (bottom-right) ──
        with _c4:
            _subj_rows = (
                filtered.groupby("subject")["num_pages"]
                .sum().sort_values(ascending=True)
                .reset_index()
                .rename(columns={"subject": "Subject", "num_pages": "Pages"})
            )
            st.markdown(f"""
<div style='background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.2);
            border-radius:14px;padding:14px 16px 10px;margin-bottom:6px;'>
  <div style='font-size:0.65rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:2px;'>Subjects</div>
  <div style='font-size:1.8rem;font-weight:900;color:{_text};line-height:1;'>{_n_subj_unique}</div>
  <div style='font-size:0.7rem;color:{_text3};margin-top:2px;'>{int(filtered["num_pages"].sum()):,} total pages</div>
</div>""", unsafe_allow_html=True)
            if not _subj_rows.empty:
                _subj_rows = _subj_rows.sort_values("Pages", ascending=False)
                _fig_subj = go.Figure(go.Bar(
                    x=_subj_rows["Subject"].str.title(),
                    y=_subj_rows["Pages"],
                    marker_color="#34D399",
                    text=[f"{int(v):,}" for v in _subj_rows["Pages"]],
                    textposition="outside",
                    textfont=dict(size=10, color=_chart_text),
                ))
                _fig_subj.update_layout(**chart_layout(height=220))
                _fig_subj.update_layout(margin=dict(l=4, r=4, t=20, b=4))
                _fig_subj.update_yaxes(visible=False)
                _fig_subj.update_xaxes(tickfont=dict(size=10))
                st.plotly_chart(_fig_subj, use_container_width=True, config={"displayModeBar": False})
            if "subject_detail_open" not in st.session_state:
                st.session_state["subject_detail_open"] = False
            if st.button("📊 Detailed Stats →", key="subj_detail_btn", use_container_width=True):
                st.session_state["subject_detail_open"] = not st.session_state["subject_detail_open"]
                st.rerun()

    with _col_sep:
        st.markdown(f"""
<div style='width:1px;background:{_border};min-height:500px;margin:0 auto;'></div>
""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # RIGHT — QUALITY ANALYSIS
    # ════════════════════════════════════════════════════════
    with _col_right:
        st.markdown(f"""
<div style='font-size:0.72rem;font-weight:700;color:#34D399;text-transform:uppercase;
            letter-spacing:0.12em;margin-bottom:12px;display:flex;align-items:center;gap:8px;'>
  <span style='display:inline-block;width:4px;height:16px;background:#34D399;border-radius:3px;'></span>
  Quality Analysis
</div>""", unsafe_allow_html=True)

        # ── QA stats from annotation DB + approved_uploads.csv ────────────
        _q_total    = _qa_counts["total"]
        _q_reviewed = _qa_counts["reviewed"]
        _q_clean    = _qa_counts["clean"]
        _q_issues   = _qa_counts["with_issues"]
        _q_accepted = _qa_counts["approved"]       # clean + w/issues
        _q_rejected = _qa_counts["rejected"]
        _q_rej_vs   = _qa_counts["rejected_vs"]
        _q_rej_bo   = _qa_counts["rejected_bodhan"]
        _q_pending  = _qa_counts["pending"]        # total − reviewed
        _done_today = _qa_counts["done_today"]
        # percentages vs total uploads
        _q_accept_pct  = round(_q_accepted / _q_total * 100, 1) if _q_total else 0
        _q_rej_pct     = round(_q_rejected / _q_total * 100, 1) if _q_total else 0
        _q_issue_pct   = round(_q_issues   / _q_total * 100, 1) if _q_total else 0
        _q_pending_pct  = round(_q_pending  / _q_total * 100, 1) if _q_total else 0
        _q_reviewed_pct = round(_q_reviewed / _q_total * 100, 1) if _q_total else 0
        # percentages vs reviewed (for breakdown bars)
        _q_accept_of_reviewed_pct = round(_q_accepted / _q_reviewed * 100, 1) if _q_reviewed else 0
        _q_reject_of_reviewed_pct = round(_q_rejected / _q_reviewed * 100, 1) if _q_reviewed else 0
        # page-level counts from filtered (for pages context)
        _q_total_pages    = int(filtered["num_pages"].sum())
        _q_approved_pages = int(filtered[filtered["quality_status"].isin(["Clean", "Accepted w/ Issues"])]["num_pages"].sum())
        _q_rejected_pages = int(filtered[filtered["quality_status"].isin(["Rejected (VS)", "Rejected (Bodhan)"])]["num_pages"].sum())
        _q_clean_pages    = int(filtered[filtered["quality_status"] == "Clean"]["num_pages"].sum())
        _q_issues_pages   = int(filtered[filtered["quality_status"] == "Accepted w/ Issues"]["num_pages"].sum())
        _q_reviewed_pages = _q_approved_pages + _q_rejected_pages
        _q_pending_pages  = _q_total_pages - _q_reviewed_pages
        _q_done_today_pages = int(filtered[filtered.get("reviewed_date", pd.Series(dtype="object")) == pd.Timestamp.today().date()]["num_pages"].sum()) if "reviewed_date" in filtered.columns else 0

        # ── Upload summary: Total PDFs + accepted/rejected in pages ──────
        _complete_pct    = round(_q_reviewed / _q_total * 100, 1) if _q_total else 0
        _q_reviewed_pct  = round(_q_reviewed / _q_total * 100, 1) if _q_total else 0
        _q_pending_pct   = round(_q_pending  / _q_total * 100, 1) if _q_total else 0
        st.markdown(f"""
<div style='background:{_bg3};border:1px solid {_border_card};border-radius:12px;
            padding:12px 16px;margin-bottom:12px;'>
  <div style='display:flex;align-items:center;gap:0;flex-wrap:wrap;'>
    <div style='flex:1;min-width:90px;text-align:center;padding:4px 10px;'>
      <div style='font-size:0.55rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:2px;'>Total Pages</div>
      <div style='font-size:1.5rem;font-weight:900;color:{_text};line-height:1;'>{_q_total_pages:,}</div>
      <div style='font-size:0.55rem;color:{_text4};margin-top:2px;'>{_q_total:,} uploads</div>
    </div>
    <div style='width:1px;background:{_border_card};align-self:stretch;margin:4px 0;'></div>
    <div style='flex:1;min-width:90px;text-align:center;padding:4px 10px;'>
      <div style='font-size:0.55rem;font-weight:700;color:#d4500a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:2px;'>Completed</div>
      <div style='font-size:1.5rem;font-weight:900;color:#d4500a;line-height:1;'>{_q_reviewed_pages:,}</div>
      <div style='font-size:0.55rem;color:{_text4};margin-top:2px;'>{_q_reviewed:,} uploads</div>
    </div>
    <div style='width:1px;background:{_border_card};align-self:stretch;margin:4px 0;'></div>
    <div style='flex:1;min-width:90px;text-align:center;padding:4px 10px;'>
      <div style='font-size:0.55rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:2px;'>⏳ Pending</div>
      <div style='font-size:1.5rem;font-weight:900;color:#FBBF24;line-height:1;'>{_q_pending_pages:,}</div>
      <div style='font-size:0.55rem;color:{_text4};margin-top:2px;'>{_q_pending:,} uploads</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        # ── Single wide "Total Reviewed" bar  X = Y + Z + A ───────────────
        _clean_w   = round(_q_clean   / _q_reviewed * 100, 1) if _q_reviewed else 0
        _issues_w  = round(_q_issues  / _q_reviewed * 100, 1) if _q_reviewed else 0
        _reject_w  = round(_q_rejected/ _q_reviewed * 100, 1) if _q_reviewed else 0
        st.markdown(f"""
<div style='background:{_bg3};border:1px solid {_border_card};border-radius:16px;
            padding:28px 32px;margin-bottom:12px;'>
  <div style='font-size:0.65rem;font-weight:700;color:{_text2};text-transform:uppercase;
              letter-spacing:0.1em;margin-bottom:14px;'>Total Reviewed Pages</div>
  <div style='display:flex;align-items:center;gap:12px;flex-wrap:nowrap;'>
    <div style='text-align:center;flex-shrink:0;'>
      <div style='font-size:2.6rem;font-weight:900;color:{_text};line-height:1;'>{_q_reviewed_pages:,}</div>
      <div style='font-size:0.58rem;color:{_text4};margin-top:3px;'>{_q_reviewed:,} uploads</div>
    </div>
    <span style='font-size:1.6rem;color:{_text2};font-weight:300;flex-shrink:0;'>=</span>
    <div style='text-align:center;flex-shrink:0;'>
      <div style='font-size:0.82rem;font-weight:700;color:#34D399;margin-bottom:5px;letter-spacing:0.02em;'>Accepted w/o Issues</div>
      <div style='font-size:2.4rem;font-weight:900;color:#34D399;line-height:1;'>{_q_clean_pages:,}</div>
      <div style='font-size:0.72rem;color:{_text4};margin-top:4px;font-weight:500;'>{_q_clean:,} uploads</div>
    </div>
    <span style='font-size:1.6rem;color:{_text2};font-weight:300;flex-shrink:0;'>+</span>
    <div style='text-align:center;flex-shrink:0;'>
      <div style='font-size:0.82rem;font-weight:700;color:#FBBF24;margin-bottom:5px;letter-spacing:0.02em;'>Accepted w/ Issues</div>
      <div style='font-size:2.4rem;font-weight:900;color:#FBBF24;line-height:1;'>{_q_issues_pages:,}</div>
      <div style='font-size:0.72rem;color:{_text4};margin-top:4px;font-weight:500;'>{_q_issues:,} uploads</div>
    </div>
    <span style='font-size:1.6rem;color:{_text2};font-weight:300;flex-shrink:0;'>+</span>
    <div style='text-align:center;flex-shrink:0;'>
      <div style='font-size:0.82rem;font-weight:700;color:#F43F5E;margin-bottom:5px;letter-spacing:0.02em;'>Rejected</div>
      <div style='font-size:2.4rem;font-weight:900;color:#F43F5E;line-height:1;'>{_q_rejected_pages:,}</div>
      <div style='font-size:0.72rem;color:{_text4};margin-top:4px;font-weight:500;'>{_q_rejected:,} uploads</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

        # ── Row 3: Issue frequency bar ────────────────────────────────────
        from collections import Counter
        _all_issues: list[str] = []
        for _iv in filtered["issues_vs"].dropna():
            if isinstance(_iv, list):
                _all_issues.extend(_iv)
        for _ib in filtered["issues_bodhan"].dropna():
            if isinstance(_ib, list):
                _all_issues.extend(_ib)

        _DEMO_ISSUES = {
            "blur": 38, "lighting_condition": 27, "glare": 19,
            "partial_page": 14, "skew": 11, "low_contrast": 8,
            "ink_bleed": 5, "torn_page": 3,
        }
        _issue_source = Counter(_all_issues) if _all_issues else _DEMO_ISSUES
        _issue_df = (
            pd.DataFrame(_issue_source.items(), columns=["IssueKey", "Count"])
            .sort_values("Count", ascending=False)
        )
        _is_demo_issues = not bool(_all_issues)
        _issue_df["Issue"] = _issue_df["IssueKey"].str.replace("_", " ").str.title()
        _issue_bar_colors = (
            [_issue_color(k) for k in _issue_df["IssueKey"]]
            if not _is_demo_issues
            else ["rgba(251,191,36,0.3)"] * len(_issue_df)
        )
        _fig_issues = go.Figure(go.Bar(
            x=_issue_df["Issue"],
            y=_issue_df["Count"],
            marker_color=_issue_bar_colors,
            text=[str(v) for v in _issue_df["Count"]],
            textposition="outside",
            textfont=dict(size=10, color=_chart_text),
        ))
        _issues_layout = chart_layout(height=220)
        _issues_layout["margin"] = dict(l=4, r=4, t=20, b=4)
        _fig_issues.update_layout(**_issues_layout)
        _fig_issues.update_yaxes(visible=False)
        _fig_issues.update_xaxes(tickfont=dict(size=10))
        if _is_demo_issues:
            st.markdown(f"""
<div style='display:flex;align-items:center;gap:6px;margin-bottom:4px;'>
  <span style='font-size:0.65rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.08em;'>Top Issue Types</span>
  <span style='background:rgba(251,191,36,0.15);color:#FBBF24;font-size:0.6rem;font-weight:600;
               padding:1px 7px;border-radius:8px;border:1px solid rgba(251,191,36,0.3);'>placeholder — to be updated</span>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:0.65rem;font-weight:700;color:{_text2};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;'>Top Issue Types</div>", unsafe_allow_html=True)
        st.plotly_chart(_fig_issues, use_container_width=True, config={"displayModeBar": False})

        # ── Enhanced Sample Viewer Buttons with Visual Picker ─────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(f"""
<div style='font-size:0.65rem;font-weight:700;color:{_text2};text-transform:uppercase;
            letter-spacing:0.08em;margin-bottom:8px;'>📸 Sample Image Viewer</div>
""", unsafe_allow_html=True)

        _qc1, _qc2, _qc3 = st.columns(3)

        # Style for the viewer buttons
        st.markdown(f"""
<style>
div[data-testid="stButton"]:has(button[key="qa_view_accepted"]) button {{
    background: linear-gradient(135deg, rgba(52,211,153,0.15), rgba(52,211,153,0.05)) !important;
    border: 1px solid rgba(52,211,153,0.3) !important;
    color: #34D399 !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 8px 10px !important;
    height: auto !important;
    white-space: normal !important;
    transition: all 0.2s ease !important;
    font-size: 0.8rem !important;
    line-height: 1.3 !important;
}}
div[data-testid="stButton"]:has(button[key="qa_view_accepted"]) button:hover {{
    background: linear-gradient(135deg, rgba(52,211,153,0.25), rgba(52,211,153,0.15)) !important;
    border-color: rgba(52,211,153,0.5) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(52,211,153,0.3) !important;
}}
div[data-testid="stButton"]:has(button[key="qa_view_rejected"]) button {{
    background: linear-gradient(135deg, rgba(244,63,94,0.15), rgba(244,63,94,0.05)) !important;
    border: 1px solid rgba(244,63,94,0.3) !important;
    color: #F43F5E !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 8px 10px !important;
    height: auto !important;
    white-space: normal !important;
    transition: all 0.2s ease !important;
    font-size: 0.8rem !important;
    line-height: 1.3 !important;
}}
div[data-testid="stButton"]:has(button[key="qa_view_rejected"]) button:hover {{
    background: linear-gradient(135deg, rgba(244,63,94,0.25), rgba(244,63,94,0.15)) !important;
    border-color: rgba(244,63,94,0.5) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(244,63,94,0.3) !important;
}}
div[data-testid="stButton"]:has(button[key="qa_view_flagged"]) button {{
    background: linear-gradient(135deg, rgba(251,191,36,0.15), rgba(251,191,36,0.05)) !important;
    border: 1px solid rgba(251,191,36,0.3) !important;
    color: #FBBF24 !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 8px 10px !important;
    height: auto !important;
    white-space: normal !important;
    transition: all 0.2s ease !important;
    font-size: 0.8rem !important;
    line-height: 1.3 !important;
}}
div[data-testid="stButton"]:has(button[key="qa_view_flagged"]) button:hover {{
    background: linear-gradient(135deg, rgba(251,191,36,0.25), rgba(251,191,36,0.15)) !important;
    border-color: rgba(251,191,36,0.5) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(251,191,36,0.3) !important;
}}
</style>""", unsafe_allow_html=True)

        if _qc1.button(f"✓ Accepted ({_q_accepted:,})", key="qa_view_accepted", use_container_width=True, help="Browse accepted samples"):
            st.session_state["show_sample_checker"] = True
            st.session_state["sc_quality_preset"] = "clean"
            st.rerun()

        if _qc2.button(f"✗ Rejected ({_q_rejected:,})", key="qa_view_rejected", use_container_width=True, help="Browse rejected samples with issues"):
            st.session_state["show_sample_checker"] = True
            st.session_state["sc_quality_preset"] = "rejected"
            st.rerun()

        if _qc3.button(f"⚠ Flagged ({_q_issues:,})", key="qa_view_flagged", use_container_width=True, help="Browse samples with quality issues"):
            st.session_state["show_sample_checker"] = True
            st.session_state["sc_quality_preset"] = "flagged"
            st.rerun()

# ── State Detailed Stats Panel ────────────────────────────────────────────────
if not st.session_state.get("show_summary") and st.session_state.get("state_detail_open"):
    _sd_state = st.session_state["state_detail_open"]
    _sd_df = filtered[filtered["state"] == _sd_state].copy()

    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:24px 0 20px;'>", unsafe_allow_html=True)

    # Close button
    _sdcol, _ = st.columns([2, 6])
    with _sdcol:
        st.markdown(f"<div style='font-size:1.1rem;font-weight:800;color:#d4500a;margin-bottom:8px;'>📍 {_sd_state} — Detailed Stats</div>", unsafe_allow_html=True)
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
<div style='margin-bottom:24px;background:rgba(212,80,10,0.06);border:1px solid rgba(212,80,10,0.15);
            border-radius:14px;padding:18px 22px;'>
  <div style='font-size:0.72rem;font-weight:700;color:#d4500a;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;'>
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
            name="Other / Unknown", marker_color="#b45309",
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
        name="Avg pages/student", marker_color="#d4500a",
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
        .apply(lambda g: (g["students"] >= _MIN_STUDENTS).all(), include_groups=False)
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
            orientation="h", marker_color="#b45309",
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
                marker_color="#b45309",
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
      <div style='background:linear-gradient(135deg,rgba(212,80,10,0.12),rgba(212,80,10,0.06));
                  border:1px solid rgba(212,80,10,0.3);border-radius:14px;padding:18px 22px;
                  display:flex;flex-direction:column;justify-content:space-between;'>
        <div style='font-size:0.7rem;font-weight:700;color:#d4500a;text-transform:uppercase;letter-spacing:0.1em;'>
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
        <div style='font-size:0.72rem;color:{_text2};margin-top:6px;'>days · 5 Jul 2026</div>
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
    PHASE1_DEADLINE = pd.Timestamp("2026-07-05", tz="Asia/Kolkata")

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
            _lvl_colors = {"Primary (1-5)": "#2563eb", "High School (6-8)": "#34D399", "Secondary (9-10)": "#F472B6", "Higher Secondary (11-12)": "#FBBF24"}
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
                    f"<span style='background:rgba(212,80,10,0.12);color:#d4500a;border-radius:4px;padding:1px 6px;font-weight:600;'>English</span>&nbsp;"
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

    # ── State-wise Target Progress (Phase 1) ─────────────────────────────────
    st.markdown(f"""
<div style='background:{_bg2};border:1px solid {_border_card};border-radius:16px;
            padding:20px 24px 16px;margin-bottom:24px;'>
  <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;'>
    <div style='font-size:0.9rem;font-weight:700;color:{_text};'>Phase 1 State Targets
      <span style='font-size:0.72rem;font-weight:500;color:{_text4};margin-left:8px;'>
        2,00,000 pages each · Deadline: 5 Jul 2026</span></div>
    <div style='font-size:0.7rem;font-weight:600;color:{_dl_clr};'>{_days_left}d remaining</div>
  </div>
  <div style='display:grid;grid-template-columns:repeat(2,1fr);gap:14px 28px;'>""", unsafe_allow_html=True)
    for _slabel, _snames, _starget in _STATE_TARGET_ROWS:
        _spages = int(df[df["state"].isin(_snames)]["num_pages"].sum())
        _spct   = min(_spages / _starget * 100, 100) if _starget else 0
        _sclr   = "#10B981" if _spct >= 100 else "#F59E0B" if _spct >= 60 else "#F43F5E"
        _sremain = max(_starget - _spages, 0)
        st.markdown(f"""
    <div>
      <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;'>
        <span style='font-size:0.8rem;font-weight:600;color:{_text3};'>{_slabel}</span>
        <span style='font-size:0.75rem;font-weight:800;color:{_sclr};'>{_spct:.1f}%</span>
      </div>
      <div style='background:{_progress_track};border-radius:6px;height:10px;overflow:hidden;'>
        <div style='width:{_spct:.1f}%;background:linear-gradient(90deg,{_sclr}cc,{_sclr});
                    height:100%;border-radius:6px;box-shadow:0 0 8px {_sclr}44;'></div>
      </div>
      <div style='display:flex;justify-content:space-between;margin-top:3px;'>
        <span style='font-size:0.65rem;color:{_text2};'>{_spages:,} pages collected</span>
        <span style='font-size:0.65rem;color:{_text4};'>{_sremain:,} remaining</span>
      </div>
    </div>""", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    # ── Pages by State chart with target annotation ─────────────────────────
    sl1, sl2 = st.columns(2)
    with sl1:
        _target_states_set = {s for _, names, _ in _STATE_TARGET_ROWS for s in names}
        _fig = go.Figure()
        _fig.add_trace(go.Bar(
            x=state_stats["state"], y=state_stats["pages"],
            marker_color=C_INDIGO,
            text=[f"{p:,}" for p in state_stats["pages"]], textposition="outside", textfont=_bar_textfont,
        ))
        _has_target_states = any(s in _target_states_set for s in state_stats["state"])
        if _has_target_states:
            _fig.add_hline(
                y=200_000, line_dash="dash", line_color="#F59E0B", line_width=1.5,
                annotation_text="2L target", annotation_position="top right",
                annotation_font=dict(size=10, color="#F59E0B"),
            )
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
      <div style='background:rgba(212,80,10,0.08);border:1px solid rgba(212,80,10,0.25);border-radius:10px;padding:12px 16px;'>
        <div style='font-size:0.65rem;font-weight:700;color:#d4500a;text-transform:uppercase;letter-spacing:.08em;'>Districts</div>
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
            colorscale=[[0, "#fef3c7"], [0.3, "#f97316"], [0.6, "#d4500a"], [1.0, "#7c2d12"]],
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
                "Printed Content", "#d4500a", "#94A3B8", "cq_pr")

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
    # UPLOAD TIMELINE & REVIEW TURNAROUND
    # ══════════════════════════════════════════════════════════════════════════════

    section("Upload Timeline & Review Turnaround")

    _tl_c1, _tl_c2 = st.columns(2)

    with _tl_c1:
        # Daily upload pace by file_number sequence
        _tl_df = filtered[filtered["date"].notna()].copy()
        _tl_df["upload_date"] = _tl_df["date"].dt.tz_convert("Asia/Kolkata").dt.date
        _daily = (
            _tl_df.groupby("upload_date")
            .agg(uploads=("file_number", "count"), pages=("num_pages", "sum"))
            .reset_index()
        )
        _daily["upload_date"] = pd.to_datetime(_daily["upload_date"])
        _fig_tl = go.Figure()
        _fig_tl.add_trace(go.Bar(
            x=_daily["upload_date"], y=_daily["uploads"],
            name="Uploads", marker_color=C_INDIGO, opacity=0.85,
            hovertemplate="%{x|%d %b}: %{y} uploads<extra></extra>",
        ))
        _fig_tl.add_trace(go.Scatter(
            x=_daily["upload_date"], y=_daily["pages"],
            name="Pages", yaxis="y2", line=dict(color="#F9A8D4", width=2),
            hovertemplate="%{x|%d %b}: %{y:,} pages<extra></extra>",
        ))
        _tl_layout = chart_layout(title="Daily Uploads & Pages", height=280)
        for _k in ("yaxis", "legend"):
            _tl_layout.pop(_k, None)
        _fig_tl.update_layout(
            **_tl_layout,
            yaxis=dict(title="Uploads", color=_chart_text),
            yaxis2=dict(title="Pages", overlaying="y", side="right", color="#F9A8D4", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            barmode="overlay",
        )
        st.plotly_chart(_fig_tl, use_container_width=True, config={"displayModeBar": False})

    with _tl_c2:
        # Review turnaround: hours between createdAt and reviewedAt
        _rt_df = filtered[filtered["reviewed_at"].notna() & filtered["date"].notna()].copy()
        if len(_rt_df):
            _rt_df["turnaround_hrs"] = (_rt_df["reviewed_at"] - _rt_df["date"]).dt.total_seconds() / 3600
            _rt_df = _rt_df[_rt_df["turnaround_hrs"] >= 0]
            _rt_mean = round(_rt_df["turnaround_hrs"].mean(), 1)
            _rt_med  = round(_rt_df["turnaround_hrs"].median(), 1)
            _rt_min  = round(_rt_df["turnaround_hrs"].min(), 1)
            _rt_max  = round(_rt_df["turnaround_hrs"].max(), 1)

            st.markdown(f"""
<div style='display:flex;gap:8px;margin-bottom:8px;'>
  <div style='flex:1;background:{_bg3};border:1px solid {_border_card};border-radius:10px;padding:10px;text-align:center;'>
    <div style='font-size:0.58rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Median</div>
    <div style='font-size:1.3rem;font-weight:800;color:#d4500a;'>{_rt_med}h</div>
  </div>
  <div style='flex:1;background:{_bg3};border:1px solid {_border_card};border-radius:10px;padding:10px;text-align:center;'>
    <div style='font-size:0.58rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Mean</div>
    <div style='font-size:1.3rem;font-weight:800;color:#34D399;'>{_rt_mean}h</div>
  </div>
  <div style='flex:1;background:{_bg3};border:1px solid {_border_card};border-radius:10px;padding:10px;text-align:center;'>
    <div style='font-size:0.58rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Fastest</div>
    <div style='font-size:1.3rem;font-weight:800;color:#FBBF24;'>{_rt_min}h</div>
  </div>
  <div style='flex:1;background:{_bg3};border:1px solid {_border_card};border-radius:10px;padding:10px;text-align:center;'>
    <div style='font-size:0.58rem;color:{_text2};text-transform:uppercase;letter-spacing:.07em;'>Slowest</div>
    <div style='font-size:1.3rem;font-weight:800;color:#F43F5E;'>{_rt_max}h</div>
  </div>
</div>""", unsafe_allow_html=True)

            # Histogram of turnaround hours (capped at 500h for readability)
            _rt_cap = _rt_df[_rt_df["turnaround_hrs"] <= 500]["turnaround_hrs"]
            _fig_rt = go.Figure(go.Histogram(
                x=_rt_cap, nbinsx=30,
                marker_color=C_INDIGO, opacity=0.8,
                hovertemplate="~%{x:.0f}h: %{y} files<extra></extra>",
            ))
            _fig_rt.add_vline(x=_rt_med, line_dash="dash", line_color="#34D399",
                annotation_text=f"median {_rt_med}h", annotation_position="top right",
                annotation_font_color="#34D399")
            _fig_rt.update_layout(**chart_layout(title="Review Turnaround Distribution", height=220),
                xaxis_title="Hours to Approve", yaxis_title="Files")
            st.plotly_chart(_fig_rt, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No review turnaround data available.")

    # ── Place (city/town/village) breakdown ───────────────────────────────────
    _pl_df = filtered[filtered["place"].notna() & (filtered["place"] != "")].copy()
    if len(_pl_df):
        _place_stats = (
            _pl_df.groupby(["state", "place"])
            .agg(uploads=("file_number", "count"), pages=("num_pages", "sum"), students=("student_id", "nunique"))
            .reset_index()
            .sort_values("uploads", ascending=False)
            .head(20)
        )
        _place_stats["label"] = _place_stats["place"] + " (" + _place_stats["state"] + ")"
        _fig_pl = go.Figure(go.Bar(
            x=_place_stats["uploads"],
            y=_place_stats["label"],
            orientation="h",
            marker_color=C_VIOLET,
            text=_place_stats["uploads"], textposition="outside", textfont=_bar_textfont,
            customdata=_place_stats[["pages", "students"]],
            hovertemplate="%{y}<br>Uploads: %{x}<br>Pages: %{customdata[0]:,}<br>Students: %{customdata[1]}<extra></extra>",
        ))
        _fig_pl.update_layout(**chart_layout(
            title="Top 20 Places (City / Town / Village)",
            height=120 + len(_place_stats) * 26,
            margin=dict(l=0, r=50, t=32, b=4),
        ))
        _fig_pl.update_xaxes(visible=False)
        _fig_pl.update_yaxes(tickfont=dict(size=11))
        st.plotly_chart(_fig_pl, use_container_width=True, config={"displayModeBar": False})

    # ── Metadata flags ─────────────────────────────────────────────────────────
    _mf_c1, _mf_c2 = st.columns(2)
    with _mf_c1:
        _gm_counts = filtered["generate_metadata"].value_counts()
        _fig_gm = go.Figure(go.Pie(
            labels=[("Auto-generated" if l else "Manual") for l in _gm_counts.index],
            values=_gm_counts.values,
            hole=0.55,
            marker=dict(colors=["#34D399", "#6B7280"]),
            textinfo="percent+label",
            hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
        ))
        _fig_gm.update_layout(**chart_layout(title="Metadata Generation", height=240, showlegend=False))
        st.plotly_chart(_fig_gm, use_container_width=True, config={"displayModeBar": False})
    with _mf_c2:
        _db_counts = filtered["data_bucket"].value_counts()
        _fig_db = go.Figure(go.Pie(
            labels=[("In Data Bucket" if l else "Not in Bucket") for l in _db_counts.index],
            values=_db_counts.values,
            hole=0.55,
            marker=dict(colors=["#d4500a", "#6B7280"]),
            textinfo="percent+label",
            hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
        ))
        _fig_db.update_layout(**chart_layout(title="Data Bucket Flag", height=240, showlegend=False))
        st.plotly_chart(_fig_db, use_container_width=True, config={"displayModeBar": False})

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
