"""
Dashboard Page: Data Collection
===============================
Provides an interactive interface to configure and launch FortyGuard API requests,
validate US coverage, avoid duplicates, and monitor asynchronous activity jobs.
"""

import time
import streamlit as st
import pandas as pd
from datetime import date, datetime

from src.collection.collector import DataCollector, SUPPORTED_US_LOCATIONS, AVAILABLE_MEASUREMENTS
from src.database.db import DatabaseManager
from src.api.fortyguard_client import FortyGuardAPIError, OutOfCoverageError, AuthenticationError


def render_collection_page(db: DatabaseManager):
    st.header("🛰️ Environmental Data Collection")
    st.markdown(
        "Query point-level microclimate data from the **FortyGuard `/v1/env_params`** endpoint. "
        "Requests are executed asynchronously with automatic status polling and local database ingestion."
    )

    # Coverage Notice
    st.info(
        "📍 **US Coverage Notice:** FortyGuard's current release supports US locations only. "
        "Live API requests outside the United States are rejected by the API."
    )

    collector = DataCollector(db=db)

    with st.form("collection_form"):
        st.subheader("1. Location Selection")
        col1, col2 = st.columns(2)

        location_names = [loc["name"] for loc in SUPPORTED_US_LOCATIONS] + ["Custom US Coordinates..."]
        selected_loc_name = col1.selectbox(
            "Select Supported US Location",
            options=location_names,
            index=0,  # Phoenix, AZ (Official Demo)
            help="Choose from documented supported US metropolitan regions or enter custom coordinates.",
        )

        custom_mode = selected_loc_name == "Custom US Coordinates..."

        if not custom_mode:
            preset = next(loc for loc in SUPPORTED_US_LOCATIONS if loc["name"] == selected_loc_name)
            default_lat = preset["latitude"]
            default_lon = preset["longitude"]
            default_name = preset["name"]
        else:
            default_lat = 33.4484
            default_lon = -112.0740
            default_name = "Custom Location"

        c_lat, c_lon = col2.columns(2)
        latitude = c_lat.number_input(
            "Latitude",
            value=default_lat,
            format="%.4f",
            disabled=not custom_mode,
            help="Must be within United States bounds (e.g. 24.0° to 50.0° N)",
        )
        longitude = c_lon.number_input(
            "Longitude",
            value=default_lon,
            format="%.4f",
            disabled=not custom_mode,
            help="Must be within United States bounds (e.g. -125.0° to -66.0° W)",
        )

        custom_name = default_name
        if custom_mode:
            custom_name = st.text_input("Location Label Name", value="My US Location")

        st.markdown("---")
        st.subheader("2. Temporal & Environmental Parameters")

        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1:
            req_date = st.date_input("Target Date", value=date(2024, 7, 15))
        with t_col2:
            req_time = st.selectbox(
                "Hour of Day (24-hour)",
                options=[f"{h:02d}:00" for h in range(0, 24)],
                index=14,  # 14:00 (Peak heat)
            )
        with t_col3:
            ref_temp = st.number_input(
                "Reference Temperature (°C)",
                value=35.0,
                min_value=-20.0,
                max_value=60.0,
                step=0.5,
                help="Baseline ambient temperature context for FortyGuard models",
            )

        st.subheader("3. Measurement Parameters")
        meas_options = [m["id"] for m in AVAILABLE_MEASUREMENTS]
        meas_labels = {m["id"]: f"{m['name']} ({m['category']})" for m in AVAILABLE_MEASUREMENTS}

        selected_measurements = st.multiselect(
            "Select Environmental Measurements to Query",
            options=meas_options,
            default=["apparent_temperature", "relative_humidity", "air_quality"],
            format_func=lambda x: meas_labels.get(x, x),
            help="Note: Basic/Startup API tiers allow up to 3 selected parameters per request.",
        )

        use_cache = st.checkbox("Check local database cache before querying API (Saves Credits)", value=True)

        st.markdown("---")
        st.subheader("4. API Credit Awareness & Confirmation")
        st.warning(
            "⚠️ **Credit Awareness:** FortyGuard Enterprise API calls consume account credits. "
            "Please confirm you wish to execute this request."
        )
        credit_confirmed = st.checkbox(
            "I understand this request may consume FortyGuard API credits and wish to proceed.",
            value=False,
        )

        submit_btn = st.form_submit_button("🚀 Start Environmental Data Collection", use_container_width=True)

    if submit_btn:
        if not credit_confirmed:
            st.error("❌ Action stopped: Please confirm the API credit checkbox above before proceeding.")
            return

        # Coordinate check
        is_us, val_msg = DataCollector.validate_us_coordinates(latitude, longitude)
        if not is_us:
            st.error(f"❌ Coverage Error: {val_msg}")
            return

        progress_placeholder = st.empty()
        status_box = st.empty()

        def update_progress(msg: str, percent: int):
            progress_placeholder.progress(min(percent, 100))
            status_box.info(f"⏳ {msg}")

        try:
            start_date_str = req_date.strftime("%Y-%m-%d")
            with st.spinner("Connecting to FortyGuard Enterprise API..."):
                res = collector.collect_point_data(
                    location_name=custom_name,
                    latitude=latitude,
                    longitude=longitude,
                    reference_temperature=ref_temp,
                    start_date=start_date_str,
                    start_time=req_time,
                    filter_type=1,
                    selected_parameters=selected_measurements,
                    use_cache=use_cache,
                    progress_callback=update_progress,
                )

            progress_placeholder.empty()
            status_box.empty()

            if res.get("cached"):
                st.success(f"⚡ {res.get('message')}")
            else:
                st.success(
                    f"✅ **Success!** Collected {res.get('rows_inserted')} record(s) "
                    f"under Activity ID `{res.get('activity_id')}`."
                )

        except OutOfCoverageError as e:
            st.error(f"❌ Region Out of Coverage: {e}")
        except AuthenticationError as e:
            st.error(f"🔒 Authentication Error: {e}")
        except Exception as e:
            st.error(f"❌ Collection Error: {e}")

    # Jobs Table
    st.markdown("---")
    st.subheader("📋 Collection Jobs History")
    jobs = db.get_jobs(limit=25)
    if jobs:
        jobs_df = pd.DataFrame(jobs)[["id", "job_type", "status", "activity_id", "created_at", "completed_at", "error_message"]]
        st.dataframe(jobs_df, use_container_width=True)
    else:
        st.write("No collection jobs yet.")

