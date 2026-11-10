# FortyGuard Environmental Intelligence & Analytics Platform

An enterprise-grade Python, Data Engineering, and Streamlit analytics application that connects to the **FortyGuard Enterprise REST API (v1)**. The platform retrieves, structures, stores, cleans, analyzes, and visualizes urban microclimate, thermal stress, air quality, solar irradiance, and spatial intelligence data for supported United States locations.

---

## 🌟 Executive Summary & Features

- **Centralized REST API Client (`src/api/fortyguard_client.py`)**:
  - Secure header-based authentication (`api-key: YOUR_KEY`) using `python-dotenv`.
  - Configurable timeouts, exponential backoff retries for transient 5xx/connection drops.
  - Asynchronous task polling (`GET /v1/status/{activity_id}`) with bounded timeouts and progress callbacks.
  - Sanitized logging: Credentials are never leaked in terminal logs or exported data.
- **Relational Data Storage (`src/database/`)**:
  - Thread-safe SQLite persistence (`data/fortyguard.db`) with foreign key constraints, indexes, and full relational tables for locations, collection jobs, observations, heatmaps, reports, segmentations, and routing.
  - Local caching layer preventing duplicate paid API requests for identical location/time queries.
- **Data Engineering & Auditing (`src/processing/cleaning.py`)**:
  - Non-destructive data cleaning preserving raw API fidelity.
  - Missingness analysis per column and Interquartile Range (IQR) outlier detection.
- **Advanced Environmental Analytics (`src/analytics/analysis.py`)**:
  - Descriptive statistics (mean, median, IQR, skewness, kurtosis).
  - Pairwise correlation matrices (Pearson/Spearman).
  - Derived thermal indicators: Thermal Delta ($\text{Apparent} - \text{Reference}$), NOAA Heat Index hazard categories, Wet-Bulb stress tiers, and US EPA AQI health classification.
- **Interactive Multi-Page Streamlit Dashboard (`app.py` & `dashboard/`)**:
  - **Page 1: Overview** — Consolidated KPIs, US interactive coverage scatter map, recent telemetry.
  - **Page 2: Data Collection** — Preset US locations + custom coordinates, credit awareness guards, real-time polling progress bar.
  - **Page 3: Environmental Analytics** — Plotly comparative bar charts, atmospheric metrics, AQI pollutant breakdowns, clear-sky solar irradiance, and correlation matrices.
  - **Page 4: Location Comparison** — Side-by-side benchmarking, ranking tables, and radar profiles.
  - **Page 5: Heat Intelligence & Heatmaps** — GeoJSON polygon submission, 77-tile Phoenix heat grid visualization, and temporary signed PDF report download handling.
  - **Page 6: Satellite & Street View** — Land cover decomposition and ground-level canyon composition.
  - **Page 7: Temperature-Aware Routing** — Origin/destination coordinate input, 200 km distance validation, and thermal vs duration route tradeoffs.
  - **Page 8: Dataset Explorer & Exporter** — Interactive filtering, raw vs cleaned view toggles, and direct CSV, JSON, and 6-sheet Excel downloads.
- **Multi-Format Data Exporter (`src/exports/export.py`)**:
  - One-click export to CSV, JSON, and multi-sheet Microsoft Excel (`.xlsx`) workbooks containing:
    1. Environmental Observations
    2. Locations
    3. Collection Summary
    4. Heatmap Results
    5. Reports
    6. Data Quality Summary

---

## 🏗️ Architecture & Project Structure

