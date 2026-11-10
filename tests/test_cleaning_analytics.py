"""
Unit tests for Data Cleaning and Analytics Modules
==================================================
Tests data quality audit, missing values, outliers, descriptive stats,
correlation matrices, and thermal stress classifications.
"""

import pandas as pd
import numpy as np
from src.processing.cleaning import DataCleaner
from src.analytics.analysis import EnvironmentalAnalytics


def sample_observations():
    """Create a sample environmental observations dataframe for testing."""
    return pd.DataFrame([
        {
            "location_id": 1,
            "location_name": "Phoenix, AZ",
            "timestamp": "2024-07-15T14:00:00",
            "reference_temp": 35.0,
            "apparent_temp": 40.5,
            "heat_index": 34.0,
            "wet_bulb_temp": 23.5,
            "relative_humidity": 22.0,
            "aqi_overall": 58.0,
            "ghi": 920.0,
        },
        {
            "location_id": 1,
            "location_name": "Phoenix, AZ",
            "timestamp": "2024-07-15T15:00:00",
            "reference_temp": 36.0,
            "apparent_temp": 41.8,
            "heat_index": 35.5,
            "wet_bulb_temp": 24.1,
            "relative_humidity": 21.0,
            "aqi_overall": 62.0,
            "ghi": 880.0,
        },
        {
            "location_id": 2,
            "location_name": "Miami, FL",
            "timestamp": "2024-07-15T14:00:00",
            "reference_temp": 32.0,
            "apparent_temp": 42.0,
            "heat_index": 41.5,
            "wet_bulb_temp": 28.5,
            "relative_humidity": 75.0,
            "aqi_overall": 35.0,
            "ghi": 850.0,
        },
        {
            "location_id": 3,
            "location_name": "Austin, TX",
            "timestamp": "2024-07-15T14:00:00",
            "reference_temp": 34.0,
            "apparent_temp": 39.5,
            "heat_index": 37.0,
            "wet_bulb_temp": 26.0,
            "relative_humidity": 48.0,
            "aqi_overall": 45.0,
            "ghi": 900.0,
        },
    ])


def test_data_cleaner_audit():
    """Test data cleaning and missing value analysis."""
    df = sample_observations()
    # Add an exact duplicate row of index 0
    duplicate_row = df.iloc[[0]].copy()
    df_with_dup = pd.concat([df, duplicate_row], ignore_index=True)

    cleaned, report = DataCleaner.clean_dataset(df_with_dup)
    assert report["duplicates_removed"] == 1
    assert len(cleaned) == 4
    assert "missing_summary" in report
    assert report["missing_summary"]["apparent_temp"]["null_count"] == 0


def test_outlier_detection():
    """Test IQR outlier detection."""
    df = sample_observations()
    outliers = DataCleaner.flag_outliers(df, columns=["apparent_temp"])
    assert "apparent_temp" in outliers
    assert outliers["apparent_temp"]["outlier_count"] == 0


def test_descriptive_stats():
    """Test descriptive statistics calculation."""
    df = sample_observations()
    stats_df = EnvironmentalAnalytics.compute_descriptive_stats(df)
    assert not stats_df.empty
    assert "apparent_temp" in stats_df.index
    assert stats_df.loc["apparent_temp", "Mean"] > 35.0


def test_correlation_matrix():
    """Test correlation matrix calculation."""
    df = sample_observations()
    corr = EnvironmentalAnalytics.compute_correlation_matrix(df)
    assert not corr.empty
    assert "apparent_temp" in corr.columns
    assert "relative_humidity" in corr.columns


def test_location_comparison():
    """Test location ranking."""
    df = sample_observations()
    ranked = EnvironmentalAnalytics.compare_locations(df, metric="apparent_temp")
    assert not ranked.empty
    assert len(ranked) == 3
    assert "Rank" in ranked.columns
    assert ranked.iloc[0]["Rank"] == 1


def test_thermal_stress_enrichment():
    """Test thermal stress tier derivation."""
    df = sample_observations()
    enriched = EnvironmentalAnalytics.enrich_with_thermal_stress_indices(df)
    assert "calc_thermal_delta" in enriched.columns
    assert "calc_heat_index_category" in enriched.columns
    assert "calc_wet_bulb_tier" in enriched.columns
    assert "calc_aqi_category" in enriched.columns

    # Miami has apparent_temp 42.0 and ref 32.0 => delta = 10.0
    miami_row = enriched[enriched["location_name"] == "Miami, FL"].iloc[0]
    assert miami_row["calc_thermal_delta"] == 10.0
