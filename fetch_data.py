#!/usr/bin/env python3
"""
fetch_data.py — run by cron every 6 hours.

Fetches all student JSON metadata from MinIO, counts PDF pages (with a
persistent local cache so each PDF is only downloaded once), normalises
fields exactly as app.py does, and writes the result to data_cache.parquet.
The Streamlit app reads that file; if it is missing it falls back to a live
bucket load.
"""

import os
import io
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
import pypdf
import urllib3
from botocore.client import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────
MINIO_ENDPOINT   = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
MINIO_BUCKET     = os.environ.get("MINIO_BUCKET")
MINIO_PREFIX     = os.environ.get("MINIO_PREFIX")

BASE_DIR        = Path(__file__).parent
CACHE_PARQUET   = BASE_DIR / "data_cache.parquet"
PAGE_CACHE_FILE = BASE_DIR / ".page_count_cache.json"
LAST_UPDATED    = BASE_DIR / ".last_updated.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "fetch_data.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Field maps (kept in sync with app.py) ─────────────────────────────────────
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
    "social_science": "Social Science",
    "history": "History", "history ": "History", "hiistory": "History",
    "geography": "Geography", "geography ": "Geography", "geogrphy": "Geography",
    "civics": "Civics", "civics ": "Civics",
    "economics": "Economics", "political science": "Political Science",
    "e.v.s": "EVS", "evs": "EVS", "environment": "EVS",
    "environmental": "EVS", "environmantal": "EVS",
    "paryavaran": "EVS", "paryawaran": "EVS", "hamara parivesh": "EVS",
    "sanskrit": "Sanskrit", "sanskrit ": "Sanskrit",
    "sanskrit grammar": "Sanskrit Grammar",
    "sanskrit_grammar": "Sanskrit Grammar",
    "computer": "Computer Science", "it": "Computer Science",
    "general knowledge": "General Knowledge", "genral knowedge": "General Knowledge",
    "physical education": "Physical Education",
    "physical_education": "Physical Education",
    "business studies": "Business Studies",
    "moral education": "Moral Education",
    "agriculture": "Agriculture", "agricultur": "Agriculture",
    "agriculture ": "Agriculture", "krishi vigyan": "Agriculture",
    "home science": "Home Science", "grihkaushal": "Home Science",
    "grikaushal": "Home Science", "gruh darshika": "Home Science",
    "mahan vyaktiva": "Moral Education",
    "hindi_grammar": "Hindi Grammar",
    "english_grammar": "English Grammar",
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

STATE_TO_LANGUAGE = {
    "uttar_pradesh": "Hindi", "bihar": "Hindi", "rajasthan": "Hindi",
    "madhya_pradesh": "Hindi", "haryana": "Hindi", "himachal_pradesh": "Hindi",
    "delhi": "Hindi", "uttarakhand": "Hindi", "chhattisgarh": "Hindi", "jharkhand": "Hindi",
    "west_bengal": "Bengali", "karnataka": "Kannada", "kerala": "Malayalam",
    "maharashtra": "Marathi", "odisha": "Odia", "punjab": "Punjabi",
    "tamil_nadu": "Tamil", "andhra_pradesh": "Telugu", "telangana": "Telugu",
}

CLASS_LEVEL_FROM_GRADE = {
    1: "Primary (1-5)", 2: "Primary (1-5)", 3: "Primary (1-5)",
    4: "Primary (1-5)", 5: "Primary (1-5)",
    6: "High School (6-8)", 7: "High School (6-8)", 8: "High School (6-8)",
    9: "Secondary (9-10)", 10: "Secondary (9-10)",
    11: "Higher Secondary (11-12)", 12: "Higher Secondary (11-12)",
}

_UNKNOWN_VALUES = {"", "unknown", "none", "null", "nan"}


def _normalise(val: str, default: str = "not mentioned") -> str:
    v = str(val or "").lower().strip()
    return default if v in _UNKNOWN_VALUES else v


# ── S3 helpers ────────────────────────────────────────────────────────────────
def _s3():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        verify=False,
    )