```
FortyGuard-Environmental-Analytics/
│
├── app.py                     # Main Streamlit dashboard orchestrator
├── requirements.txt           # Project dependencies
├── .env                       # Local private API key (never committed)
├── .env.example               # Template configuration file
├── .gitignore                 # Excludes secrets, cache, and db files
├── README.md                  # Comprehensive platform documentation
│
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── fortyguard_client.py  # Enterprise FortyGuard REST client
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.py             # DDL statements, indexes, tables
│   │   └── db.py                 # SQLite CRUD, caching, and ORM helpers
│   ├── collection/
│   │   ├── __init__.py
│   │   └── collector.py          # Collection workflow & US validation
│   ├── processing/
│   │   ├── __init__.py
│   │   └── cleaning.py           # Deduplication, missingness, and IQR
│   ├── analytics/
│   │   ├── __init__.py
│   │   └── analysis.py           # Statistical metrics & thermal indices
│   └── exports/
│       ├── __init__.py
│       └── export.py             # CSV, JSON, and Multi-Sheet Excel
│
├── dashboard/
│   ├── __init__.py
│   ├── overview.py               # Overview & KPIs
│   ├── collection.py             # Interactive API collection page
│   ├── environmental.py          # Charts for heat, humidity, AQI, solar
│   ├── locations.py              # Benchmarking & radar profiles
│   ├── heat_intelligence.py      # Heatmaps & intelligence reports
│   ├── segmentation.py           # Satellite & street-view segmentation
│   ├── routing.py                # Temperature-aware route alternatives
│   └── explorer.py               # Data explorer and direct downloads
│
├── data/
│   ├── fortyguard.db             # Local SQLite database (live data)
│   ├── raw/                      # Raw response store
│   ├── processed/                # Cleaned cache files
│   └── exports/
│       └── fortyguard_environmental_analytics.xlsx # Example multi-sheet export
│
├── tests/
│   ├── __init__.py
│   ├── test_client.py            # API client and mock polling tests
│   ├── test_database.py          # Database schema and query tests
│   ├── test_cleaning_analytics.py# Cleaning and statistical tests
│   └── test_exports.py           # CSV and Excel export tests
│
└── notebooks/
    └── environmental_intelligence_demo.ipynb # Jupyter exploratory notebook
```

---

## 🛠️ Installation & Setup (Windows PowerShell)

### 1. Prerequisites
Ensure you have **Python 3.10+** installed on your system.

### 2. Clone / Open Workspace
Open Windows PowerShell in the project directory:
```powershell
cd C:\Users\shahz\OneDrive\Desktop\fortyguard
```

### 3. Create and Activate a Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Configure Your API Key
A `.env` file has been provided in the project root. If you need to reconfigure it, copy `.env.example`:
```powershell
Copy-Item .env.example .env
```
Open `.env` and set your FortyGuard API key:
```ini
FORTYGUARD_API_KEY=your_actual_api_key_here
FORTYGUARD_BASE_URL=https://api.fortyguard.com/v1
DATABASE_PATH=data/fortyguard.db
LOG_LEVEL=INFO
```
*(Never commit `.env` to Git. The `.gitignore` is already pre-configured to exclude it.)*

---

## 🚀 Running the Application

Launch the Streamlit web dashboard using:
```powershell
streamlit run app.py
```
Streamlit will launch locally in your web browser at:
👉 **`http://localhost:8501`**

---

## 🧪 Running Automated Unit & Integration Tests

All tests utilize mocked responses for API requests so that **no API credits are consumed** during testing.

Run the complete test suite with verbose output:
```powershell
pytest -v
```

