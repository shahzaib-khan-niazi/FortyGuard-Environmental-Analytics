"""
Environmental Analytics and Statistical Modeling Module
======================================================
Provides statistical analysis, correlation modeling, distribution insights,
cross-location benchmarking, and thermal stress classifications.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats


class EnvironmentalAnalytics:
    """Computes advanced statistical indicators and environmental benchmarks."""

    @staticmethod
    def compute_descriptive_stats(df: pd.DataFrame, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Compute comprehensive descriptive statistics for numeric environmental metrics:
        Mean, Median, Std Dev, Min, 25%, 75%, Max, IQR, Skewness, Kurtosis.
        """
        if df.empty:
            return pd.DataFrame()

        num_df = df[columns] if columns else df.select_dtypes(include=[np.number])
        if num_df.empty:
            return pd.DataFrame()

        records = []
        for col in num_df.columns:
            s = num_df[col].dropna()
            if len(s) == 0:
                continue

            q25 = float(s.quantile(0.25))
            q75 = float(s.quantile(0.75))
            iqr = q75 - q25
            skew_val = float(stats.skew(s)) if len(s) >= 3 else np.nan
            kurt_val = float(stats.kurtosis(s)) if len(s) >= 4 else np.nan

            records.append({
                "Metric": col,
                "Count": int(len(s)),
                "Mean": round(float(s.mean()), 2),
                "Median": round(float(s.median()), 2),
                "Std Dev": round(float(s.std()), 2) if len(s) > 1 else 0.0,
                "Min": round(float(s.min()), 2),
                "25%": round(q25, 2),
                "75%": round(q75, 2),
                "Max": round(float(s.max()), 2),
                "IQR": round(iqr, 2),
                "Skewness": round(skew_val, 2) if not np.isnan(skew_val) else "N/A",
                "Kurtosis": round(kurt_val, 2) if not np.isnan(kurt_val) else "N/A",
            })

        return pd.DataFrame(records).set_index("Metric") if records else pd.DataFrame()

    @staticmethod
    def compute_correlation_matrix(
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        method: str = "pearson"
    ) -> pd.DataFrame:
        """Calculate pairwise correlation matrix between numeric environmental metrics."""
        if df.empty:
            return pd.DataFrame()

        available_cols = [
            c for c in (columns or [
                "reference_temp", "apparent_temp", "heat_index", "wet_bulb_temp",
                "relative_humidity", "cloud_cover", "aqi_overall", "aqi_pm25", "ghi"
            ])
            if c in df.columns and df[c].notna().sum() >= 2
        ]

        if len(available_cols) < 2:
            return pd.DataFrame()

        corr = df[available_cols].corr(method=method)
        return corr.round(3)

    @staticmethod
    def compare_locations(df: pd.DataFrame, metric: str = "apparent_temp") -> pd.DataFrame:
        """
        Rank and compare locations for a specific environmental indicator.
        Calculates mean, max, min, and count of observations per location.
        """
        if df.empty or metric not in df.columns or "location_name" not in df.columns:
            return pd.DataFrame()

        valid = df.dropna(subset=[metric])
        if valid.empty:
            return pd.DataFrame()

        grouped = valid.groupby("location_name")[metric].agg([
            ("Obs Count", "count"),
            ("Mean", "mean"),
            ("Max", "max"),
            ("Min", "min"),
            ("Std Dev", lambda x: x.std() if len(x) > 1 else 0.0),
        ]).reset_index()

        grouped["Mean"] = grouped["Mean"].round(2)
        grouped["Max"] = grouped["Max"].round(2)
        grouped["Min"] = grouped["Min"].round(2)
        grouped["Std Dev"] = grouped["Std Dev"].round(2)

        # Rank locations descending by mean
        grouped = grouped.sort_values(by="Mean", ascending=False).reset_index(drop=True)
        grouped["Rank"] = grouped.index + 1
        return grouped

    @classmethod
    def enrich_with_thermal_stress_indices(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Derive calculated indicators (clearly distinguished from observed API values):
        - Thermal Delta = Apparent Temp - Reference Temp
        - Heat Index Hazard Tier (NOAA criteria)
        - Wet-Bulb Safety Tier (OSHA/ISO criteria)
        - AQI Health Tier (EPA AirNow criteria)
        """
        if df.empty:
            return df.copy()

        enriched = df.copy()

        # 1. Thermal Anomaly Delta
        if "apparent_temp" in enriched.columns and "reference_temp" in enriched.columns:
            enriched["calc_thermal_delta"] = (
                enriched["apparent_temp"] - enriched["reference_temp"]
            ).round(2)

        # 2. NOAA Heat Index Hazard Classification
        if "heat_index" in enriched.columns:
            def _heat_index_category(val: Optional[float]) -> str:
                if pd.isna(val):
                    return "Unknown"
                if val < 27.0:
                    return "Normal (<27°C)"
                elif val < 32.0:
                    return "Caution (27-32°C)"
                elif val < 41.0:
                    return "Extreme Caution (32-41°C)"
                elif val < 54.0:
                    return "Danger (41-54°C)"
                else:
                    return "Extreme Danger (≥54°C)"

            enriched["calc_heat_index_category"] = enriched["heat_index"].apply(_heat_index_category)

        # 3. Wet-Bulb Stress Classification
        if "wet_bulb_temp" in enriched.columns:
            def _wb_category(val: Optional[float]) -> str:
                if pd.isna(val):
                    return "Unknown"
                if val < 26.0:
                    return "Safe (<26°C)"
                elif val < 29.0:
                    return "Moderate Stress (26-29°C)"
                elif val < 32.0:
                    return "High Stress (29-32°C)"
                else:
                    return "Critical Danger (≥32°C)"

            enriched["calc_wet_bulb_tier"] = enriched["wet_bulb_temp"].apply(_wb_category)

        # 4. US EPA AQI Classification
        if "aqi_overall" in enriched.columns:
            def _aqi_category(val: Optional[float]) -> str:
                if pd.isna(val):
                    return "Unknown"
                if val <= 50:
                    return "Good (0-50)"
                elif val <= 100:
                    return "Moderate (51-100)"
                elif val <= 150:
                    return "Unhealthy for Sensitive (101-150)"
                elif val <= 200:
                    return "Unhealthy (151-200)"
                elif val <= 300:
                    return "Very Unhealthy (201-300)"
                else:
                    return "Hazardous (301+)"

            enriched["calc_aqi_category"] = enriched["aqi_overall"].apply(_aqi_category)

        return enriched

