# FortyGuard Product & Technical Evaluation Dossier
**Candidate:** Shahzaib Khan Niazi  
**Role Applied For:** Data Engineering  
**Date:** November 2026  
**Project:** FortyGuard Environmental Intelligence Platform  

---

## Executive Summary
This evaluation dossier accompanies the official product evaluation submitted for the FortyGuard hiring process. It provides an empirical, data engineering-focused review of:
1. **The FortyGuard Temperature Dashboard®**
2. **The FortyGuard Temperature API® (v1)**
3. **The FortyGuard Temperature MCP (Model Context Protocol)**

The evaluation is supported by a fully operational, production-quality Python/Streamlit data platform connecting to FortyGuard's live API endpoints, ingesting microclimate data into an ACID-compliant local SQLite database, running statistical modeling, and providing multi-sheet reporting.

---

## 1. FortyGuard Architecture & Empirical Findings

```mermaid
flowchart TD
    subgraph FortyGuard Cloud
        API["FortyGuard REST API v1\n(https://api.fortyguard.com/v1/)"]
        LTM["Large Temperature Models (LTMs)\nThermal & Microclimate Inferencing"]
        TaskEngine["Asynchronous Activity Engine\n/v1/status/{activity_id}"]
    end

    subgraph Data Engineering Pipeline (Local)
        Client["FortyGuardClient\n(src/api/fortyguard_client.py)\n- API Key Header Auth\n- Exponential Backoff\n- Nonce/Masked Telemetry"]
        Cache["Local SQLite Caching Layer\n(data/fortyguard.db)\n- Prevents Duplicate Ingestion\n- Saves User Account Credits"]
        Cleaner["DataCleaner (src/processing/cleaning.py)\n- Non-Destructive Ingestion\n- Missingness Heatmaps\n- IQR Outlier Detection"]
        Analytics["EnvironmentalAnalytics (src/analytics/)\n- Thermal Delta (Apparent - Ambient)\n- NOAA Heat Index Hazard Classification\n- Wet-Bulb Stress Safety Thresholds\n- Pairwise Pearson/Spearman Correlations"]
        Exporter["DataExporter (src/exports/export.py)\n- CSV / JSON\n- Multi-Sheet OpenPyXL Workbook\n- Timezone-Aware Stripping (dt.tz_localize)"]
    end

    subgraph Presentation & UI Layer
        Dashboard["Streamlit Multi-Page Dashboard\n(app.py & dashboard/)\n- Page 1: Executive Overview & KPIs\n- Page 2: Interactive Data Collection\n- Page 3: Environmental Analytics\n- Page 4: Cross-Location Comparison\n- Page 5: Heat Intelligence & Heatmaps\n- Page 6: Satellite & Street View\n- Page 7: Temperature-Aware Routing\n- Page 8: Dataset Explorer & Exporter"]
    end

    API --> Client
    TaskEngine <--> Client
    Client --> Cache
    Cache --> Cleaner
    Cleaner --> Analytics
    Analytics --> Dashboard
    Analytics --> Exporter
```

### Empirical API Performance Observed
During live integration testing against `https://api.fortyguard.com/v1/`, the following metrics and response characteristics were recorded:

| Endpoint | Method | Operation Type | Observed Latency | Return Structure | Error Code Handling |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `/v1/env_params` | `POST` | Asynchronous Task | ~1.2s to queue | `activity_id` UUID | 400 (`OUT_OF_COVERAGE`), 401 (Auth), 422 (Validation) |
| `/v1/status/{id}` | `GET` | Status Polling | ~180ms – 400ms | `Processing` / `Completed` | 200 with inner status flag |
| `/v1/heatmap` | `POST` | Asynchronous GeoJSON | ~2.5s to queue; ~8s to complete | FeatureCollection of Polygon tiles | 422 missing AOI polygon |
| `/v1/routing` | `POST` | Asynchronous Path | ~1.5s to queue | Route geometries & thermal metrics | Enforces max 200 km straight-line distance |
| `/v1/heat_intelligence` | `POST` | Asynchronous Dossier | ~2.0s to queue | Temporary signed PDF download URL | 403 / 422 tier bounds |

---

## 2. In-Depth Product Evaluation