Expected result:
```
tests/test_cleaning_analytics.py::test_data_cleaner_audit PASSED         [  5%]
tests/test_cleaning_analytics.py::test_outlier_detection PASSED          [ 10%]
tests/test_cleaning_analytics.py::test_descriptive_stats PASSED          [ 15%]
tests/test_cleaning_analytics.py::test_correlation_matrix PASSED         [ 20%]
tests/test_cleaning_analytics.py::test_location_comparison PASSED        [ 25%]
tests/test_cleaning_analytics.py::test_thermal_stress_enrichment PASSED  [ 30%]
tests/test_client.py::test_missing_api_key_raises_error PASSED           [ 35%]
tests/test_client.py::test_client_header_initialization PASSED           [ 40%]
tests/test_client.py::test_successful_env_params PASSED                  [ 45%]
tests/test_client.py::test_authentication_failure_401 PASSED             [ 50%]
tests/test_client.py::test_out_of_coverage_400 PASSED                    [ 55%]
tests/test_client.py::test_validation_error_422 PASSED                   [ 60%]
tests/test_client.py::test_rate_limit_error_429 PASSED                   [ 65%]
tests/test_client.py::test_poll_activity_success PASSED                  [ 70%]
tests/test_client.py::test_poll_activity_timeout PASSED                  [ 75%]
tests/test_database.py::test_upsert_and_get_location PASSED              [ 80%]
tests/test_database.py::test_insert_environmental_observations PASSED    [ 85%]
tests/test_database.py::test_platform_overview_metrics PASSED            [ 90%]
tests/test_exports.py::test_csv_and_json_exports PASSED                  [ 95%]
tests/test_exports.py::test_excel_multisheet_export PASSED               [100%]

============================= 20 passed in 4.25s ==============================
```

---

## 📊 Exporting Datasets

You can export datasets in two ways:
1. **Via Dashboard**: Navigate to **Page 8: Dataset Explorer & Exporter** and click:
   - `📄 Download CSV`
   - `🌐 Download JSON`
   - `📊 Download Multi-Sheet Excel (.xlsx)`
2. **Via Python Script**: Run the export module to generate a fresh file in `data/exports/`:
   ```powershell
   python -c "from src.exports.export import DataExporter; DataExporter().export_excel_file('data/exports/fortyguard_environmental_analytics.xlsx')"
   ```

The Excel workbook contains 6 tabs:
1. **Environmental Observations**: Full point-level metrics (reference temp, apparent temp, heat index, wet bulb, relative humidity, AQI, solar flux).
2. **Locations**: Monitored US metropolitan cities and coordinates.
3. **Collection Summary**: API job telemetry and execution history.
4. **Heatmap Results**: GeoJSON thermal tiles with microclimate readings.
5. **Reports**: Heat Intelligence compilation dossiers.
6. **Data Quality Summary**: Column-by-column missingness and completeness audit.

---

## 🔒 API Limitations & Known Coverage Rules

1. **US Coverage Only**: FortyGuard's current API catalog strictly covers locations within the United States. Queries for foreign coordinates (e.g., Karachi, London) return HTTP 400 (`OUT_OF_COVERAGE`).
2. **Credit Awareness**: Endpoints consume credits:
   - Point observations (`env_params`): ~1 credit / request
   - Routing (`routing`): ~3,500 credits / request (API Premium)
   - Heatmap (`heatmap`): Consumes credits based on AOI area (up to 10 mi² Basic, up to 50 mi² Premium)
   - Heat Intelligence (`heat_intelligence`): ~8,600 credits / request (API Premium)
   - Street View (`streetview`): ~8,600 credits / request (API Premium)
   - Satellite (`satellite`): ~14,400 credits / request (API Premium)
3. **Straight-Line Distance Cap for Routing**: Origin and destination must not exceed **200 km** straight-line distance.
4. **Parameter Selection Cap**: Basic and Startup tiers allow a maximum of 3 selected parameters per `env_params` call.
5. **Satellite Imagery Dates**: Imagery capture dates reflect catalog passes and may not match the exact requested hour.

---

## 👨‍💻 Data Science Portfolio Highlights

This project demonstrates:
- **Clean Architecture**: Decoupled API client, database ORM, cleaning, analytics, and presentation layers.
- **Data Engineering**: Robust schema modeling, idempotent upserts, foreign key integrity, and deduplication.
- **Microclimate Science**: Real-world implementation of wet-bulb safety, apparent temperature deltas, and urban heat island analysis.
- **Production Streamlit UX**: Non-blocking asynchronous task polling, credit consumption guardrails, and interactive Plotly visualizations.

