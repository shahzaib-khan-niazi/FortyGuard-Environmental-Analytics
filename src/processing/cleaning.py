"""
Data Cleaning and Quality Assurance Module
==========================================
Provides data auditing, type enforcement, duplicate detection,
missing-value analysis, and outlier flagging while maintaining
strict raw data integrity without fabricating synthetic values.
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


class DataCleaner:
    """Performs rigorous data quality checks and non-destructive cleaning."""

    NUMERIC_COLUMNS = [
        "reference_temp",
        "heat_index",
        "apparent_temp",
        "wet_bulb_temp",
        "relative_humidity",
        "precipitation",
        "cloud_cover",
        "aqi_overall",
        "aqi_pm25",
        "aqi_pm10",
        "aqi_no2",
        "aqi_co",
        "aqi_o3",
        "aqi_so2",
        "methane_ppb",
        "co2_ppm",
        "ghi",
        "dni",
        "dhi",
    ]

    @classmethod
    def clean_dataset(cls, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Produce a cleaned copy of the dataframe with:
        - Strict datetime parsing
        - Numeric conversion with NaN for missing values
        - Deduplication
        - Quality report metadata
        
        Raw original dataframe is preserved untouched.
        """
        if df.empty:
            return df.copy(), {
                "initial_rows": 0,
                "clean_rows": 0,
                "duplicates_removed": 0,
                "missing_summary": {},
            }

        cleaned = df.copy()
        initial_rows = len(cleaned)

        # 1. Type validation and datetime parsing
        if "timestamp" in cleaned.columns:
            cleaned["parsed_timestamp"] = pd.to_datetime(cleaned["timestamp"], utc=True, errors="coerce")

        for col in cls.NUMERIC_COLUMNS:
            if col in cleaned.columns:
                cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")

        # 2. Duplicate detection
        dup_subset = ["location_id", "timestamp"]
        existing_subset = [c for c in dup_subset if c in cleaned.columns]
        duplicates_removed = 0
        if existing_subset:
            duplicates_count = cleaned.duplicated(subset=existing_subset).sum()
            if duplicates_count > 0:
                cleaned = cleaned.drop_duplicates(subset=existing_subset, keep="last")
                duplicates_removed = int(duplicates_count)

        # 3. Missing Value Analysis
        missing_summary = cls.analyze_missing_values(cleaned)

        # 4. Outlier Analysis
        outlier_flags = cls.flag_outliers(cleaned)

        # Attach quality metadata
        quality_report = {
            "initial_rows": initial_rows,
            "clean_rows": len(cleaned),
            "duplicates_removed": duplicates_removed,
            "missing_summary": missing_summary,
            "outlier_summary": outlier_flags,
        }

        return cleaned, quality_report

    @classmethod
    def analyze_missing_values(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate null counts and percentage of missingness per column."""
        total = len(df)
        if total == 0:
            return {}

        summary = {}
        for col in df.columns:
            null_count = int(df[col].isna().sum())
            null_pct = round((null_count / total) * 100, 2)
            summary[col] = {
                "null_count": null_count,
                "null_percent": null_pct,
                "valid_count": total - null_count,
            }
        return summary

    @classmethod
    def flag_outliers(
        cls,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        iqr_multiplier: float = 1.5,
    ) -> Dict[str, Any]:
        """
        Flag outliers using IQR (Interquartile Range) method.
        Never deletes or modifies original values; returns index sets and bounds.
        """
        target_cols = columns or [
            c for c in ["reference_temp", "apparent_temp", "relative_humidity", "aqi_overall"]
            if c in df.columns
        ]

        outlier_info = {}
        for col in target_cols:
            series = df[col].dropna()
            if len(series) < 4:
                continue

            q25 = float(series.quantile(0.25))
            q75 = float(series.quantile(0.75))
            iqr = q75 - q25
            lower_bound = q25 - (iqr_multiplier * iqr)
            upper_bound = q75 + (iqr_multiplier * iqr)

            outlier_mask = (series < lower_bound) | (series > upper_bound)
            outlier_count = int(outlier_mask.sum())

            outlier_info[col] = {
                "q25": round(q25, 2),
                "q75": round(q75, 2),
                "iqr": round(iqr, 2),
                "lower_bound": round(lower_bound, 2),
                "upper_bound": round(upper_bound, 2),
                "outlier_count": outlier_count,
            }

        return outlier_info
