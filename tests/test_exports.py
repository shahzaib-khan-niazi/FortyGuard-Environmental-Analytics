"""
Unit tests for Data Export Capabilities
======================================
Tests generation of CSV, JSON, and multi-sheet Excel workbooks.
"""

import io
import datetime
import openpyxl
import pandas as pd
from src.exports.export import DataExporter
from src.database.db import DatabaseManager


def test_csv_and_json_exports():
    """Test CSV and JSON byte exports."""
    df = pd.DataFrame([
        {"location": "Phoenix", "temp": 35.0},
        {"location": "Miami", "temp": 32.0},
    ])
    exporter = DataExporter()

    csv_bytes = exporter.export_csv_bytes(df)
    assert b"Phoenix" in csv_bytes
    assert b"Miami" in csv_bytes

    json_bytes = exporter.export_json_bytes(df)
    assert b'"location": "Phoenix"' in json_bytes or b'"location":"Phoenix"' in json_bytes


def test_excel_multisheet_export():
    """Test multi-sheet Excel generation."""
    exporter = DataExporter()
    excel_bytes = exporter.export_excel_bytes()

    # Verify using openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    sheet_names = wb.sheetnames

    expected_sheets = [
        "Environmental Observations",
        "Locations",
        "Collection Summary",
        "Heatmap Results",
        "Reports",
        "Data Quality Summary",
    ]

    for expected in expected_sheets:
        assert expected in sheet_names, f"Sheet {expected} missing from Excel export"


def test_excel_timezone_aware_export():
    """
    Test that timezone-aware datetime64 columns, pandas Timestamps,
    and Python datetime objects in object columns export cleanly to Excel
    without ValueError: Excel does not support datetimes with timezones,
    while preserving the displayed wall-clock time and leaving source DataFrames unmodified.
    """
    tz_arizona = datetime.timezone(datetime.timedelta(hours=-7))
    tz_utc = datetime.timezone.utc

    source_df = pd.DataFrame({
        "location_name": ["Phoenix, AZ", "Miami, FL"],
        "dt64_tz": pd.date_range("2024-07-15 14:00", periods=2, freq="h", tz="America/Phoenix"),
        "obj_timestamp_tz": [
            pd.Timestamp("2024-07-15 14:00:00-07:00"),
            pd.Timestamp("2024-07-15 15:00:00-07:00"),
        ],
        "obj_py_datetime_tz": [
            datetime.datetime(2024, 7, 15, 14, 0, tzinfo=tz_arizona),
            datetime.datetime(2024, 7, 15, 15, 0, tzinfo=tz_utc),
        ],
        "mixed_obj": [
            pd.Timestamp("2024-07-15 14:00:00-07:00"),
            "string_val",
        ],
        "apparent_temp": [40.7, 42.1],
    })

    # Keep a reference copy to verify source_df is not modified
    orig_dt64_tz = source_df["dt64_tz"].dt.tz
    orig_ts_tz = source_df["obj_timestamp_tz"].iloc[0].tz

    exporter = DataExporter()
    excel_bytes = exporter.export_excel_bytes(observations_df=source_df)

    # 1. Assert export succeeded and produced valid bytes
    assert len(excel_bytes) > 0

    # 2. Verify source DataFrame was not mutated
    assert source_df["dt64_tz"].dt.tz == orig_dt64_tz
    assert source_df["obj_timestamp_tz"].iloc[0].tz == orig_ts_tz

    # 3. Inspect generated Excel sheets using openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    assert "Environmental Observations" in wb.sheetnames
    ws = wb["Environmental Observations"]

    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    row1 = rows[1]

    # Verify column headers exist
    assert "dt64_tz" in headers
    assert "obj_timestamp_tz" in headers
    assert "obj_py_datetime_tz" in headers

    dt64_idx = headers.index("dt64_tz")
    obj_ts_idx = headers.index("obj_timestamp_tz")
    obj_dt_idx = headers.index("obj_py_datetime_tz")

    # 4. Verify wall-clock values are preserved without timezone errors
    val_dt64 = row1[dt64_idx]
    val_obj_ts = row1[obj_ts_idx]
    val_obj_dt = row1[obj_dt_idx]

    assert isinstance(val_dt64, datetime.datetime)
    assert val_dt64.tzinfo is None
    assert val_dt64.year == 2024 and val_dt64.month == 7 and val_dt64.day == 15
    assert val_dt64.hour == 14 and val_dt64.minute == 0

    assert isinstance(val_obj_ts, datetime.datetime)
    assert val_obj_ts.tzinfo is None
    assert val_obj_ts.hour == 14 and val_obj_ts.minute == 0

    assert isinstance(val_obj_dt, datetime.datetime)
    assert val_obj_dt.tzinfo is None
    assert val_obj_dt.hour == 14 and val_obj_dt.minute == 0


def test_remove_timezones_for_excel_standalone():
    """Test the standalone remove_timezones_for_excel method."""
    df = pd.DataFrame({
        "tz_col": pd.Series([pd.Timestamp("2024-07-15 14:00:00-07:00")]),
        "py_dt": pd.Series([datetime.datetime(2024, 7, 15, 14, 0, tzinfo=datetime.timezone.utc)]),
        "plain_col": [100],
    })

    safe_df = DataExporter.remove_timezones_for_excel(df)

    # Output has no timezones
    assert getattr(safe_df["tz_col"].dt, "tz", None) is None
    assert safe_df["py_dt"].iloc[0].tzinfo is None

    # Source df still has timezones
    assert getattr(df["tz_col"].dt, "tz", None) is not None
    assert df["py_dt"].iloc[0].tzinfo is not None


