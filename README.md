# Indic Handwriting Collection Dashboard (OCR-VS)

A Streamlit-based monitoring dashboard for tracking the progress of Indic handwriting data collection across schools, validating against strict compliance targets.

## Key Features

*   **Real-time Target Tracking:** Analyzes metrics to ensure the dataset follows predefined distribution requirements (Phase 1 milestone: 2.5 Crore pages).
*   **Language-Specific Tabs:** Automatically segments data by district region (Tamil, Telugu, Hindi, etc.) for targeted compliance tracking.
*   **Regional Medium Validation:** Validates that the student's medium of instruction matches the active region. Blank (`Not Mentioned`) values are treated as failures.
*   **Demographics Breakdown:** Breakdowns of collection rates by class level, board, and gender.
*   **Subject Coverage:** Ensures sufficient distribution across multi-subject criteria.
*   **Compliance Target Bars:** Segmented HTML bars (School Type, Rural/Urban, Left-handedness, Regional Medium) with dashed target lines and color-coded legends.
*   **Aspirational Districts:** Tracks the percentage of records from aspirational-district states (shown only when relevant data is present).
*   **Left-handedness Tracking:** Monitors left-handed participant ratio (target ≥5%).
*   **Min Students per Class per School:** Validates that school-class combinations meet the minimum student threshold (≥25).
*   **Quality Analysis Panel:** Side-by-side collection vs. quality view per language tab, showing accepted/rejected/pending counts, Top Issue Types bar chart (bars colored per issue type), and deeplink filtering into the Sample Checker.
*   **Sample Checker — PDF Viewer:** Overlay dialog (`st.dialog`) for browsing and reviewing individual collected PDFs directly from S3/MinIO. Supports filtering by distributor, state, district, block, school, gender, and quality status. Flagged page buttons are color-coded per issue type. All "Rejected (VS)" / "Rejected (Bodhan)" labels are unified to "Rejected".
*   **Parallel PDF Caching:** All flagged pages for a PDF are pre-cached in parallel via `ThreadPoolExecutor` (8 workers). Pages are rendered as JPEG at 1.5× zoom (~5× faster than PNG).
*   **Annotation DB Integration:** Review decisions and page-level issues are read from a local SQLite `annotation.db` (via `load_annotation_data` / `load_qa_counts`).
*   **Dark / Light Theme Toggle:** Fixed toggle button in the top-right corner; defaults to dark mode.

## Quick Start

1. Install dependencies:
   ```bash
   pip install streamlit pandas plotly openpyxl boto3 pypdf pymupdf python-dotenv
   ```

2. Place the raw data Excel file (`Details of collected data.xlsx`) in the root directory.

3. Set up a `.env` file with your MinIO/S3 credentials (see `s3_helpers.py` for required vars).

4. Run the dashboard:
   ```bash
   streamlit run app.py
   ```

## Compliance Targets

| Metric | Target |
|---|---|
| Total Pages | ≥ Phase 1 milestone |
| Female Participants | ≥ 45% |
| Male Participants | ≥ 45% |
| Government Schools | ≥ 60% |
| Rural Participants | ≥ 50% |
| Regional Medium of Instruction | ≥ 50% |
| Aspirational Districts | ≥ 15% (of records from aspirational-district states) |
| Left-handed Participants | ≥ 5% |
| Min Students per Class per School | ≥ 25 |

## Project Structure

```
app.py               # Main dashboard application
chart_helpers.py     # Chart layout, color constants, HTML helpers
s3_helpers.py        # MinIO/S3 client, presigned URLs, page cache
mappings.py          # State/language/subject/board normalization maps
fetch_data.py        # Data fetching utilities
field_schema.json    # Field schema definitions
targets.json         # Compliance target configuration
annotation.db        # Local SQLite DB for review decisions (not committed)
```

## Workflow & Logic Notes

*   **Accurate Page Counts:** Reads exact page counts from PDFs rather than assuming file count = page count.
*   **Compliance Penalties:** Any collection marked "Not Mentioned" is recorded as a failure to enforce data hygiene.
*   **Conditional Display:** Sections like Aspirational Districts and Min Students per Class per School are hidden when no qualifying data exists.
*   **Caching:** Dashboard data is cached with `@st.cache_data` (30-min TTL for S3 renders, 5-min TTL for annotation DB reads).
