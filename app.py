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
import os
from dotenv import load_dotenv

load_dotenv()  # Load from .env file if exists



urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OCR-VS Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling (dark-theme safe, all headings white) ────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* Global App Background & Font */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp > header { background-color: transparent !important; }
    .stApp {
        background-color: #09090B !important;
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(129, 140, 248, 0.05), transparent 40%),
            radial-gradient(circle at 85% 30%, rgba(16, 185, 129, 0.03), transparent 40%);
    }
    .main .block-container { padding-top: 1.2rem; max-width: 1400px; }

    /* Title */
    .dashboard-title {
        font-size: 4rem; font-weight: 900; 
        background: linear-gradient(90deg, #FFFFFF 0%, #A1A1AA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0; letter-spacing: -2px; line-height: 1.1;
    }
    .dashboard-subtitle {
        font-size: 1.05rem; color: #A1A1AA; margin-top: 4px; margin-bottom: 10px;
        font-weight: 500; letter-spacing: -0.2px;
    }

    /* Section headers */
    .section-header {
        font-size: 1.4rem; font-weight: 700; color: #FFFFFF !important;
        display: flex; align-items: center; gap: 12px;
        margin: 20px 0 16px 0; letter-spacing: -0.3px;
    }
    .section-header::before {
        content: ''; display: block; width: 6px; height: 24px;
        background: linear-gradient(180deg, #818CF8, #A78BFA);
        border-radius: 4px;
    }

    /* KPI cards */
    div[data-testid="metric-container"] {
        background: #121217;
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-top: 1px solid rgba(255, 255, 255, 0.08); /* slight inner reflection */
        border-radius: 16px; padding: 20px 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px);
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 12px 30px rgba(129, 140, 248, 0.1);
    }
    div[data-testid="metric-container"] label {
        color: #A1A1AA !important; 
        font-size: 0.75rem !important; font-weight: 600 !important;
        text-transform: uppercase; letter-spacing: 1px;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #FFFFFF !important; 
        font-size: 2.2rem !important; font-weight: 800 !important; 
        letter-spacing: -0.5px;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricDelta"] {
        font-size: 0.8rem !important; font-weight: 600 !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #09090B !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #FFFFFF !important; font-weight: 800 !important; letter-spacing: -0.5px;
    }
    section[data-testid="stSidebar"] * { color: #A1A1AA !important; }
    section[data-testid="stSidebar"] .stSelectbox label {
        color: #FFFFFF !important; font-weight: 600 !important;
        font-size: 0.8rem !important; text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.05) !important;
    }

    /* Default Markdown */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 { color: #ffffff !important; }
    .stMarkdown strong { color: #E2E8F0 !important; }

    /* Expander */
    .streamlit-expanderHeader { color: #FFFFFF !important; font-weight: 600 !important; }

    /* Progress bar labels */
    .progress-label {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 6px;
    }
    .progress-label span { color: #A1A1AA; font-size: 0.85rem; font-weight: 500; }
    .progress-label .pct { font-weight: 700; color: #FFFFFF; }

    /* Compliance badge */
    .badge-pass {
        background: rgba(16, 185, 129, 0.15); color: #10B981;
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    }
    .badge-fail {
        background: rgba(244, 63, 94, 0.15); color: #F43F5E;
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    }
    .badge-warn {
        background: rgba(245, 158, 11, 0.15); color: #F59E0B;
        padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
    .stTabs [data-baseweb="tab"] {
        color: #A1A1AA !important; font-weight: 500;
        padding: 8px 16px; border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #FFFFFF !important;
        border-bottom: 2px solid #818CF8 !important;
        background: linear-gradient(180deg, rgba(129,140,248,0) 0%, rgba(129,140,248,0.08) 100%);
    }

    /* Divider helper */
    .spacer { margin-top: 24px; }
    .stAlert { border-radius: 12px !important; border: 1px solid rgba(255,255,255,0.05); }


    /* Sidebar Dropdown Menu */
    .st-jump-menu {
        position: relative; display: inline-block; width: 100%; margin-bottom: 24px;
    }
    .st-jump-btn {
        background-color: #121217; color: #FFFFFF;
        padding: 12px 16px; font-size: 0.9rem; font-weight: 600;
        border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px;
        cursor: pointer; width: 100%; text-align: left;
        display: flex; justify-content: space-between; align-items: center;
        transition: border-color 0.2s;
    }
    .st-jump-btn::after { content: "▼"; font-size: 0.7rem; color: #A1A1AA; }
    .st-jump-content {
        display: none; position: absolute; background-color: #18181F;
        min-width: 100%; box-shadow: 0px 8px 24px 0px rgba(0,0,0,0.6);
        z-index: 10000; border: 1px solid #818CF8; border-radius: 8px;
        margin-top: 4px; max-height: 400px; overflow-y: auto;
    }
    .st-jump-content a {
        color: #A1A1AA; padding: 12px 16px; text-decoration: none;
        display: block; font-size: 0.85rem; font-weight: 500;
        border-bottom: 1px solid rgba(255,255,255,0.03);
    }
    .st-jump-content a:last-child { border-bottom: none; }
    .st-jump-content a:hover {
        background-color: rgba(129, 140, 248, 0.15); color: #FFFFFF;
    }
    .st-jump-menu:hover .st-jump-content { display: block; }
    .st-jump-menu:hover .st-jump-btn { border-color: #818CF8; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# BUCKET CONFIG & HELPERS
# ══════════════════════════════════════════════════════════════════════════════

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET")
MINIO_PREFIX     = os.getenv("MINIO_PREFIX")


PAGE_CACHE_FILE  = Path(__file__).parent / ".page_count_cache.json"

def _s3():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        verify=False,
    )


def _presigned_url(key: str, expires: int = 3600) -> tuple[str, str, str]:
    """Return (url, error, found_ext). url is empty string on failure. found_ext is the extension that exists (e.g. 'png') when PDF is missing but an image was found."""
    try:
        s3 = _s3()
        try:
            s3.head_object(Bucket=MINIO_BUCKET, Key=key)
        except Exception:
            # PDF missing — check for image alternatives
            base = key[:-4] if key.endswith(".pdf") else key
            for ext in ("png", "jpg", "jpeg", "tiff", "tif"):
                alt_key = f"{base}.{ext}"
                try:
                    s3.head_object(Bucket=MINIO_BUCKET, Key=alt_key)
                    alt_url = s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": MINIO_BUCKET, "Key": alt_key},
                        ExpiresIn=expires,
                    )
                    return alt_url, "", ext
                except Exception:
                    continue
            return "", "File does not exist in storage (404)", ""
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": MINIO_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
        return url, "", "pdf"
    except Exception as e:
        return "", str(e), ""


def _load_page_cache() -> dict:
    try:
        if PAGE_CACHE_FILE.exists():
            return _json.loads(PAGE_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_page_cache(cache: dict):
    try:
        PAGE_CACHE_FILE.write_text(_json.dumps(cache))
    except Exception:
        pass


def _count_pdf_pages(s3_client, key: str, size_bytes: int, cache: dict, exact: bool = False) -> int:
    """Return page count.  If exact=False and key not cached, estimate from file size."""
    if key in cache:
        return cache[key]
    if not exact:
        # ~600 KB per scanned page (calibrated from sample data)
        return max(1, round(size_bytes / 600_000))
    try:
        body = s3_client.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()
        n = len(pypdf.PdfReader(io.BytesIO(body)).pages)
    except Exception:
        n = max(1, round(size_bytes / 600_000))
    cache[key] = n
    return n


STATE_TO_LANGUAGE = {
    "uttar_pradesh": "Hindi", "bihar": "Hindi", "rajasthan": "Hindi",
    "madhya_pradesh": "Hindi", "haryana": "Hindi", "himachal_pradesh": "Hindi",
    "delhi": "Hindi", "uttarakhand": "Hindi", "chhattisgarh": "Hindi", "jharkhand": "Hindi",
    "west_bengal": "Bengali",
    "karnataka": "Kannada",
    "kerala": "Malayalam",
    "maharashtra": "Marathi",
    "odisha": "Odia",
    "punjab": "Punjabi",
    "tamil_nadu": "Tamil",
    "andhra_pradesh": "Telugu",
    "telangana": "Telugu",
}

CLASS_LEVEL_FROM_GRADE = {
    1: "Primary (1-5)", 2: "Primary (1-5)", 3: "Primary (1-5)",
    4: "Primary (1-5)", 5: "Primary (1-5)",
    6: "High School (6-8)", 7: "High School (6-8)", 8: "High School (6-8)",
    9: "Secondary (9-10)", 10: "Secondary (9-10)",
    11: "Higher Secondary (11-12)", 12: "Higher Secondary (11-12)",
}


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING & CLEANING
# ══════════════════════════════════════════════════════════════════════════════

SUBJECT_MAP = {
    "english": "English", "eanglish": "English", "engl;ish": "English",
    "english grammer": "English Grammar", "english grammar": "English Grammar",
    "grammer english": "English Grammar", "grammar": "English Grammar",
    "hindi": "Hindi", "hindi grammar": "Hindi Grammar",
    "hindi vyakaran": "Hindi Grammar", "hindi kawy": "Hindi Literature",
    "vavyakaran": "Hindi Grammar",
    "math": "Mathematics", "maths": "Mathematics", "mahth": "Mathematics",
    "rekha garhi": "Mathematics",
    "science": "Science", "science project": "Science", "science_project": "Science",
    "biology": "Biology", "biology ": "Biology",
    "chemistry": "Chemistry", "chemistry ": "Chemistry",
    "physics": "Physics", "phisics": "Physics",
    "social science": "Social Science", "social science ": "Social Science",
    " social science ": "Social Science", "scocial science": "Social Science",
    "history": "History", "history ": "History", "hiistory": "History",
    "geography": "Geography", "geography ": "Geography", "geogrphy": "Geography",
    "civics": "Civics", "civics ": "Civics",
    "economics": "Economics", "political science": "Political Science",
    "e.v.s": "EVS", "evs": "EVS", "environment": "EVS",
    "environmental": "EVS", "environmantal": "EVS",
    "paryavaran": "EVS", "paryawaran": "EVS", "hamara parivesh": "EVS",
    "sanskrit": "Sanskrit", "sanskrit ": "Sanskrit",
    "sanskrit grammar": "Sanskrit Grammar",
    "computer": "Computer Science", "it": "Computer Science",
    "general knowledge": "General Knowledge", "genral knowedge": "General Knowledge",
    "physical education": "Physical Education",
    "business studies": "Business Studies",
    "moral education": "Moral Education",
    "agriculture": "Agriculture", "agricultur": "Agriculture",
    "agriculture ": "Agriculture", "krishi vigyan": "Agriculture",
    "home science": "Home Science", "grihkaushal": "Home Science",
    "grikaushal": "Home Science", "gruh darshika": "Home Science",
    "mahan vyaktiva": "Moral Education",
    "grade shelf": "Other", "not mentioned": "Not Mentioned",
}

SAMPLE_TYPE_MAP = {
    "notebook c.w": "Notebook (Classwork)",
    "notebook c.w & h.w": "Notebook (CW & HW)",
    "notebook h.w": "Notebook (Homework)",
    "notebook": "Notebook", "notebook ": "Notebook",
    "worksheet": "Worksheet",
    "objective_assessment": "Objective Assessment",
    "subjective_assessment": "Subjective Assessment",
    "hybrid_obj_subj_assessment": "Hybrid Assessment",
    "cursive_writing_notebook": "Cursive Writing",
    "textbook": "Textbook",
    "graphbook": "Graphbook",
    "board_image": "Board Image",
    "map_labelling": "Map Labelling",
    "record_notebook": "Record Notebook",
    "form": "Form",
}

GENDER_MAP = {"male": "Male", "female": "Female", "other": "Other", "not mentioned": "Not Mentioned"}
BOARD_MAP = {
    "up_board_of_high_school_and_intermediate_education": "UP Board",
    "up board of high school and intermediate education": "UP Board",
    "cbse": "CBSE", "c b s e": "CBSE",
    "u p": "UP Board", "u.p": "UP Board",
    "icse": "ICSE",
    "state_board": "State Board", "state board": "State Board",
    "not mentioned": "Not Mentioned",
}
BLOCK_MAP = {
    "arajilines": "Arajilines", "baragaon": "Baragaon", "chiraigaon": "Chiraigaon",
    "k.v.p": "KVP", "kvp": "KVP",
    "nagar nigam": "Nagar Nigam", "nagar_nigam": "Nagar Nigam",
    "sewapuri": "Sewapuri", "sewapuri ": "Sewapuri", "sewpuri": "Sewapuri",
    "not mentioned": "Not Mentioned",
}

SCHOOL_NORMALIZATIONS = {
    "u ps bohar": "UPS Bohar", "ups bohar": "UPS Bohar",
    "u ps ramana": "UPS Ramana", "ups ramana": "UPS Ramana",
    "u ps anei": "UPS Anei", "ups anei": "UPS Anei",
    "u ps lachhapur": "UPS Lachhapur",
    "cs rustampur": "CS Rustampur", "cs dholapur": "CS Dholapur",
    "ku ps kamauli": "KUPS Kamauli", "kups kamauli": "KUPS Kamauli",
    "cs pracheen": "CS Pracheen",
    "cs dehalivinayak": "CS Dehlivinayak", "cs dehalivinayak ": "CS Dehlivinayak",
    "cs dehlivinayak": "CS Dehlivinayak", "cs delhivinayak": "CS Dehlivinayak",
    "cs deyeepur ": "CS Deyeepur", "cs gairaha": "CS Gairaha",
    "cs kardhana": "CS Kardhana",
    "ku ps amani": "KUPS Amini", "ku ps amini": "KUPS Amini",
    "ku ps amini ": "KUPS Amini", "k u ps amani": "KUPS Amini",
    "u ps tikari": "UPS Tikari",
    "u ps vihara": "UPS Vihara", "u ps vihara ": "UPS Vihara", "u ps vihra": "UPS Vihara",
}


SUBJ_CAT_MAP = {
    "English": "English", "English Grammar": "English",
    "Hindi": "Hindi / Regional", "Hindi Grammar": "Hindi / Regional",
    "Hindi Literature": "Hindi / Regional",
    "Sanskrit": "Sanskrit", "Sanskrit Grammar": "Sanskrit",
    "Mathematics": "Mathematics",
    "Science": "Science", "Biology": "Science", "Chemistry": "Science", "Physics": "Science",
    "Social Science": "Social Science", "History": "Social Science",
    "Geography": "Social Science", "Civics": "Social Science",
    "Economics": "Social Science", "Political Science": "Social Science",
    "EVS": "EVS",
    "Computer Science": "Other", "General Knowledge": "Other",
    "Physical Education": "Other", "Business Studies": "Other",
    "Moral Education": "Other", "Agriculture": "Other",
    "Home Science": "Other", "Other": "Other", "Not Mentioned": "Other",
}


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
            "distributor":           str(meta.get("distributor") or meta.get("collector_name") or meta.get("data_collector") or "Not Mentioned").strip(),
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
    data["subject"] = (
        data["subject"].map(SUBJECT_MAP)
        .fillna(data["subject"].str.replace("_", " ").str.title())
    )
    data["gender"]      = data["gender"].map(GENDER_MAP).fillna("Not Mentioned")
    data["board"]       = (
        data["board"].map(BOARD_MAP)
        .fillna(data["board"].str.replace("_", " ").str.title())
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

_LEVELS = ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)")
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


@st.cache_data(ttl=300)
def load_from_cache() -> pd.DataFrame:
    """Read the parquet file written by fetch_data.py (fast, no network calls)."""
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
        df = load_from_cache()
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

# LANGUAGE_SPECIFIC_TARGETS is defined as a constant above (no external file needed)

# ══════════════════════════════════════════════════════════════════════════════
# CHART THEME
# ══════════════════════════════════════════════════════════════════════════════

# ── Color palette ─────────────────────────────────────────────────────────────
# Muted, perceptually balanced — readable on dark bg without visual noise.
# Saturation kept ~60-70% so no single color dominates.

# Status — clear but not garish
C_GREEN   = "#34D399"   # pass / on target  (soft emerald)
C_RED     = "#F87171"   # fail / below      (soft rose)
C_AMBER   = "#FBBF24"   # warning / target  (warm gold)
C_GREY    = "#6B7280"   # neutral / other   (cool grey)

# Semantic — each concept owns one color, used everywhere
C_FEMALE  = "#C084FC"   # female            (soft lavender-pink)
C_MALE    = "#60A5FA"   # male              (soft cornflower blue)
C_GOVT    = "#34D399"   # government school (emerald)
C_AIDED   = "#6EE7B7"   # govt-aided        (lighter emerald)
C_PRIVATE = "#F43F5E"   # private           (red)
C_RURAL   = "#34D399"   # rural             (emerald, matches govt — both "public")
C_URBAN   = "#818CF8"   # urban             (soft indigo)
C_LEFT    = "#C084FC"   # left-handed       (lavender)
C_RIGHT   = "#60A5FA"   # right-handed      (blue)

# App accent (used for section bar, tabs, etc.)
C_INDIGO  = "#818CF8"   # softer indigo
C_VIOLET  = "#A78BFA"   # soft violet

# General-purpose palette for multi-series charts
# Ordered so adjacent colors are maximally distinct
COLORS = [
    "#818CF8",  # soft indigo
    "#34D399",  # emerald
    "#FBBF24",  # gold
    "#C084FC",  # lavender
    "#60A5FA",  # cornflower
    "#A78BFA",  # violet
    "#6EE7B7",  # light emerald
    "#F9A8D4",  # soft pink
    "#FCD34D",  # light gold
    "#7DD3FC",  # sky blue
]

CHART_HEIGHT = 370
CHART_TEMPLATE = "plotly_dark"

def chart_layout(**kwargs):
    base = dict(
        template=CHART_TEMPLATE,
        height=kwargs.pop("height", CHART_HEIGHT),
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", size=12, color="#A1A1AA"),
        title_font=dict(size=15, color="#FFFFFF", family="Inter"),
        xaxis=dict(showgrid=False, zeroline=False, showline=False, color="#A1A1AA"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.03)", zeroline=False, showline=False, color="#A1A1AA"),
        legend=dict(font=dict(color="#A1A1AA")),
        hoverlabel=dict(bgcolor="#121217", font_size=13, font_family="Inter", bordercolor="rgba(255,255,255,0.1)")
    )
    base.update(kwargs)
    return base


def section(title):
    anchor = title.lower().replace(" ", "-").replace("&", "and")
    st.markdown(f'<div id="{anchor}" class="section-header">{title}</div>', unsafe_allow_html=True)


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
    "Subject Coverage by Class Level",
    "Student Multi-Subject Coverage",
    "Pages per Record Distribution",
    "Raw Data Explorer",
]

_days_left = (pd.Timestamp("2026-05-31", tz="Asia/Kolkata") - pd.Timestamp.now(tz="Asia/Kolkata")).days

with st.sidebar:
    st.markdown("## OCR-VS")
    st.markdown("Data Collection Monitor")
    st.caption(f"Data: {_data_source}")
    _deadline_color = "#F43F5E" if _days_left <= 14 else "#F59E0B" if _days_left <= 30 else "#10B981"
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px 14px; margin-bottom:8px;">'
        f'<div style="font-size:0.7rem; text-transform:uppercase; letter-spacing:1px; color:#A1A1AA; font-weight:600;">Phase 1 Deadline</div>'
        f'<div style="font-size:1.05rem; font-weight:700; color:#FFFFFF; margin-top:2px;">31 May 2026</div>'
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

# ── Top-right Sample Checker toggle ──────────────────────────────────────────
if "show_sample_checker" not in st.session_state:
    st.session_state["show_sample_checker"] = False

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
    _is_open = st.session_state["show_sample_checker"]
    if _is_open:
        _sc_bg     = "linear-gradient(135deg, #F43F5E 0%, #E11D48 100%)"
        _sc_shadow = "0 4px 20px rgba(244,63,94,0.5)"
        _sc_border = "1px solid rgba(244,63,94,0.6)"
        _sc_label  = "✕  Close Checker"
    else:
        _sc_bg     = "linear-gradient(135deg, #818CF8 0%, #A78BFA 100%)"
        _sc_shadow = "0 4px 20px rgba(129,140,248,0.5)"
        _sc_border = "1px solid rgba(129,140,248,0.6)"
        _sc_label  = "🔍  Sample Checker"
    st.markdown(f"""
<style>
div[data-testid="stButton"]:has(button[data-testid="baseButton-secondary"][key="toggle_sample_checker"]) button,
div[data-testid="stButton"] > button[kind="secondary"] {{
    background: {_sc_bg} !important;
    border: {_sc_border} !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.03em !important;
    border-radius: 12px !important;
    padding: 12px 20px !important;
    box-shadow: {_sc_shadow} !important;
    transition: all 0.2s ease !important;
    text-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;
}}
div[data-testid="stButton"] > button[kind="secondary"]:hover {{
    filter: brightness(1.12) !important;
    transform: translateY(-2px) !important;
    box-shadow: {_sc_shadow.replace("0.5", "0.7")} !important;
}}
div[data-testid="stButton"] > button[kind="secondary"]:active {{
    transform: translateY(0px) !important;
    filter: brightness(0.95) !important;
}}
</style>
""", unsafe_allow_html=True)
    if st.button(_sc_label, key="toggle_sample_checker", use_container_width=True):
        st.session_state["show_sample_checker"] = not st.session_state["show_sample_checker"]
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

    _dist_opts = ["All"] + sorted([d for d in _sc_df["distributor"].unique() if d and d != "Not Mentioned"])
    _sel_dist = _sc_f1.selectbox("Distributor", _dist_opts, key="sc_dist")
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

    _sc_fa, _sc_fb, _ = st.columns([1, 1, 2])
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

    _sc_show = _sc_df.head(100).reset_index(drop=True)
    n_total  = len(_sc_df)

    st.markdown(
        f"<div style='color:#A1A1AA;font-size:0.8rem;margin:8px 0 12px;'>"
        f"<b style='color:#F1F5F9;'>{n_total:,}</b> records match"
        f"{' · showing first 100' if n_total > 100 else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )

    if n_total == 0:
        st.info("No records match the selected filters.")
    else:
        # ── Select a record to view PDF ────────────────────────────────────
        st.markdown("<div style='font-size:0.72rem;font-weight:600;color:#64748B;text-transform:uppercase;"
                    "letter-spacing:0.07em;margin-bottom:6px;'>Select a record to view PDF</div>",
                    unsafe_allow_html=True)

        _dropdown_labels = ["— select a sample to open PDF —"]
        for _i, _r in _sc_show.iterrows():
            _n   = str(_r["student_name"]).title() or "Unknown"
            _cl  = int(_r["class"]) if _r["class"] and not pd.isna(_r["class"]) else "?"
            _sb  = str(_r["subject"]).title()
            _pg  = int(_r["num_pages"])
            _sch = str(_r["school_name"]).title()
            _dt  = str(_r["date"])[:10] if pd.notna(_r["date"]) else "—"
            _dropdown_labels.append(f"{_i+1}. {_n}  ·  Class {_cl}  ·  {_sb}  ·  {_pg} pg  |  {_sch}  ·  {_dt}")

        _sel_label = st.selectbox(
            "Select sample",
            options=_dropdown_labels,
            index=0,
            key="sc_student_select",
            label_visibility="collapsed",
        )

        if _sel_label != "— select a sample to open PDF —":
            _sel_pos     = _dropdown_labels.index(_sel_label) - 1  # offset for placeholder
            _sc_row      = _sc_show.iloc[_sel_pos]
            _pdf_key_val = _sc_row["pdf_key"]
            _cls_v = int(_sc_row["class"]) if _sc_row["class"] and not pd.isna(_sc_row["class"]) else "?"

            # Metadata strip
            st.markdown(f"""
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
     border-radius:10px;padding:10px 16px;margin:10px 0;
     display:grid;grid-template-columns:repeat(4,1fr);gap:8px;'>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>Student</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{str(_sc_row["student_name"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>Class · Subject</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>Class {_cls_v} · {str(_sc_row["subject"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>School</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{str(_sc_row["school_name"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>District · Block</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{_sc_row["district"]} · {str(_sc_row["block"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>Gender</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{str(_sc_row["gender"]).title()}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>Pages</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{int(_sc_row["num_pages"])}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>Date</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{str(_sc_row["date"])[:10] if pd.notna(_sc_row["date"]) else "—"}</div></div>
  <div><div style='font-size:0.6rem;color:#64748B;text-transform:uppercase;letter-spacing:.07em;'>Sample Type</div>
       <div style='font-size:0.82rem;font-weight:600;color:#F1F5F9;'>{str(_sc_row["sample_type"]).title()}</div></div>
</div>
""", unsafe_allow_html=True)

            with st.spinner("Fetching file…"):
                _pdf_url, _pdf_err, _found_ext = _presigned_url(_pdf_key_val, expires=1800)

            if _pdf_url and _found_ext == "pdf":
                st.markdown(f"""
<div style='background:#18181F;border:1px solid rgba(255,255,255,0.1);
     border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.5);'>
  <div style='background:rgba(255,255,255,0.04);padding:8px 14px;display:flex;
       align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.06);'>
    <span style='font-size:0.75rem;font-weight:600;color:#A1A1AA;'>📄 {_pdf_key_val.split("/")[-1]}</span>
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
<div style='background:#18181F;border:1px solid rgba(255,255,255,0.1);
     border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.5);'>
  <div style='background:rgba(255,255,255,0.04);padding:8px 14px;display:flex;
       align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.06);'>
    <span style='font-size:0.75rem;font-weight:600;color:#A1A1AA;'>🖼 {_pdf_key_val.split("/")[-1].replace(".pdf", f".{_found_ext}")}</span>
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

    st.markdown("---")

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
n_subjects  = filtered["subject"].nunique()
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
    <div style='font-size:2.6rem;font-weight:900;color:#FFFFFF;letter-spacing:-1px;line-height:1.1;margin-top:6px;'>
      {total_pages:,}
    </div>
    <div style='margin-top:10px;'>
      <div style='display:flex;justify-content:space-between;margin-bottom:4px;'>
        <span style='font-size:0.72rem;color:#94A3B8;'>of {_PHASE1_TOTAL_PAGES_FULL:,} target</span>
        <span style='font-size:0.72rem;font-weight:700;color:{_hero_clr};'>{_hero_pct}%</span>
      </div>
      <div style='background:rgba(255,255,255,0.08);border-radius:6px;height:8px;overflow:hidden;'>
        <div style='width:{min(_hero_pct,100):.1f}%;background:{_hero_clr};height:100%;border-radius:6px;
                    box-shadow:0 0 10px {_hero_clr}66;'></div>
      </div>
    </div>
  </div>

  <!-- Students -->
  <div style='background:rgba(52,211,153,0.07);border:1px solid rgba(52,211,153,0.2);
              border-radius:14px;padding:18px 20px;'>
    <div style='font-size:0.7rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:0.1em;'>Students</div>
    <div style='font-size:2rem;font-weight:800;color:#FFFFFF;margin-top:8px;line-height:1;'>{n_students:,}</div>
    <div style='font-size:0.72rem;color:#64748B;margin-top:6px;'>{avg_pg_student} pages/student avg</div>
  </div>

  <!-- Schools -->
  <div style='background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);
              border-radius:14px;padding:18px 20px;'>
    <div style='font-size:0.7rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:0.1em;'>Schools</div>
    <div style='font-size:2rem;font-weight:800;color:#FFFFFF;margin-top:8px;line-height:1;'>{n_schools:,}</div>
    <div style='font-size:0.72rem;color:#64748B;margin-top:6px;'>{avg_students_school} students/school avg</div>
  </div>

  <!-- Deadline -->
  <div style='background:rgba(244,63,94,0.07);border:1px solid rgba(244,63,94,0.2);
              border-radius:14px;padding:18px 20px;'>
    <div style='font-size:0.7rem;font-weight:700;color:#F43F5E;text-transform:uppercase;letter-spacing:0.1em;'>Deadline</div>
    <div style='font-size:2rem;font-weight:800;color:{_dl_clr};margin-top:8px;line-height:1;'>{_days_left}</div>
    <div style='font-size:0.72rem;color:#64748B;margin-top:6px;'>days · 31 May 2026</div>
  </div>

</div>

<!-- Tier 2: Geographic coverage + collection depth -->
<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:16px;'>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>States</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{n_states}</div>
  </div>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>Districts</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{n_districts}</div>
  </div>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>Blocks</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{n_blocks}</div>
  </div>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>Records</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{total_records:,}</div>
  </div>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>Subjects</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{n_subjects}</div>
  </div>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>Pg / Record</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{avg_pg_record}</div>
  </div>
  <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:10px 12px;text-align:center;'>
    <div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>Subj / Student</div>
    <div style='font-size:1.35rem;font-weight:800;color:#E2E8F0;margin-top:4px;'>{avg_subjects_student}</div>
  </div>
</div>
""", unsafe_allow_html=True)

section("Overview")

# ══════════════════════════════════════════════════════════════════════════════
# 2. TARGETS vs ACHIEVED (Phase 1)
# ══════════════════════════════════════════════════════════════════════════════

section("Phase 1 Targets vs Achieved")

# ── Target definitions (overall total comes from targets.json) ──
PHASE1_TOTAL_PAGES = _PHASE1_TOTAL_PAGES_FULL
PHASE1_DEADLINE = pd.Timestamp("2026-05-31", tz="Asia/Kolkata")

# Overall class-level targets: 20L split equally across 3 class levels → 6.67L each
_overall_lvl_pages = round(_PHASE1_TOTAL_PAGES_FULL / 3)  # 6,66,667
CLASS_LEVEL_TARGETS = {
    lvl: {
        "pages": _overall_lvl_pages,
        "participants": round(_overall_lvl_pages / _PG_PER[lvl]),  # 6,66,667 / 50 = 13,333
        "pg_per_participant": _PG_PER[lvl],
    }
    for lvl in ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)")
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

def progress_bar_html(label, current, target, fmt_current="", fmt_target="", override_color=None):
    pct = min(current / target * 100, 100) if target else 0
    if override_color:
        color = override_color
    else:
        color = C_GREEN if pct >= 100 else C_AMBER if pct >= 60 else C_RED

    fc = fmt_current or f"{current:,.0f}"
    ft = fmt_target or f"{target:,.0f}"
    return f"""
    <div style="margin-bottom: 12px;">
        <div class="progress-label">
            <span>{label}</span>
            <span class="pct" style="color:{color}">{pct:.1f}%</span>
        </div>
        <div style="background: rgba(255,255,255,0.08); border-radius: 8px; height: 14px; overflow: hidden;">
            <div style="width: {pct:.1f}%; background: {color}; height: 100%; border-radius: 8px;
                        transition: width 0.5s;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 2px;">
            <span style="color: #a0aec0; font-size: 0.75rem;">{fc} collected</span>
            <span style="color: #a0aec0; font-size: 0.75rem;">Target: {ft}</span>
        </div>
    </div>
    """

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
                    for lvl in ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)")
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
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);
            border-radius:12px;padding:16px 20px;margin-bottom:16px;'>
  <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;'>
    <div>
      <div style='font-size:0.72rem;font-weight:600;color:#64748B;text-transform:uppercase;letter-spacing:0.07em;'>
        Overall Page Collection
      </div>
      <div style='font-size:1.9rem;font-weight:800;color:#F1F5F9;line-height:1.15;margin-top:2px;'>
        {total_pg:,}
        <span style='font-size:1rem;font-weight:500;color:#64748B;'>&nbsp;/ {cur_phase1_total:,} pages</span>
      </div>
    </div>
    <div style='text-align:right;'>
      <div style='font-size:2rem;font-weight:900;color:{_ov_clr};'>{overall_pct:.1f}%</div>
      <div style='font-size:0.72rem;color:#475569;margin-top:1px;'>{total_students_overall:,} students</div>
    </div>
  </div>
  <div style='background:rgba(255,255,255,0.07);border-radius:8px;height:10px;overflow:hidden;'>
    <div style='width:{overall_pct:.1f}%;background:{_ov_clr};height:100%;border-radius:8px;
                box-shadow:0 0 8px {_ov_clr}55;transition:width 0.6s;'></div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── 2b. Class-Level Page & Participant Targets ──
        _lvl_colors = {"Primary (1-5)": "#818CF8", "High School (6-8)": "#34D399", "Secondary (9-10)": "#F472B6"}
        _lvl_short  = {"Primary (1-5)": "Primary", "High School (6-8)": "High School", "Secondary (9-10)": "Secondary"}

        tg1, tg2 = st.columns(2)

        with tg1:
            st.markdown("<div style='font-size:0.72rem;font-weight:700;color:#64748B;text-transform:uppercase;"
                        "letter-spacing:0.07em;margin-bottom:8px;'>Pages by Class Level</div>",
                        unsafe_allow_html=True)
            for lvl, targets in cur_class_targets.items():
                lvl_pages = int(tgt_df[tgt_df["class_level"] == lvl]["num_pages"].sum())
                _pct = min(lvl_pages / targets["pages"] * 100, 100) if targets["pages"] else 0
                _clr = "#10B981" if _pct >= 100 else "#F59E0B" if _pct >= 60 else "#F43F5E"
                _ac  = _lvl_colors.get(lvl, "#94A3B8")
                st.markdown(f"""
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-left:3px solid {_ac};border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
  <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;'>
    <span style='font-size:0.82rem;font-weight:600;color:#CBD5E1;'>{_lvl_short[lvl]}</span>
    <span style='font-size:0.9rem;font-weight:700;color:{_clr};'>{_pct:.1f}%</span>
  </div>
  <div style='background:rgba(255,255,255,0.07);border-radius:4px;height:6px;overflow:hidden;margin-bottom:5px;'>
    <div style='width:{_pct:.1f}%;background:{_clr};height:100%;border-radius:4px;'></div>
  </div>
  <div style='display:flex;justify-content:space-between;'>
    <span style='font-size:0.72rem;color:#64748B;'>{lvl_pages:,} collected</span>
    <span style='font-size:0.72rem;color:#475569;'>Target: {targets["pages"]:,}</span>
  </div>
</div>""", unsafe_allow_html=True)

        with tg2:
            st.markdown("<div style='font-size:0.72rem;font-weight:700;color:#64748B;text-transform:uppercase;"
                        "letter-spacing:0.07em;margin-bottom:8px;'>Participants by Class Level</div>",
                        unsafe_allow_html=True)
            for lvl, targets in cur_class_targets.items():
                lvl_students = tgt_df[tgt_df["class_level"] == lvl]["student_id"].nunique()
                _pct = min(lvl_students / targets["participants"] * 100, 100) if targets["participants"] else 0
                _clr = "#10B981" if _pct >= 100 else "#F59E0B" if _pct >= 60 else "#F43F5E"
                _ac  = _lvl_colors.get(lvl, "#94A3B8")
                st.markdown(f"""
<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-left:3px solid {_ac};border-radius:8px;padding:10px 14px;margin-bottom:8px;'>
  <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;'>
    <span style='font-size:0.82rem;font-weight:600;color:#CBD5E1;'>{_lvl_short[lvl]}</span>
    <span style='font-size:0.9rem;font-weight:700;color:{_clr};'>{_pct:.1f}%</span>
  </div>
  <div style='background:rgba(255,255,255,0.07);border-radius:4px;height:6px;overflow:hidden;margin-bottom:5px;'>
    <div style='width:{_pct:.1f}%;background:{_clr};height:100%;border-radius:4px;'></div>
  </div>
  <div style='display:flex;justify-content:space-between;'>
    <span style='font-size:0.72rem;color:#64748B;'>{lvl_students:,} students</span>
    <span style='font-size:0.72rem;color:#475569;'>Target: {targets["participants"]:,}</span>
  </div>
</div>""", unsafe_allow_html=True)

        # ── Demographics ──────────────────────────────────────────────────────────
        section("Demographics")

        _DEM_H = 210

        _DEM_M = dict(l=10, r=10, t=30, b=0)

        # Row 1: Class Level, Board, Gender, State (4 equal cols)
        _dem_r1 = st.columns(4, gap="small")
        _CLASS_COLORS = [C_INDIGO, C_GREEN, C_VIOLET]
        with _dem_r1[0]:
            _counts = tgt_df["class_level"].value_counts()
            _fig = go.Figure(go.Pie(labels=_counts.index, values=_counts.values, hole=0.5,
                marker=dict(colors=_CLASS_COLORS), textinfo="label+percent", textposition="outside"))
            _fig.update_layout(**chart_layout(title="Class Level Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
            st.plotly_chart(_fig, use_container_width=True, key=f"dem_class_{current_lang}")

        with _dem_r1[1]:
            _counts = tgt_df["board"].value_counts()
            _fig = go.Figure(go.Pie(labels=_counts.index, values=_counts.values, hole=0.5,
                marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside"))
            _fig.update_layout(**chart_layout(title="Board Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
            st.plotly_chart(_fig, use_container_width=True, key=f"dem_board_{current_lang}")

        with _dem_r1[2]:
            _counts = tgt_df["gender"].value_counts()
            _g_color_map_d = {"Female": C_FEMALE, "Male": C_MALE}
            _g_colors_d = [_g_color_map_d.get(l, C_GREY) for l in _counts.index]
            _fig = go.Figure(go.Pie(labels=_counts.index, values=_counts.values, hole=0.5,
                marker=dict(colors=_g_colors_d), textinfo="label+percent", textposition="outside"))
            _fig.update_layout(**chart_layout(title="Gender Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
            st.plotly_chart(_fig, use_container_width=True, key=f"dem_gender_{current_lang}")

        with _dem_r1[3]:
            _state_counts = tgt_df[~tgt_df["state"].isin(["Unknown", ""])]["state"].value_counts()
            _fig = go.Figure(go.Pie(labels=_state_counts.index, values=_state_counts.values, hole=0.5,
                marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside"))
            _fig.update_layout(**chart_layout(title="State Split", showlegend=False, height=_DEM_H, margin=_DEM_M))
            st.plotly_chart(_fig, use_container_width=True, key=f"dem_state_{current_lang}")

        # Row 2: Rural/Urban, School Type, Medium of Instruction, Sample Type (4 equal cols)
        _dem_r2 = st.columns(4, gap="small")
        with _dem_r2[0]:
            _ru_counts = tgt_df["rural_urban"].replace("", "Not Mentioned").value_counts()
            _ru_colors_d = [{"Rural": C_RURAL, "Urban": C_URBAN}.get(l, C_GREY) for l in _ru_counts.index]
            _fig = go.Figure(go.Pie(labels=_ru_counts.index, values=_ru_counts.values, hole=0.5,
                marker=dict(colors=_ru_colors_d), textinfo="label+percent", textposition="outside"))
            _fig.update_layout(**chart_layout(title="Rural / Urban", showlegend=False, height=_DEM_H, margin=_DEM_M))
            st.plotly_chart(_fig, use_container_width=True, key=f"dem_ru_{current_lang}")

        with _dem_r2[1]:
            _st_counts = tgt_df["school_type"].replace("", "Not Mentioned").value_counts()
            _st_colors_d = [{"government": C_GOVT, "government_aided": C_AIDED, "private": C_PRIVATE}.get(str(l).lower(), C_GREY) for l in _st_counts.index]
            _fig = go.Figure(go.Pie(labels=_st_counts.index, values=_st_counts.values, hole=0.5,
                marker=dict(colors=_st_colors_d), textinfo="label+percent", textposition="outside"))
            _fig.update_layout(**chart_layout(title="School Type", showlegend=False, height=_DEM_H, margin=_DEM_M))
            st.plotly_chart(_fig, use_container_width=True, key=f"dem_st_{current_lang}")

        with _dem_r2[2]:
            _med_d = tgt_df[tgt_df["medium_of_instruction"] != "Not Mentioned"]
            if len(_med_d):
                _med_counts = _med_d["medium_of_instruction"].value_counts()
                _fig = go.Figure(go.Pie(labels=_med_counts.index, values=_med_counts.values, hole=0.5,
                    marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside"))
                _fig.update_layout(**chart_layout(title="Medium of Instruction", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_medium_{current_lang}")
            else:
                st.info("No medium data.")

        with _dem_r2[3]:
            _samp_d = tgt_df[tgt_df["sample_type"] != "Not Mentioned"]
            if len(_samp_d):
                _samp_counts = _samp_d["sample_type"].value_counts()
                _fig = go.Figure(go.Pie(labels=_samp_counts.index, values=_samp_counts.values, hole=0.5,
                    marker=dict(colors=COLORS[3:]), textinfo="label+percent", textposition="outside"))
                _fig.update_layout(**chart_layout(title="Sample Type", showlegend=False, height=_DEM_H, margin=_DEM_M))
                st.plotly_chart(_fig, use_container_width=True, key=f"dem_sample_{current_lang}")
            else:
                st.info("No sample data.")

        # Row 3: Gender × Class Level pages bar (full width)
        _dem_gc = tgt_df.groupby(["class_level", "gender"])["num_pages"].sum().unstack(fill_value=0)
        _fig_gcbar = go.Figure()
        _g_bar_cm = {"Female": C_FEMALE, "Male": C_MALE}
        for _g in _dem_gc.columns:
            _fig_gcbar.add_trace(go.Bar(name=_g, x=_dem_gc.index, y=_dem_gc[_g],
                                        marker_color=_g_bar_cm.get(_g, C_GREY)))
        _fig_gcbar.update_layout(**chart_layout(title="Pages Collected: Gender × Class Level", barmode="group", height=_DEM_H, margin=dict(l=10, r=10, t=30, b=10)))
        st.plotly_chart(_fig_gcbar, use_container_width=True, key=f"dem_gcbar_{current_lang}")

        # ── 2c. Avg Pages per Participant ──
        st.markdown("")
        pp_col = st.container()

        with pp_col:
            st.markdown("<div style='font-size:0.72rem;font-weight:700;color:#64748B;text-transform:uppercase;"
                        "letter-spacing:0.07em;margin-bottom:8px;'>Avg Pages per Participant vs Target</div>",
                        unsafe_allow_html=True)
            _pp_html = "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;'>"
            for lvl, targets in cur_class_targets.items():
                lvl_df = tgt_df[tgt_df["class_level"] == lvl]
                lvl_students = lvl_df["student_id"].nunique()
                lvl_pages = int(lvl_df["num_pages"].sum())
                actual_pp = round(lvl_pages / lvl_students, 1) if lvl_students else 0
                target_pp = targets["pg_per_participant"]
                passed = actual_pp >= target_pp
                _pc = "#10B981" if passed else "#F43F5E"
                _ac = _lvl_colors.get(lvl, "#94A3B8")
                _pp_html += (
                    f"<div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);"
                    f"border-top:2px solid {_ac};border-radius:6px;padding:8px 10px;text-align:center;'>"
                    f"<div style='font-size:0.65rem;font-weight:600;color:#64748B;text-transform:uppercase;"
                    f"letter-spacing:0.06em;margin-bottom:4px;'>{_lvl_short[lvl]}</div>"
                    f"<div style='font-size:1.2rem;font-weight:800;color:{_pc};'>{actual_pp}</div>"
                    f"<div style='font-size:0.65rem;color:#475569;margin-top:2px;'>pg/student · target {target_pp}</div>"
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

        # ── 2e. School Type & Rural/Urban ──
        st.markdown("")
        su1, su2 = st.columns(2)

        # safe defaults so compliance summary always has values
        _govt_total_pct = 0.0
        _rural_pct = 0.0
        _aspir_pct = 0.0
        _aspir_state_n = 0
        _left_pct = 0.0
        _total_handed = 0

        with su1:
            st.markdown("**School Type (Target: ≥60% Government)**")
            _total_n = len(tgt_df)
            if _total_n > 0:
                _st_vals = tgt_df["school_type"].str.lower().str.strip()
                _govt_n  = int((_st_vals == "government").sum())
                _aided_n = int((_st_vals == "government_aided").sum())
                _priv_n  = int((_st_vals == "private").sum())
                _other_sn = _total_n - _govt_n - _aided_n - _priv_n
                _govt_total_n   = _govt_n + _aided_n
                _govt_total_pct = round(_govt_total_n / _total_n * 100, 1)
                _govt_passed    = _govt_total_pct >= 60
                _gp = round(_govt_n / _total_n * 100, 1)
                _ap = round(_aided_n / _total_n * 100, 1)
                _pp = round(_priv_n / _total_n * 100, 1)
                _op = round(_other_sn / _total_n * 100, 1)
                _st_segments = [
                    (_govt_n,   _gp,  "Govt",    C_GOVT),
                    (_aided_n,  _ap,  "Aided",   C_AIDED),
                    (_priv_n,   _pp,  "Private", C_PRIVATE),
                    (_other_sn, _op,  "Other",   C_GREY),
                ]
                _st_bar = "<div style='position:relative;margin-bottom:6px;'>"
                # dashed line + label — outside overflow:hidden so it extends above bar
                _st_bar += (
                    "<div style='position:absolute;left:60%;top:-18px;bottom:0;width:0;"
                    "border-left:2px dashed #F59E0B;z-index:2;'></div>"
                    "<div style='position:absolute;left:calc(60% + 4px);top:-18px;"
                    "color:#F59E0B;font-size:0.7rem;font-weight:600;white-space:nowrap;z-index:2;'>60%</div>"
                )
                _st_bar += "<div style='display:flex;width:100%;height:40px;border-radius:8px;overflow:hidden;'>"
                for _cnt, _pct, _lbl, _col in _st_segments:
                    if _cnt > 0:
                        _inner = f"{_lbl} {_pct}%" if _pct >= 15 else ""
                        _st_bar += (
                            f"<div style='width:{_pct}%;background:{_col};display:flex;align-items:center;"
                            f"justify-content:center;font-size:0.78rem;font-weight:600;color:#fff;"
                            f"white-space:nowrap;flex-shrink:0;' title='{_lbl}: {_cnt:,} ({_pct}%)'>"
                            f"{_inner}</div>"
                        )
                _st_bar += "</div>"
                _st_bar += "</div>"
                # legend row below bar
                _st_legend = "<div style='display:flex;flex-wrap:wrap;gap:10px;margin-bottom:4px;'>"
                for _cnt, _pct, _lbl, _col in _st_segments:
                    if _cnt > 0:
                        _st_legend += (
                            f"<span style='display:inline-flex;align-items:center;gap:4px;'>"
                            f"<span style='width:10px;height:10px;border-radius:2px;background:{_col};display:inline-block;flex-shrink:0;'></span>"
                            f"<span style='color:#E2E8F0;font-size:0.78rem;font-weight:500;'>{_lbl} {_pct}%</span></span>"
                        )
                _st_legend += "</div>"
                st.markdown(_st_bar + _st_legend, unsafe_allow_html=True)
            else:
                st.info("No data.")

        with su2:
            st.markdown("**Rural / Urban (Target: ≥50% Rural)**")
            if _total_n > 0:
                _ru_vals   = tgt_df["rural_urban"].str.lower().str.strip()
                _rural_n   = int((_ru_vals == "rural").sum())
                _urban_n   = int((_ru_vals == "urban").sum())
                _other_run = _total_n - _rural_n - _urban_n
                _rural_pct = round(_rural_n / _total_n * 100, 1)
                _urban_pct = round(_urban_n / _total_n * 100, 1)
                _other_rup = round(_other_run / _total_n * 100, 1)
                _rural_passed = _rural_pct >= 50
                _ru_segments = [
                    (_rural_n,   _rural_pct, "Rural", C_RURAL),
                    (_urban_n,   _urban_pct, "Urban", C_URBAN),
                    (_other_run, _other_rup, "Other", C_GREY),
                ]
                _ru_bar = "<div style='position:relative;margin-bottom:6px;'>"
                _ru_bar += (
                    "<div style='position:absolute;left:50%;top:-18px;bottom:0;width:0;"
                    "border-left:2px dashed #F59E0B;z-index:2;'></div>"
                    "<div style='position:absolute;left:calc(50% + 4px);top:-18px;"
                    "color:#F59E0B;font-size:0.7rem;font-weight:600;white-space:nowrap;z-index:2;'>50%</div>"
                )
                _ru_bar += "<div style='display:flex;width:100%;height:40px;border-radius:8px;overflow:hidden;'>"
                for _cnt, _pct, _lbl, _col in _ru_segments:
                    if _cnt > 0:
                        _inner = f"{_lbl} {_pct}%" if _pct >= 15 else ""
                        _ru_bar += (
                            f"<div style='width:{_pct}%;background:{_col};display:flex;align-items:center;"
                            f"justify-content:center;font-size:0.78rem;font-weight:600;color:#fff;"
                            f"white-space:nowrap;flex-shrink:0;' title='{_lbl}: {_cnt:,} ({_pct}%)'>"
                            f"{_inner}</div>"
                        )
                _ru_bar += "</div>"
                _ru_bar += "</div>"
                _ru_legend = "<div style='display:flex;flex-wrap:wrap;gap:10px;margin-bottom:4px;'>"
                for _cnt, _pct, _lbl, _col in _ru_segments:
                    if _cnt > 0:
                        _ru_legend += (
                            f"<span style='display:inline-flex;align-items:center;gap:4px;'>"
                            f"<span style='width:10px;height:10px;border-radius:2px;background:{_col};display:inline-block;flex-shrink:0;'></span>"
                            f"<span style='color:#E2E8F0;font-size:0.78rem;font-weight:500;'>{_lbl} {_pct}%</span></span>"
                        )
                _ru_legend += "</div>"
                st.markdown(_ru_bar + _ru_legend, unsafe_allow_html=True)

        # ── 2f. Aspirational Districts & Left-handedness ──
        st.markdown("")
        al1, al2 = st.columns(2)

        with al1:
            _aspir_pct = 0.0
            if _total_n > 0:
                _aspir_states = tgt_df[tgt_df["aspirational_district"] == True]["state"].unique()
                _aspir_state_df = tgt_df[tgt_df["state"].isin(_aspir_states)]
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
                    fmt_target=f"Target: ≥{REGIONAL_MEDIUM_TARGET}%",
                    override_color="#10B981" if _rm_passed else "#F43F5E"
                ), unsafe_allow_html=True)
                st.markdown(f"&nbsp;&nbsp;{badge('PASS' if _rm_passed else 'FAIL', _rm_passed)}", unsafe_allow_html=True)
            else:
                st.info("No data available.")

        with al2:
            _left_pct = 0.0
            if "handedness" in tgt_df.columns and _total_n > 0:
                _handed_df   = tgt_df[tgt_df["handedness"].isin(["left", "right"])]
                _total_handed = len(_handed_df)
                _left_n       = int((tgt_df["handedness"] == "left").sum())
                _right_n      = int((tgt_df["handedness"] == "right").sum())
                _left_pct     = round(_left_n / _total_handed * 100, 1) if _total_handed else 0.0
                _right_pct    = round(_right_n / _total_handed * 100, 1) if _total_handed else 0.0
                _left_passed  = _left_pct >= 5
                if _total_handed > 0:
                    st.markdown("**Left-handedness (Target: ≥5%)**")
                    _hd_segments = [
                        (_left_n,  _left_pct,  "Left",  C_LEFT),
                        (_right_n, _right_pct, "Right", C_RIGHT),
                    ]
                    _hd_bar = "<div style='position:relative;margin-bottom:6px;'>"
                    _hd_bar += (
                        "<div style='position:absolute;left:5%;top:-18px;bottom:0;width:0;"
                        "border-left:2px dashed #F59E0B;z-index:2;'></div>"
                        "<div style='position:absolute;left:calc(5% + 4px);top:-18px;"
                        "color:#F59E0B;font-size:0.7rem;font-weight:600;white-space:nowrap;z-index:2;'>5%</div>"
                    )
                    _hd_bar += "<div style='display:flex;width:100%;height:40px;border-radius:8px;overflow:hidden;'>"
                    for _cnt, _pct, _lbl, _col in _hd_segments:
                        if _cnt > 0:
                            _inner = f"{_lbl} {_pct}%" if _pct >= 15 else ""
                            _hd_bar += (
                                f"<div style='width:{_pct}%;background:{_col};display:flex;align-items:center;"
                                f"justify-content:center;font-size:0.78rem;font-weight:600;color:#fff;"
                                f"white-space:nowrap;flex-shrink:0;' title='{_lbl}: {_cnt:,} ({_pct}%)'>"
                                f"{_inner}</div>"
                            )
                    _hd_bar += "</div>"
                    _hd_bar += "</div>"
                    _hd_legend = "<div style='display:flex;flex-wrap:wrap;gap:10px;margin-bottom:4px;'>"
                    for _cnt, _pct, _lbl, _col in _hd_segments:
                        _hd_legend += (
                            f"<span style='display:inline-flex;align-items:center;gap:4px;'>"
                            f"<span style='width:10px;height:10px;border-radius:2px;background:{_col};display:inline-block;flex-shrink:0;'></span>"
                            f"<span style='color:#E2E8F0;font-size:0.78rem;font-weight:500;'>{_lbl} {_pct}%</span></span>"
                        )
                    _hd_legend += "</div>"
                    st.markdown(_hd_bar + _hd_legend, unsafe_allow_html=True)

        # ── 2g. Pre-compute multi-subject stats for summary line ──
        _ms_parts = []
        for lvl in ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)"):
            lvl_df = tgt_df[tgt_df["class_level"] == lvl]
            lvl_students = lvl_df["student_id"].nunique()
            if lvl_students == 0:
                continue
            n_required = lvl_df["subject_category"].nunique()
            student_subj = lvl_df.groupby("student_id")["subject_category"].nunique()
            all_subj = int((student_subj >= n_required).sum())
            specific_only = int((student_subj == 1).sum())
            all_pct = round(all_subj / lvl_students * 100, 1)
            spec_pct = round(specific_only / lvl_students * 100, 1)
            _ms_parts.append((lvl, lvl_students, all_subj, all_pct, specific_only, spec_pct))

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
                f"<span style='font-size:0.82rem;color:#E2E8F0;'>{label}</span></div>"
            )

        summary_html = f"""
<div style='margin-bottom:12px;'>
  <div style='font-size:1.05rem;font-weight:700;color:#F1F5F9;letter-spacing:0.02em;margin-bottom:10px;'>
    Overall Compliance Summary
  </div>
  <div style='display:flex;gap:10px;margin-bottom:14px;'>
    <div style='flex:1;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);border-radius:10px;padding:10px 14px;text-align:center;'>
      <div style='font-size:1.8rem;font-weight:800;color:#10B981;line-height:1.1;'>{n_pass}</div>
      <div style='font-size:0.72rem;color:#6EE7B7;text-transform:uppercase;letter-spacing:0.08em;margin-top:3px;'>Passing</div>
    </div>
    <div style='flex:1;background:rgba(244,63,94,0.12);border:1px solid rgba(244,63,94,0.3);border-radius:10px;padding:10px 14px;text-align:center;'>
      <div style='font-size:1.8rem;font-weight:800;color:#F43F5E;line-height:1.1;'>{n_fail}</div>
      <div style='font-size:0.72rem;color:#FDA4AF;text-transform:uppercase;letter-spacing:0.08em;margin-top:3px;'>Failing</div>
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
            _ms_cards = ""
            for lvl, n, _a, a_pct, _s, s_pct in _ms_parts:
                a_ok  = a_pct  >= 30
                s_ok  = s_pct  >= 30
                a_clr = "#10B981" if a_ok  else "#F43F5E"
                s_clr = "#10B981" if s_ok  else "#F43F5E"
                _ms_cards += (
                    f"<div style='flex:1;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);"
                    f"border-radius:8px;padding:8px 12px;min-width:0;'>"
                    f"<div style='font-size:0.75rem;font-weight:700;color:#94A3B8;text-transform:uppercase;"
                    f"letter-spacing:0.06em;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>{lvl}</div>"
                    f"<div style='font-size:0.7rem;color:#64748B;margin-bottom:2px;'>{n} students</div>"
                    f"<div style='display:flex;gap:8px;margin-top:4px;flex-wrap:wrap;'>"
                    f"<span style='font-size:0.78rem;color:#CBD5E1;'>All:&nbsp;<b style='color:{a_clr};'>{a_pct}%</b>&nbsp;{badge('PASS' if a_ok else 'FAIL', a_ok)}</span>"
                    f"<span style='color:#334155;'>·</span>"
                    f"<span style='font-size:0.78rem;color:#CBD5E1;'>Specific:&nbsp;<b style='color:{s_clr};'>{s_pct}%</b>&nbsp;{badge('PASS' if s_ok else 'FAIL', s_ok)}</span>"
                    f"</div></div>"
                )
            st.markdown(
                f"<div style='margin-top:10px;'>"
                f"<div style='font-size:0.72rem;font-weight:600;color:#64748B;text-transform:uppercase;"
                f"letter-spacing:0.07em;margin-bottom:6px;'>Subject Coverage per Student &nbsp;·&nbsp; Target ≥30% each</div>"
                f"<div style='display:flex;gap:8px;'>{_ms_cards}</div></div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# SUBJECT COVERAGE BY CLASS LEVEL (dynamic target = 100 / n_subjects)
# ══════════════════════════════════════════════════════════════════════════════

rm1, rm2 = st.columns(2)

with rm1:
    _rm1_aspir_pct = 0.0
    _rm1_total_n = len(filtered)
    if _rm1_total_n > 0:
        _rm1_aspir_states = filtered[filtered["aspirational_district"] == True]["state"].unique()
        _rm1_aspir_state_df = filtered[filtered["state"].isin(_rm1_aspir_states)]
        _rm1_aspir_state_n  = len(_rm1_aspir_state_df)
        _rm1_aspir_n        = int((filtered["aspirational_district"] == True).sum())
        _rm1_aspir_pct      = round(_rm1_aspir_n / _rm1_aspir_state_n * 100, 1) if _rm1_aspir_state_n else 0.0
        _rm1_aspir_passed   = _rm1_aspir_pct >= 15
        if _rm1_aspir_state_n > 0:
            st.markdown("**Aspirational Districts (Target: ≥15% of records from aspirational-district states)**")
            st.markdown(progress_bar_html(
                "Aspirational Districts", _rm1_aspir_n, _rm1_aspir_state_n,
                f"{_rm1_aspir_n:,} / {_rm1_aspir_state_n:,} ({_rm1_aspir_pct}%)",
                "Target: ≥15%",
                override_color="#10B981" if _rm1_aspir_passed else "#F43F5E"
            ), unsafe_allow_html=True)
            st.markdown(f"&nbsp;&nbsp;{badge('PASS' if _rm1_aspir_passed else 'FAIL', _rm1_aspir_passed)}", unsafe_allow_html=True)

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
        text=[f"{p:,}" for p in state_stats["pages"]], textposition="outside",
    ))
    _fig.update_layout(**chart_layout(title="Pages by State"))
    st.plotly_chart(_fig, use_container_width=True)

with sl2:
    _fig = go.Figure()
    _fig.add_trace(go.Bar(name="Students", x=state_stats["state"], y=state_stats["students"],
        marker_color=COLORS[1], text=state_stats["students"], textposition="outside"))
    _fig.add_trace(go.Bar(name="Schools", x=state_stats["state"], y=state_stats["schools"],
        marker_color=COLORS[2], text=state_stats["schools"], textposition="outside"))
    _fig.add_trace(go.Bar(name="Districts", x=state_stats["state"], y=state_stats["districts"],
        marker_color=COLORS[3], text=state_stats["districts"], textposition="outside"))
    _fig.update_layout(**chart_layout(title="Students, Schools & Districts by State", barmode="group"))
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
    <div style='font-size:1.6rem;font-weight:800;color:#F1F5F9;line-height:1.1;margin-top:4px;'>{_d_n_districts}</div>
  </div>
  <div style='background:rgba(52,211,153,0.07);border:1px solid rgba(52,211,153,0.2);border-radius:10px;padding:12px 16px;'>
    <div style='font-size:0.65rem;font-weight:700;color:#34D399;text-transform:uppercase;letter-spacing:.08em;'>Pages</div>
    <div style='font-size:1.6rem;font-weight:800;color:#F1F5F9;line-height:1.1;margin-top:4px;'>{_d_total_pages:,}</div>
  </div>
  <div style='background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);border-radius:10px;padding:12px 16px;'>
    <div style='font-size:0.65rem;font-weight:700;color:#FBBF24;text-transform:uppercase;letter-spacing:.08em;'>Students</div>
    <div style='font-size:1.6rem;font-weight:800;color:#F1F5F9;line-height:1.1;margin-top:4px;'>{_d_total_students:,}</div>
  </div>
  <div style='background:rgba(192,132,252,0.07);border:1px solid rgba(192,132,252,0.2);border-radius:10px;padding:12px 16px;'>
    <div style='font-size:0.65rem;font-weight:700;color:#C084FC;text-transform:uppercase;letter-spacing:.08em;'>Top District</div>
    <div style='font-size:1.1rem;font-weight:800;color:#F1F5F9;line-height:1.1;margin-top:4px;'>{_d_top_dist}</div>
    <div style='font-size:0.65rem;color:#64748B;margin-top:2px;'>{_d_top_pages:,} pages</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Charts row 1: pages + students/schools
    dd1, dd2 = st.columns(2)
    with dd1:
        _fig = go.Figure(go.Bar(
            x=dist_stats["district"], y=dist_stats["pages"],
            marker_color=C_GREEN,
            text=[f"{p:,}" for p in dist_stats["pages"]], textposition="outside",
        ))
        _fig.update_layout(**chart_layout(title="Pages by District"))
        st.plotly_chart(_fig, use_container_width=True)

    with dd2:
        _fig = go.Figure()
        _fig.add_trace(go.Bar(name="Students", x=dist_stats["district"], y=dist_stats["students"],
            marker_color=COLORS[1], text=dist_stats["students"], textposition="outside"))
        _fig.add_trace(go.Bar(name="Schools", x=dist_stats["district"], y=dist_stats["schools"],
            marker_color=COLORS[2], text=dist_stats["schools"], textposition="outside"))
        _fig.add_trace(go.Bar(name="Blocks", x=dist_stats["district"], y=dist_stats["blocks"],
            marker_color=COLORS[3], text=dist_stats["blocks"], textposition="outside"))
        _fig.update_layout(**chart_layout(title="Students, Schools & Blocks by District", barmode="group"))
        st.plotly_chart(_fig, use_container_width=True)

    # Charts row 2: pg/student bar + rural/urban breakdown per district
    dd3, dd4 = st.columns(2)
    with dd3:
        _pps = dist_stats.sort_values("pg_per_student", ascending=True)
        _fig = go.Figure(go.Bar(
            x=_pps["pg_per_student"], y=_pps["district"],
            orientation="h",
            marker_color=[C_GREEN if v >= 50 else C_RED for v in _pps["pg_per_student"]],
            text=[f"{v}" for v in _pps["pg_per_student"]], textposition="outside",
        ))
        _fig.add_vline(x=50, line_dash="dash", line_color=C_AMBER,
            annotation_text="50 pg target", annotation_position="top right",
            annotation_font_color=C_AMBER)
        _fig.update_layout(**chart_layout(title="Avg Pages / Student by District",
            height=max(300, len(_pps) * 30),
            xaxis_title="Pages/Student",
            yaxis=dict(showgrid=False, zeroline=False, showline=False, color="#A1A1AA")))
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
        text=[f"{p:,}" for p in block_stats["pages"]], textposition="outside",
    ))
    fig.update_layout(**chart_layout(title="Pages by Block"))
    st.plotly_chart(fig, use_container_width=True)

with b2:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Unique Students", x=block_stats["block"], y=block_stats["students"],
        marker_color=COLORS[1], text=block_stats["students"], textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Unique Schools", x=block_stats["block"], y=block_stats["schools"],
        marker_color=COLORS[2], text=block_stats["schools"], textposition="outside",
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

st.markdown("<div style='font-size:0.8rem;font-weight:700;color:#64748B;text-transform:uppercase;"
            "letter-spacing:0.08em;margin:12px 0 6px;'>Block Statistics</div>",
            unsafe_allow_html=True)
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
#         text=[f"{p:,}" for p in _top_schools["pages"]], textposition="outside",
#     ))
#     _fig.update_layout(**chart_layout(title="Top 15 Schools by Pages Collected",
#                                       xaxis=dict(tickangle=-35, showgrid=False, zeroline=False,
#                                                  showline=False, color="#A1A1AA")))
#     st.plotly_chart(_fig, use_container_width=True)

# with _sch2:
#     _pps = school_stats.sort_values("pg_per_student", ascending=True).head(15)
#     _fig = go.Figure(go.Bar(
#         x=_pps["pg_per_student"], y=_pps["school_name"],
#         orientation="h",
#         marker_color=[C_GREEN if v >= 50 else C_RED for v in _pps["pg_per_student"]],
#         text=[f"{v}" for v in _pps["pg_per_student"]], textposition="outside",
#     ))
#     _fig.add_vline(x=50, line_dash="dash", line_color=C_AMBER,
#         annotation_text="50 pg target", annotation_position="top right",
#         annotation_font_color=C_AMBER)
#     _fig.update_layout(**chart_layout(title="Avg Pages / Student by School",
#         height=max(370, len(_pps) * 28),
#         xaxis_title="Pages/Student",
#         yaxis=dict(showgrid=False, zeroline=False, showline=False, color="#A1A1AA")))
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
            marker_color=COLORS[0], text=class_pages["num_pages"], textposition="outside",
        ))
        fig.update_layout(**chart_layout(title="Total Pages by Class"))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        class_students = class_data.groupby("class")["student_id"].nunique().sort_index().reset_index()
        class_students["class"] = class_students["class"].astype(int).astype(str)
        fig = go.Figure(go.Bar(
            x=class_students["class"], y=class_students["student_id"],
            marker_color=COLORS[1], text=class_students["student_id"], textposition="outside",
        ))
        fig.update_layout(**chart_layout(title="Unique Students by Class"))
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    s1, s2 = st.columns(2)
    with s1:
        subj_pages = filtered.groupby("subject")["num_pages"].sum().sort_values(ascending=True).reset_index()
        fig = go.Figure(go.Bar(
            x=subj_pages["num_pages"], y=subj_pages["subject"],
            orientation="h", marker_color=COLORS[2],
            text=[f"{p:,}" for p in subj_pages["num_pages"]], textposition="outside",
        ))
        fig.update_layout(**chart_layout(title="Pages by Subject", height=max(380, len(subj_pages) * 26)))
        st.plotly_chart(fig, use_container_width=True)
    with s2:
        cat_counts = filtered["subject_category"].value_counts()
        fig = go.Figure(go.Pie(
            labels=cat_counts.index, values=cat_counts.values, hole=0.5,
            marker=dict(colors=COLORS), textinfo="label+percent", textposition="outside",
        ))
        fig.update_layout(**chart_layout(title="Subject Category Breakdown", showlegend=False))
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    heat = filtered.groupby(["class_level", "subject_category"])["num_pages"].sum().unstack(fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=heat.values, x=heat.columns.tolist(), y=heat.index.tolist(),
        colorscale=[[0, "#1E1B4B"], [0.3, "#4338CA"], [0.6, "#818CF8"], [1.0, "#C7D2FE"]],
        text=heat.values, texttemplate="%{text:,}",
        textfont=dict(color="white", size=11),
    ))
    fig.update_layout(**chart_layout(title="Pages Heatmap: Class Level × Subject Category", height=380))
    st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# 6b. STUDENT MULTI-SUBJECT COVERAGE
# ══════════════════════════════════════════════════════════════════════════════

section("Subject Coverage by Class Level")

_sc_lvl_sel = st.selectbox(
    "Select Class Level",
    ("Primary (1-5)", "High School (6-8)", "Secondary (9-10)"),
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
    _sc_html = "<table style='width:100%; color:#e2e8f0; font-size:0.85rem;'>"
    _sc_html += "<tr style='border-bottom:1px solid rgba(255,255,255,0.1);'>"
    for h in ["Subject", "Pages", "Actual %", "Target %", "Status"]:
        align = "left" if h == "Subject" else "right" if h != "Status" else "center"
        _sc_html += f"<th style='text-align:{align}; padding:8px;'>{h}</th>"
    _sc_html += "</tr>"
    for r in _sc_tbl:
        _sc_html += "<tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>"
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
        marker_color=COLORS[1], text=subj_dist["Students"], textposition="outside",
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
    for i, lvl in enumerate(sorted(filtered["class_level"].unique())):
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

section("Raw Data Explorer")

with st.expander("View & download filtered data", expanded=False):
    _show_pdf_key = st.toggle("Show pdf_key column", value=False, key="raw_show_pdf_key")
    _raw_cols = [c for c in filtered.columns if c != "pdf_key"]
    if _show_pdf_key:
        _raw_cols = _raw_cols + ["pdf_key"]
    st.dataframe(filtered[_raw_cols], use_container_width=True, height=400)

    csv = filtered[_raw_cols].to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "ocr_vs_filtered_data.csv", "text/csv")
