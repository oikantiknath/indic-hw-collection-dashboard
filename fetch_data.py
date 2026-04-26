#!/usr/bin/env python3
"""
fetch_data.py — run by cron every 6 hours.

Fetches all student JSON metadata from MinIO, counts PDF pages (with a
persistent local cache so each PDF is only downloaded once), normalises
fields exactly as app.py does, and writes the result to data_cache.parquet.
The Streamlit app reads that file; if it is missing it falls back to a live
bucket load.
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
from s3_helpers import (
    _s3, load_page_cache, save_page_cache, count_pdf_pages,
    MINIO_BUCKET, MINIO_PREFIX,
)

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR        = Path(__file__).parent
CACHE_PARQUET   = BASE_DIR / "data_cache.parquet"
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

_UNKNOWN_VALUES = {"", "unknown", "none", "null", "nan"}


def _normalise(val: str, default: str = "not mentioned") -> str:
    v = str(val or "").lower().strip()
    return default if v in _UNKNOWN_VALUES else v


# ── Main fetch ────────────────────────────────────────────────────────────────
def fetch() -> pd.DataFrame:
    s3 = _s3()
    page_cache = load_page_cache()
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
        num_pages = count_pdf_pages(s3, pdf_key, pdf_size, page_cache, exact=True)

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
            "distributor":           (lambda v: v.split("@")[0].strip() if "@" in v else v)(str(meta.get("distributor") or meta.get("uploaded_by") or meta.get("collector_name") or meta.get("data_collector") or "Not Mentioned").strip()),
            "rural_urban":           str(meta.get("rural_urban") or "").strip().title(),
            "aspirational_district": meta.get("aspirational_district", False),
            "curriculum_type":       str(meta.get("curriculum_type") or "").strip(),
            "performance_group":     str(meta.get("performance_group") or "").strip() or "Not Mentioned",
            "capture_device":        str(meta.get("capture_device") or "").strip(),
            "orientation":           str(meta.get("orientation") or "").strip(),
            "handedness":            _normalise(meta.get("handedness")),
            "handwritten_or_handdrawn": str(meta.get("handwritten_or_handdrawn") or "").lower().strip(),
            "printed":               str(meta.get("printed")       or "").lower().strip(),
            "mixed_content":         str(meta.get("mixed_content")  or "").lower().strip(),
            "rotation":              str(meta.get("rotation")       or "").lower().strip(),
        })

    if cache_dirty:
        save_page_cache(page_cache)
        log.info("Page cache updated.")

    if not rows:
        log.warning("No records loaded from bucket.")
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
