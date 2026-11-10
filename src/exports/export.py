"""
Data Export Module for FortyGuard Platform
==========================================
Provides multi-format data export capabilities:
- Cleaned CSV exports
- Structured JSON exports
- Multi-sheet Microsoft Excel workbooks with data quality audit sheets
"""

import io
import os
import json
import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from src.database.db import DatabaseManager
from src.processing.cleaning import DataCleaner


class DataExporter:
    """Exports platform datasets into CSV, JSON, and multi-sheet Excel files."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    @staticmethod
    def remove_timezones_for_excel(df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect and safely remove timezone information from all datetime columns
        and object columns containing Python datetime or pandas Timestamp objects,
        preserving the displayed wall-clock date and time.
        Does not modify the original DataFrame or database records.
        """
        if df.empty:
            return df.copy()

        safe_df = df.copy()

        def _strip_tz_val(val: Any) -> Any:
            if val is None or pd.isna(val):
                return val
            if isinstance(val, pd.Timestamp):
                if val.tz is not None:
                    return val.tz_localize(None)
                return val
            if isinstance(val, datetime.datetime):
                if val.tzinfo is not None:
                    return val.replace(tzinfo=None)
                return val
            return val

        for col in safe_df.columns:
            series = safe_df[col]
            # 1. Standard datetime dtype with timezone (e.g. datetime64[ns, UTC])
            if pd.api.types.is_datetime64_any_dtype(series):
                if getattr(series.dt, "tz", None) is not None:
                    safe_df[col] = series.dt.tz_localize(None)
            # 2. Object or mixed columns that may contain Timestamps or datetimes
            elif series.dtype == object:
                safe_df[col] = series.apply(_strip_tz_val)

        return safe_df

    def export_csv_bytes(self, df: pd.DataFrame) -> bytes:
        """Convert DataFrame to CSV bytes for in-browser download."""
        return df.to_csv(index=False).encode("utf-8")

    def export_json_bytes(self, df: pd.DataFrame) -> bytes:
        """Convert DataFrame to JSON bytes for in-browser download."""
        return df.to_json(orient="records", date_format="iso", indent=2).encode("utf-8")

    def export_excel_bytes(
        self,
        observations_df: Optional[pd.DataFrame] = None,
    ) -> bytes:
        """
        Generate a comprehensive multi-sheet Excel workbook as bytes.
        Sheets:
        1. Environmental Observations
        2. Locations
        3. Collection Summary
        4. Heatmap Results
        5. Reports
        6. Data Quality Summary
        """
        output = io.BytesIO()

        # 1. Observations
        obs_df = observations_df if observations_df is not None else self.db.get_observations_df()
        if obs_df.empty:
            obs_df = pd.DataFrame([{"Message": "No observations recorded yet."}])

        # 2. Locations
        locs = self.db.get_locations()
        locs_df = pd.DataFrame(locs) if locs else pd.DataFrame([{"Message": "No locations registered."}])

        # 3. Collection Summary
        jobs = self.db.get_jobs(limit=100)
        jobs_df = pd.DataFrame(jobs) if jobs else pd.DataFrame([{"Message": "No collection jobs run."}])

        # 4. Heatmap Results
        heatmaps = self.db.get_heatmaps()
        heatmaps_df = pd.DataFrame(heatmaps) if heatmaps else pd.DataFrame([{"Message": "No heatmap activities run."}])

        # 5. Reports
        reports = self.db.get_heat_intelligence_reports()
        reports_df = pd.DataFrame(reports) if reports else pd.DataFrame([{"Message": "No reports generated."}])

        # 6. Data Quality Summary
        if not obs_df.empty and "Message" not in obs_df.columns:
            _, quality_report = DataCleaner.clean_dataset(obs_df)
            missing_dict = quality_report.get("missing_summary", {})
            quality_rows = []
            for col, stats in missing_dict.items():
                quality_rows.append({
                    "Column Name": col,
                    "Valid Records": stats.get("valid_count"),
                    "Missing Records": stats.get("null_count"),
                    "Missing Percentage (%)": stats.get("null_percent"),
                })
            quality_df = pd.DataFrame(quality_rows) if quality_rows else pd.DataFrame([{"Message": "No metrics found."}])
        else:
            quality_df = pd.DataFrame([{"Message": "No observations available for quality audit."}])

        # Safely remove timezones across all exported DataFrames preserving wall-clock times
        clean_obs_df = self.remove_timezones_for_excel(obs_df)
        clean_locs_df = self.remove_timezones_for_excel(locs_df)
        clean_jobs_df = self.remove_timezones_for_excel(jobs_df)
        clean_heatmaps_df = self.remove_timezones_for_excel(heatmaps_df)
        clean_reports_df = self.remove_timezones_for_excel(reports_df)
        clean_quality_df = self.remove_timezones_for_excel(quality_df)

        # Write to Excel writer using openpyxl engine
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            clean_obs_df.to_excel(writer, sheet_name="Environmental Observations", index=False)
            clean_locs_df.to_excel(writer, sheet_name="Locations", index=False)
            clean_jobs_df.to_excel(writer, sheet_name="Collection Summary", index=False)
            clean_heatmaps_df.to_excel(writer, sheet_name="Heatmap Results", index=False)
            clean_reports_df.to_excel(writer, sheet_name="Reports", index=False)
            clean_quality_df.to_excel(writer, sheet_name="Data Quality Summary", index=False)

        output.seek(0)
        return output.getvalue()

    def export_excel_file(self, file_path: str, observations_df: Optional[pd.DataFrame] = None) -> str:
        """Write multi-sheet Excel file directly to disk."""
        excel_bytes = self.export_excel_bytes(observations_df)
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(excel_bytes)
        return file_path

