#!/usr/bin/env python3
"""
fetch_data.py — run by cron every 6 hours.

Reads approved_uploads.csv (the approved set), normalises fields exactly as
app.py does, and writes the result to data_cache.parquet.
The Streamlit app reads that file; if it is missing it falls back to a live load.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import urllib3
from dotenv import load_dotenv

from mappings import (
    STATE_TO_LANGUAGE, CLASS_LEVEL_FROM_GRADE,
    SUBJECT_MAP, SAMPLE_TYPE_MAP, GENDER_MAP, BOARD_MAP,
    BLOCK_MAP, SCHOOL_NORMALIZATIONS, SUBJ_CAT_MAP, fuzzy_subject,
)
from s3_helpers import MINIO_PREFIX

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import os

BASE_DIR        = Path(__file__).parent
CACHE_PARQUET   = BASE_DIR / "data_cache.parquet"
LAST_UPDATED    = BASE_DIR / ".last_updated.json"
APPROVED_CSV    = Path(os.environ.get("APPROVED_CSV_PATH", str(BASE_DIR / "approved_uploads.csv")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "fetch_data.log"),
    ],
)
log = logging.getLogger(__name__)

_UNKNOWN_VALUES = {"", "unknown", "none", "null", "nan"}


def _normalise(val, default: str = "not mentioned") -> str:
    v = str(val or "").lower().strip()
    return default if v in _UNKNOWN_VALUES else v


def _grade_num(val):
    try:
        return int(str(val).replace("Grade", "").strip())
    except Exception:
        return None


# ── Main fetch ────────────────────────────────────────────────────────────────
def fetch() -> pd.DataFrame:
    log.info(f"Reading approved CSV: {APPROVED_CSV}")
    raw = pd.read_csv(APPROVED_CSV)
    log.info(f"Loaded {len(raw)} approved records")

    rows = []
    for i, r in raw.iterrows():
        grade     = _grade_num(r.get("classGrade"))
        state_raw = str(r.get("state") or "").lower().strip().replace(" ", "_")
        medium    = str(r.get("medium") or "not mentioned").strip().title()
        distributor_raw = str(r.get("uploadedByUserId") or "Not Mentioned").strip()
        distributor = distributor_raw.split("@")[0].strip() if "@" in distributor_raw else distributor_raw

        rows.append({
            "pdf_key":                  MINIO_PREFIX + str(r.get("s3Key") or ""),
            "student_name":             "not mentioned",
            "student_id":               str(r.get("studentId") or ""),
            "unique_file_id":           str(r.get("id") or ""),
            "school_id":                str(r.get("schoolId") or ""),
            "gender":                   _normalise(r.get("gender")),
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
            "distributor":              distributor,
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
            "reject_stage":             "null",
            "review_flag":              "stage_vs",
            "place":                    str(r.get("place") or "").strip().title(),
            "file_number":              int(r.get("fileNumber") or 0),
            "reviewed_at":              pd.to_datetime(r.get("reviewedAt"), errors="coerce", utc=True),
            "generate_metadata":        bool(r.get("generateMetadata", False)),
            "data_bucket":              bool(r.get("data_bucket", False)),
        })

        if (i + 1) % 500 == 0:
            log.info(f"  Processed {i + 1}/{len(raw)} records…")

    if not rows:
        log.warning("No records loaded.")
        return pd.DataFrame()

    data = pd.DataFrame(rows)

    # ── Normalise ──────────────────────────────────────────────────────────────
    def _map_subject(raw: str) -> str:
        mapped = SUBJECT_MAP.get(str(raw).lower().strip())
        if mapped:
            return mapped
        fuzzy = fuzzy_subject(str(raw).replace("_", " "))
        return fuzzy if fuzzy else "Other"

    data["subject"] = data["subject"].apply(_map_subject)
    data["gender"] = data["gender"].map(GENDER_MAP).fillna("Not Mentioned")
    _b = data["board"].str.lower().str.strip()
    data["board"] = (
        data["board"].map(BOARD_MAP)
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
