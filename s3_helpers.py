"""S3 / MinIO helpers: client, presigned URLs, page count cache."""

import io
import json
import os
from pathlib import Path

import boto3
import pypdf
import urllib3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET")
MINIO_PREFIX     = os.getenv("MINIO_PREFIX")

PAGE_CACHE_FILE = Path(__file__).parent / ".page_count_cache.json"


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        verify=False,
    )


def presigned_url(key: str, expires: int = 3600) -> tuple[str, str, str]:
    """Return (url, error, found_ext). url is empty on failure."""
    try:
        s3 = _s3()
        try:
            s3.head_object(Bucket=MINIO_BUCKET, Key=key)
        except Exception:
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


def load_page_cache() -> dict:
    try:
        if PAGE_CACHE_FILE.exists():
            return json.loads(PAGE_CACHE_FILE.read_text())
    except Exception:
        pass
    return {}


def save_page_cache(cache: dict):
    try:
        PAGE_CACHE_FILE.write_text(json.dumps(cache))
    except Exception:
        pass


def count_pdf_pages(s3_client, key: str, size_bytes: int, cache: dict, exact: bool = False) -> int:
    if key in cache:
        return cache[key]
    if not exact:
        return max(1, round(size_bytes / 600_000))
    try:
        body = s3_client.get_object(Bucket=MINIO_BUCKET, Key=key)["Body"].read()
        n = len(pypdf.PdfReader(io.BytesIO(body)).pages)
    except Exception:
        n = max(1, round(size_bytes / 600_000))
    cache[key] = n
    return n
