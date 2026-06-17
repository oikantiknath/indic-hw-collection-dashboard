# Indic Handwriting Collection Dashboard (OCR-VS)

A Streamlit-based monitoring dashboard for tracking the progress of Indic handwriting data collection across schools, validating against strict Phase 1 compliance targets.

---

## Quick Start

1. Install dependencies:
   ```bash
   pip install streamlit pandas numpy plotly openpyxl boto3 botocore pypdf pymupdf python-dotenv
   ```

2. Set up a `.env` file with the required environment variables (see [Configuration](#configuration)).

3. Place `targets.json` in the root directory with Phase 1 target values.

4. Run the dashboard:
   ```bash
   streamlit run app.py
   ```

---

## Configuration

**Environment variables:**

| Variable | Description |
|---|---|
| `APPROVED_CSV_PATH` | Path to `approved_uploads.csv` (approved student upload records) |
| `ANNOTATION_DB_PATH` | Path to `annotation.db` (SQLite quality review database) |
| `MINIO_BUCKET` | MinIO/S3 bucket name (set in `s3_helpers.py`) |
| `MINIO_PREFIX` | MinIO/S3 key prefix for PDFs |

**Config files:**

| File | Description |
|---|---|
| `targets.json` | Phase 1 targets: `phase1_total_pages`, `per_language_pages`, `pg_per_participant`, `language_participants` |
| `data_cache.parquet` | Pre-built data cache (refreshed every 6h by cron job; preferred over live bucket load) |
| `.last_updated.json` | Timestamp of last parquet cache refresh |
| `annotation.db` | SQLite DB with quality review decisions and page-level issue flags (not committed) |

---

## Data Sources

- **`approved_uploads.csv`** — All approved student upload records with full metadata (state, district, block, school, class, subject, gender, pages, board, etc.).
- **`annotation.db`** — SQLite database with quality review decisions (`pdf_annotations` table: `unique_file_id`, `pdf_decision`, `page_rejections`, `reviewer`, `created_at`).
- **MinIO/S3** — PDFs stored at `{prefix}{state}/{district}/{block}/{board}/{curriculum}/{school}/{medium}/{class_level}/{subject}/{sample_type}/{uid}/{uid}.pdf`. Presigned URLs generated for in-browser viewing (1800s expiry).
- **`targets.json`** — Phase 1 goals and per-language/per-class-level participant targets.

---

## Features

### Sidebar Filters

- **Board**, **Class Level**, **Subject Category**, **Gender**, **Language**, **State**, **Block**, **School**
- **Date Range** (From / To pickers, defaults to data min/max)
- **Refresh** button (clears cache and reloads)
- **Recount Pages** button (forces exact PDF page count from S3)
- Data source indicator: "Cache (updated HH:MM)" or "Live bucket (no cache yet)"

---

### Main Dashboard

**Hero metrics** (top strip):
- Total Pages, Student Count, School Count, State Count

**Phase 1 Progress Bar:**
- 3-segment stacked bar — Accepted % | Rejected % | Pending %
- Days remaining to deadline (5 Jul 2026), color-coded: red ≤14 days, amber ≤30, green otherwise

**KPI Cards** (7-column grid):
- States, Districts, Blocks, Records, Subjects, Pages/Record, Subjects/Student

**Collection | Quality Analysis split** (left/right panels):

*Collection panel:*
- States card (count + pages-per-state bar chart + drill-down)
- Languages card (count + pages-per-language bar chart + drill-down)
- Students card (count + pages-by-class bar chart + drill-down)
- Subjects card (count + pages-by-subject bar chart + drill-down)

*Quality Analysis panel:*
- KPI strip: Total Pages | Completed (reviewed) | Pending
- Reviewed breakdown bar: Clean + Accepted w/ Issues + Rejected
- **Top Issue Types** bar chart — bars colored per issue category
- Quick-filter buttons: ✓ Accepted (N) | ✗ Rejected (N) | ⚠ Flagged (N) — each opens Sample Checker with the corresponding quality preset

---

### Sample Checker (PDF Viewer)

Opened via the top-right **Sample Checker** button. Renders as a full-page overlay (`st.dialog`).

**Filters** (independent of sidebar):
- Distributor, State, District, Block/City/Village, School, Gender, Subject, Class, Date Range, Student Name
- **Quality Status**: All / Pending / Clean / Accepted w/ Issues / Rejected (VS) / Rejected (Bodhan)

**Sample table:**
- Columns: # | Student ID | Class | Subject | Pages | Quality Status | Issues | Date | View
- Inline issue badges with counts; status badges color-coded
- 10 records per page with Prev / Next pagination

**PDF Viewer dialog** (opened on View button):
- Header: Quality Status badge | Student ID | Class | Subject | Pages | School | District
- Issue chips: colored per issue type with count
- **Flagged page buttons** (max 12 per row) — color-coded per issue type
- Selected page rendered as JPEG (1.5× zoom, quality 82)
- View Full PDF toggle (iframe embed via presigned MinIO URL)
- Prev / Next navigation (Page X of Y)

**Issue types tracked:** `reject_bleed_through`, `reject_blur`, `reject_lighting`, `reject_sparsity`, `reject_rotation_mismatch`, `reject_subject_content_mismatch`, `reject_source_type_mismatch`, `reject_cutoff`, `pii_flag`

**Quality status labels:** Pending | Clean | Accepted w/ Issues | Rejected (unified label for both VS and Bodhan rejections)

---

### Detailed Language View

Accessed via language drill-down. Tabs per language + "India Overall".

- Overall page collection progress bar (vs. per-language target)
- Class-level pages vs. target (4 progress bars: Primary, High School, Secondary, Higher Secondary)
- Participant targets (4 progress bars)

**Demographics** (8 pie charts, 2 rows):
- Row 1: Class Level | Gender | Medium of Instruction | Sample Type
- Row 2: Board | State | Rural/Urban (≥50% indicator) | School Type (≥60% govt indicator)

**Avg Pages per Participant** (4 cards, one per class level):
- Actual vs. target (50 pages/student), Pass/Fail badge

**Compliance Summary Grid** (~14 checks, 2-column layout):
- Pages, gender %, regional medium %, avg pages per level, govt %, rural %, aspirational districts %, left-handed %, school-class combos meeting ≥25 students

**Subject Coverage** (per class level):
- Coverage of 5 core subjects per level, Pass/Fail for "30% with all 5 core subjects"

---

### State / District / Block Analysis

**State Level:**
- Pages by State, Students by State, Schools by State, Districts by State (bar charts, 2-column grid)
- Treemap: State → District → Block
- State-wise progress cards (10 states, each with progress bar + pages/target)

**District Level:**
- KPI strip: Districts, Pages, Students, Top District
- Pages / Students / Schools / Blocks by District (bar charts)
- Avg Pages/Student by District (horizontal bar, green/red by target)
- School Type mix, Rural/Urban mix, Board mix (stacked bar charts)
- Treemap: District → Block
- Statistics table (expandable)

**Block Level:**
- Pages by Block, Students & Schools per Block (grouped bar)
- Treemap: Block → School → Pages
- Statistics table (expandable)

---

### Class, Subject & Student Analysis

**Class & Subject Analysis** (3 tabs):
- *By Class*: Total Pages by Class + Unique Students by Class
- *By Subject*: Pages by Subject (horizontal bar) + Subject Category pie
- *Heatmap*: Class Level × Subject Category

**Subject & Gender Coverage** (by class level):
- Gender × Class Level pages bar (grouped)
- Subject breakdown table per level (% and Pass/Fail vs. target)

**Student Multi-Subject Coverage:**
- Subjects per Student distribution (bar)
- Coverage breadth pie: 1 subject only | 2-3 subjects | 4+ subjects

**Pages per Record Distribution:**
- Box plots by Class Level and Subject Category

**Content Quality** (4 pie charts):
- Handwritten/Drawn | Printed Content | Mixed Content | Page Rotation

---

### Distributor & Timeline Analysis

**Distributor Stats:**
- KPI row: Distributors, Total Pages, Students, Avg Pages/Student
- Pages / Students / Schools / Districts by Distributor
- Avg Pages/Student by Distributor (horizontal bar)
- Statistics table

**Upload Timeline:**
- Daily Uploads & Pages (bar + line dual-axis)
- Review turnaround KPIs: Median, Mean, Fastest, Slowest hours
- Turnaround distribution histogram

**Place Analysis:** Top 20 cities/towns/villages by upload count

**Metadata Flags:** Generate Metadata pie | Data Bucket Flag pie

---

## Compliance Targets

| Metric | Target |
|---|---|
| Total Pages | ≥ Phase 1 milestone (2,000,000) |
| Female Participants | ≥ 45% |
| Male Participants | ≥ 45% |
| Government Schools | ≥ 60% |
| Rural Participants | ≥ 50% |
| Regional Medium of Instruction | ≥ 50% |
| Aspirational Districts | ≥ 15% (of records from aspirational-district states) |
| Left-handed Participants | ≥ 5% |
| Min Students per Class per School | ≥ 25 |
| Students with all 5 core subjects | ≥ 30% |

**Phase 1 State targets (200,000 pages each):** Tamil Nadu, AP & Telangana, Uttar Pradesh, Karnataka, Maharashtra, Odisha, Kerala, West Bengal, Gujarat, Punjab

---

## Technical Notes

- **Caching:** `@st.cache_data(ttl=300)` for annotation DB and bucket data; `@st.cache_data(ttl=1800)` for PDF page renders and presigned URLs.
- **Parallel PDF rendering:** All flagged pages for a PDF are rendered concurrently via `ThreadPoolExecutor` (8 workers). Pages are encoded as JPEG at 1.5× zoom, quality 82 (~5× smaller and faster than PNG).
- **Dark / Light theme toggle:** Fixed button top-right, defaults to dark. Entire color palette (16+ tokens) switches dynamically; all charts respect the active theme.
- **Deep links:** Quality Analysis buttons (Accepted / Rejected / Flagged) open Sample Checker with a pre-set quality status filter via session state (`sc_quality_preset`).
- **Data normalization:** Subject, board, gender, block, school names, and class levels are normalized via mapping tables in `mappings.py`.
- **Compliance penalties:** Any field marked "Not Mentioned" is counted as a failure against the relevant compliance target.
- **Conditional display:** Aspirational Districts and Min Students per Class per School sections are hidden when no qualifying data exists.

---

## Project Structure

```
app.py               # Main dashboard application
chart_helpers.py     # Chart layout, color constants, HTML progress bar helpers
s3_helpers.py        # MinIO/S3 client, presigned URLs, page cache utilities
mappings.py          # Normalization maps (state/language/subject/board/block/school)
fetch_data.py        # Data fetching utilities
field_schema.json    # Field schema definitions
targets.json         # Phase 1 compliance target configuration
annotation.db        # SQLite quality review DB — not committed
data_cache.parquet   # Pre-built data cache — not committed
```
