"""
Unit tests for Database Operations
==================================
Tests SQLite schema creation, location management, observations insertion,
and analytical queries using an isolated in-memory or temporary database.
"""

import os
import gc
import tempfile
import pytest
import pandas as pd
from src.database.db import DatabaseManager


@pytest.fixture
def test_db():
    """Create a temporary test database file with safe Windows cleanup."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(db_path=path)
    yield db
    del db
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass


def test_upsert_and_get_location(test_db):
    """Test inserting and updating locations."""
    loc_id1 = test_db.upsert_location(
        name="Phoenix, AZ",
        latitude=33.4484,
        longitude=-112.0740,
        state="AZ",
        notes="Desert capital",
    )
    assert loc_id1 > 0

    loc = test_db.get_location_by_id(loc_id1)
    assert loc is not None
    assert loc["name"] == "Phoenix, AZ"
    assert loc["latitude"] == 33.4484
    assert loc["state"] == "AZ"

    # Upsert with new notes
    loc_id2 = test_db.upsert_location(
        name="Phoenix, AZ",
        latitude=33.4484,
        longitude=-112.0740,
        elevation=333.0,
        notes="Updated notes",
    )
    assert loc_id2 == loc_id1

    loc_updated = test_db.get_location_by_name("Phoenix, AZ")
    assert loc_updated["elevation"] == 333.0
    assert loc_updated["notes"] == "Updated notes"


def test_insert_environmental_observations(test_db):
    """Test parsing and ingesting FortyGuard env_params response payload."""
    loc_id = test_db.upsert_location(name="Austin, TX", latitude=30.2672, longitude=-97.7431)
    job_id = test_db.create_job("env_params", {"name": "Austin"})

    mock_result = {
        "metadata": {
            "timezone": "America/Chicago",
            "time_range": {"start": "2024-07-15T14:00:00-05:00"},
            "timestamps": ["2024-07-15T14:00:00-05:00"],
        },
        "locations": [
            {
                "lat": 30.2672,
                "lon": -97.7431,
                "elevation": 150.0,
                "temperature": 36.5,
                "parameters": {
                    "heat_index_celsius": [38.2],
                    "apparent_temperature_celsius": [41.0],
                    "relative_humidity_percent": [45.0],
                    "wet_bulb_temperature_celsius": [26.4],
                    "air_quality:idx": [42.0],
                    "precipitation_mm": [0.0],
                    "cloud_cover_octas": [1.0],
                },
                "solar_irradiance": {
                    "clear_sky": {"ghi": 890.5, "dni": 810.0, "dhi": 105.0}
                },
            }
        ],
    }

    inserted = test_db.insert_environmental_observations(
        location_id=loc_id,
        job_id=job_id,
        result_payload=mock_result,
        raw_response_str="{}",
    )
    assert inserted == 1

    df = test_db.get_observations_df(location_ids=[loc_id])
    assert not df.empty
    assert len(df) == 1
    row = df.iloc[0]
    assert row["location_name"] == "Austin, TX"
    assert row["apparent_temp"] == 41.0
    assert row["heat_index"] == 38.2
    assert row["relative_humidity"] == 45.0
    assert row["ghi"] == 890.5


def test_platform_overview_metrics(test_db):
    """Test KPI aggregation calculations."""
    loc_id = test_db.upsert_location("Miami, FL", 25.7617, -80.1918)
    job_id = test_db.create_job("env_params", {})
    test_db.update_job_status(job_id, "COMPLETED")

    kpis = test_db.get_platform_overview_metrics()
    assert kpis["total_locations"] >= 1
    assert kpis["completed_jobs"] == 1
    assert kpis["failed_jobs"] == 0
