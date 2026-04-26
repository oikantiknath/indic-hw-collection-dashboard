# Indic Handwriting Collection Dashboard (OCR-VS)

Access the live dashboard here: https://untold-displace-proton.ngrok-free.dev/

This is a Streamlit-based monitoring dashboard specifically designed to track the progress of Indic handwriting data collection across schools, validating against strict compliance targets. 

## Key Features

*   **Real-time Target Tracking:** Analyzes metrics to ensure the dataset accurately follows predefined distribution requirements (e.g., Phase 1 milestone aiming for 2.5 Crore pages).
*   **Language-Specific Groupings:** Automatically segments data into language-specific tabs based on district regions (Tamil, Telugu, Hindi, etc.) for targeted compliance scaling.
*   **Regional Medium Validation:** Strictly validates that the student's reported medium of instruction matches the active region/tab (e.g. `Hindi == Hindi`). Blank (`Not Mentioned`) values are treated as failures to enforce data hygiene.
*   **Detailed Demographics Breakdown:** Comprehensive breakdowns of collection rates visually grouped by class level, board, and gender.
*   **Subject Coverage:** Dynamically ensures sufficient distribution across multi-subject criteria.
*   **Compliance Target Bars:** Consistent segmented HTML bars (School Type, Rural/Urban, Left-handedness, Regional Medium) with dashed target lines and color-coded legends.
*   **Aspirational Districts:** Tracks the percentage of records from aspirational-district states, shown only when relevant data is present.
*   **Left-handedness Tracking:** Monitors left-handed participant ratio (target ≥5%) using the same bar format as other demographic metrics.
*   **Min Students per Class per School:** Validates that school-class combinations meet the minimum student threshold (≥25); only displayed when at least one combo meets the target.
*   **Sample Checker — PDF Viewer:** A toggleable panel (top-right button) that lets reviewers browse and view individual collected PDFs directly from S3/MinIO storage. Supports filtering by distributor, state, district, block, school, gender, and more, with inline PDF rendering via pre-signed URLs.

## Quick Start

1. Install required dependencies:
   ```bash
   pip install streamlit pandas plotly openpyxl
   ```

2. Place the raw data excel file (`Details of collected data.xlsx`) in the root directory.

3. Run the dashboard:
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

## Workflow & Logic Enhancements

*   **Accurate Metrics:** The tool reads exact page counts rather than assuming files are equivalent to PDFs.
*   **Compliance Penalties:** Any collection marked as "Not Mentioned" is recorded as a failure against target goals to ensure field vendors enforce data entry.
*   **Conditional Display:** Sections like Aspirational Districts and Min Students per Class per School are hidden when no qualifying data exists, keeping the dashboard clean.
