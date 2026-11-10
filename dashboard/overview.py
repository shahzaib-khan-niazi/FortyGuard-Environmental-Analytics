"""
Dashboard Page: Overview
========================
Displays executive KPIs, coverage map, telemetry, and quick summary charts.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.database.db import DatabaseManager


def render_overview_page(db: DatabaseManager):
    st.header("🌐 Platform Overview & Executive Summary")
    st.markdown(
        "Welcome to the **FortyGuard Environmental Intelligence Platform**. "
        "This platform provides microclimate intelligence, urban heat modeling, and atmospheric analytics "
        "powered by the FortyGuard Enterprise REST API."
    )

    kpis = db.get_platform_overview_metrics()

    # KPI Metric Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="Monitored Locations",
            value=kpis.get("total_locations", 0),
            help="Total registered US urban monitoring locations",
        )
    with c2:
        st.metric(
            label="Environmental Observations",
            value=kpis.get("total_observations", 0),
            help="Point-level environmental parameter records in database",
        )
    with c3:
        st.metric(
            label="Completed Jobs",
            value=kpis.get("completed_jobs", 0),
            help="Successfully executed API collection and analysis jobs",
        )
    with c4:
        st.metric(
            label="Failed Jobs",
            value=kpis.get("failed_jobs", 0),
            help="API requests that failed or encountered network errors",
        )

    st.caption(f"🕒 **Latest Observation Timestamp:** {kpis.get('latest_timestamp')}")

    st.markdown("---")

    # Available Indicators
    st.subheader("📊 Monitored Environmental Indicators")
    indicators = kpis.get("available_indicators", [])
    if indicators:
        badge_cols = st.columns(len(indicators) if len(indicators) <= 7 else 7)
        for i, ind in enumerate(indicators):
            col_idx = i % (len(indicators) if len(indicators) <= 7 else 7)
            badge_cols[col_idx].info(f"✓ {ind.replace('_', ' ').title()}")
    else:
        st.info("No observations collected yet. Visit the **Data Collection** page to collect your first dataset.")

    st.markdown("---")

    # Geospatial Map of Monitored Locations
    locs = db.get_locations()
    if locs:
        st.subheader("📍 Active US Monitoring Locations")
        loc_df = pd.DataFrame(locs)

        # Merge with latest observations if available
        obs_df = db.get_observations_df()
        if not obs_df.empty:
            latest_per_loc = (
                obs_df.sort_values("timestamp")
                .groupby("location_name")
                .last()
                .reset_index()
            )
            map_data = pd.merge(
                loc_df,
                latest_per_loc[["location_name", "apparent_temp", "relative_humidity", "aqi_overall"]],
                left_on="name",
                right_on="location_name",
                how="left",
            )
        else:
            map_data = loc_df
            map_data["apparent_temp"] = 35.0

        fig = px.scatter_geo(
            map_data,
            lat="latitude",
            lon="longitude",
            hover_name="name",
            color="apparent_temp",
            color_continuous_scale="Reds",
            size_max=15,
            scope="usa",
            title="Geographic Distribution of Supported Monitoring Sites in the US",
        )
        fig.update_layout(
            geo=dict(
                bgcolor="rgba(0,0,0,0)",
                lakecolor="rgb(220, 235, 250)",
                landcolor="rgb(240, 243, 246)",
                showsubunits=True,
                subunitcolor="rgb(200, 200, 200)",
                showcountries=False,
            ),
            margin=dict(l=0, r=0, t=40, b=0),
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Recent Jobs Telemetry Table
    st.subheader("⚡ Recent API Collection Jobs")
    jobs = db.get_jobs(limit=10)
    if jobs:
        jobs_df = pd.DataFrame(jobs)[["id", "job_type", "status", "activity_id", "created_at", "error_message"]]
        st.dataframe(jobs_df, use_container_width=True)
    else:
        st.write("No collection jobs recorded yet.")