def _load_page_cache() -> dict:
    try:
        if PAGE_CACHE_FILE.exists():
            return json.loads(PAGE_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_page_cache(cache: dict):
    try:
        PAGE_CACHE_FILE.write_text(json.dumps(cache))
    except Exception as e:
        log.warning(f"Could not save page cache: {e}")


def _count_pdf_pages(s3_client, key: str, size_bytes: int, cache: dict) -> int:
    """Download PDF and count pages; cache result.  Falls back to size estimate."""
    if key in cache:
        return cache[key]
    try:
        body = s3_client.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()
        n = len(pypdf.PdfReader(io.BytesIO(body)).pages)
        log.debug(f"Counted {n} pages for {key.split('/')[-1]}")
    except Exception as e:
        log.warning(f"Could not count pages for {key}: {e} — estimating from size")
        n = max(1, round(size_bytes / 600_000))
    cache[key] = n
    return n


# ── Main fetch ────────────────────────────────────────────────────────────────
def fetch() -> pd.DataFrame:
    s3 = _s3()
    page_cache = _load_page_cache()
    cache_dirty = False

    log.info("Listing bucket objects…")
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

    log.info(f"Found {len(json_keys)} records, {len(pdf_sizes)} PDFs")

    rows = []
    new_pdfs = [k[:-5] + ".pdf" for k in json_keys if (k[:-5] + ".pdf") not in page_cache]
    if new_pdfs:
        log.info(f"Downloading {len(new_pdfs)} new PDFs to count pages…")

    for i, key in enumerate(json_keys, 1):
        try:
            meta = json.loads(
                s3.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()
            )
        except Exception as e:
            log.warning(f"Skipping {key}: {e}")
            continue

        pdf_key  = key[:-5] + ".pdf"
        pdf_size = pdf_sizes.get(pdf_key, 0)
        if pdf_key not in page_cache:
            cache_dirty = True
        num_pages = _count_pdf_pages(s3, pdf_key, pdf_size, page_cache)

        if i % 50 == 0:
            log.info(f"  Processed {i}/{len(json_keys)} records…")

        grade     = meta.get("grade")
        state_raw = str(meta.get("state") or "").lower().strip()
        lang_prim = str(meta.get("language_primary") or "").strip().title()

        rows.append({
            "pdf_key":               pdf_key,
            "student_name":          str(meta.get("student_name") or "not mentioned").strip(),
            "student_id":            str(meta.get("student_id")   or ""),
            "unique_file_id":        str(meta.get("unique_file_id") or ""),
            "school_id":             str(meta.get("school_id")    or ""),
            "gender":                _normalise(meta.get("gender")),
            "class":                 int(grade) if grade else None,
            "class_level":           CLASS_LEVEL_FROM_GRADE.get(int(grade), "Unknown") if grade else "Unknown",
            "school_name":           str(meta.get("school_name")   or "").strip(),
            "school_type":           str(meta.get("school_type")   or "").strip(),
            "board":                 _normalise(meta.get("board")),
            "block":                 _normalise(meta.get("city_town_village")),
            "district":              str(meta.get("district")      or "").strip().title(),
            "state":                 state_raw.replace("_", " ").title() or "Unknown",
            "regional_language":     lang_prim or STATE_TO_LANGUAGE.get(state_raw, "Unknown"),
            "medium_of_instruction": str(meta.get("medium_of_instruction") or "not mentioned").strip().title(),
            "subject":               str(meta.get("subject") or "").lower().strip(),
            "sample_type":           str(meta.get("source_type") or "").lower().strip(),
            "num_pages":             num_pages,
            "date":                  pd.to_datetime(meta.get("uploaded_at"), errors="coerce", utc=True),
            "distributor":           str(meta.get("school_name") or "unknown").strip(),
            "rural_urban":           str(meta.get("rural_urban") or "").strip().title(),
            "aspirational_district": meta.get("aspirational_district", False),
            "curriculum_type":       str(meta.get("curriculum_type") or "").strip(),
            "performance_group":     str(meta.get("performance_group") or "").strip() or "Not Mentioned",
            "capture_device":        str(meta.get("capture_device") or "").strip(),
            "orientation":           str(meta.get("orientation") or "").strip(),
            "handedness":            _normalise(meta.get("handedness")),
        })

    if cache_dirty:
        _save_page_cache(page_cache)
        log.info("Page cache updated.")

    if not rows:
        log.warning("No records loaded from bucket.")
        return pd.DataFrame()

    data = pd.DataFrame(rows)

    # ── Normalise ──────────────────────────────────────────────────────────────
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
    data["distributor"]     = data["school_name"]
    data["subject_category"] = data["subject"].map(SUBJ_CAT_MAP).fillna("Other")

    return data


def main():
    log.info("=== fetch_data.py starting ===")
    try:
        df = fetch()
        if df.empty:
            log.error("Empty DataFrame — aborting write.")
            sys.exit(1)

        # Write atomically: write to tmp then rename
        tmp = CACHE_PARQUET.with_suffix(".tmp.parquet")
        df.to_parquet(tmp, index=False)
        tmp.rename(CACHE_PARQUET)

        meta = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "records": len(df),
            "students": int(df["student_id"].nunique()),
            "pages": int(df["num_pages"].sum()),
        }
        LAST_UPDATED.write_text(json.dumps(meta, indent=2))
        log.info(f"Saved {len(df)} records → {CACHE_PARQUET}")
        log.info(f"  {meta['students']} unique students, {meta['pages']:,} total pages")

    except Exception as e:
        log.exception(f"fetch_data.py failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