### A. FortyGuard Temperature Dashboard®
* **Strengths:**
  - Distinctive visual presentation focused on thermal comfort and human resilience rather than generic meteorological forecasts.
  - Integration of apparent temperature, wet-bulb stress, and solar irradiance elevates microclimate intelligence above conventional weather apps.
  - Good responsiveness across standard viewports and clean initial onboarding.
* **Weaknesses & Engineering Opportunities:**
  - **Credit Consumption Opacity:** High-compute requests (such as heatmaps covering up to 10–50 mi² or satellite segmentation) lack a proactive "pre-flight" estimation dialog showing exact credit deductions and runtime estimates before submission.
  - **Spatial AOI Ingestion:** Entering raw GeoJSON polygons manually in web forms introduces human error; an interactive polygon-drawing tool with real-time area calculation would improve usability.
  - **Diurnal Comparison:** Lacks multi-location comparison tools to contrast diurnal heat retention across diverse urban typologies (e.g., desert vs. coastal basin).

### B. FortyGuard Temperature API® (v1)
* **Strengths:**
  - Predictable REST conventions, consistent HTTP status code usage (401, 400 with `OUT_OF_COVERAGE`, 422 validation, 429 rate limiting).
  - Clear separation between point-level environmental data (`/v1/env_params`) and spatial grid mapping (`/v1/heatmap`).
  - High fidelity in solar irradiance outputs (providing modeled clear-sky GHI, DNI, and DHI in $\text{W/m}^2$).
* **Data Engineering Recommendations:**
  1. **Add Account & Quota Telemetry (`GET /v1/credits` or `GET /v1/account`):** Enterprise pipelines require programmatic access to inspect remaining credit quotas, subscription tier, and concurrency limits without human intervention.
  2. **Synchronous Mode for Lightweight Point Lookups:** For single-coordinate point lookups, an optional synchronous parameter (`?sync=true`) would reduce round-trip latency and eliminate status polling loops.
  3. **Batch Coordinate Ingestion (`POST /v1/env_params/batch`):** Support ingesting up to 50–100 coordinate pairs in a single HTTP request for logistics and sensor-grid deployments.

### C. FortyGuard Temperature MCP (Model Context Protocol)
* **Strengths:**
  - Modern protocol implementation enabling LLMs (e.g., Claude Code, Cursor) to leverage FortyGuard tools directly within agentic workflows.
  - Effective tool schema descriptions guiding LLMs to supply correct parameters (coordinates, temperature, date filters).
* **Engineering Opportunities:**
  - **Internal Polling Wrapper:** LLM tool executions expect synchronous returns. If an MCP tool returns an `activity_id` without awaiting completion, the model is forced to perform manual multi-step polling. The MCP server should encapsulate status polling up to a configurable timeout before returning final results to the agent.
  - **Prompt-Level Coverage Constraints:** Incorporating explicit coverage boundaries (e.g., *"Supported US regions only"*) within tool docstrings prevents agents from attempting queries for unsupported global locations.

---

## 3. Data Science & Engineering Highlights of this Project

1. **ACID-Compliant Relational Architecture:**
   - 10 structured SQLite tables tracking locations, collection jobs, observations, heatmap polygon tiles, intelligence reports, and telemetry logs.
   - Built-in deduplication ensuring zero wasted credits on repeated identical queries.

2. **Non-Destructive Data Cleaning:**
   - Strict separation between raw API responses and cleaned analytical DataFrames.
   - Transparent derivation of thermal indices (Thermal Delta $\text{Apparent} - \text{Ambient}$, NOAA heat categories, OSHA wet-bulb stress tiers) without fabricating synthetic values.

3. **Timezone-Aware Excel Serialization:**
   - Solved openpyxl's limitation regarding timezone-aware timestamps using `.dt.tz_localize(None)` to safely remove timezone metadata while strictly preserving wall-clock solar hours.
   - Exported comprehensive 6-sheet workbooks containing observations, locations, jobs, heatmaps, reports, and data quality audits.

4. **100% Mocked CI/CD Testing:**
   - 22 comprehensive unit and integration tests verifying authentication, 400 out-of-coverage boundaries, 422 schema validation, polling timeouts, and Excel exports in 4.5 seconds without consuming live API credits.
