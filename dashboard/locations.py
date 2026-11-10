"""
Dashboard Page: Location Comparison
===================================
Benchmarking and comparative multi-location analysis across microclimate indicators,
rankings, radar profiles, and missingness audits.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.database.db import DatabaseManager
from src.analytics.analysis import EnvironmentalAnalytics
from src.processing.cleaning import DataCleaner


def render_locations_page(db: DatabaseManager):
    st.header("🏙️ Cross-Location Benchmarking & Comparative Analytics")

    df = db.get_observations_df()
    if df.empty:
        st.warning("⚠️ No observations recorded in the database yet. Collect data to compare locations.")
        return

    clean_df, _ = DataCleaner.clean_dataset(df)
    enriched_df = EnvironmentalAnalytics.enrich_with_thermal_stress_indices(clean_df)

    locations = sorted(enriched_df["location_name"].unique().tolist())
    if len(locations) < 2:
        st.info("💡 Collect data for at least 2 locations to enable comparative ranking and cross-city analytics.")

    # Indicator selector for ranking
    numeric_metrics = [
        col for col in [
            "apparent_temp", "reference_temp", "heat_index", "wet_bulb_temp",
            "calc_thermal_delta", "relative_humidity", "aqi_overall", "aqi_pm25", "ghi"
        ]
        if col in enriched_df.columns and enriched_df[col].notna().sum() > 0
    ]

    metric_labels = {
        "apparent_temp": "Apparent Temperature (°C)",
        "reference_temp": "Reference Temperature (°C)",
        "heat_index": "Heat Index (°C)",
        "wet_bulb_temp": "Wet-Bulb Temperature (°C)",
        "calc_thermal_delta": "Thermal Comfort Delta (°C Above Ambient)",
        "relative_humidity": "Relative Humidity (%)",
        "aqi_overall": "Air Quality Index (AQI)",
        "aqi_pm25": "PM2.5 AQI",
        "ghi": "Global Horizontal Solar Irradiance (W/m²)",
    }

    selected_metric = st.selectbox(
        "Select Indicator for Location Ranking & Comparison",
        options=numeric_metrics,
        format_func=lambda x: metric_labels.get(x, x),
    )

    # Ranking Table and Chart
    ranked_df = EnvironmentalAnalytics.compare_locations(enriched_df, metric=selected_metric)
    if not ranked_df.empty:
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader(f"🏆 Location Ranking: {metric_labels.get(selected_metric, selected_metric)}")
            st.dataframe(ranked_df, use_container_width=True)

        with c2:
            fig_rank = px.bar(
                ranked_df,
                x="location_name",
                y="Mean",
                color="Mean",
                color_continuous_scale="Viridis",
                title=f"Mean {metric_labels.get(selected_metric, selected_metric)} by Location",
                labels={"location_name": "Location", "Mean": "Mean Value"},
            )
            fig_rank.update_layout(height=380)
            st.plotly_chart(fig_rank, use_container_width=True)

    st.markdown("---")

    # Multi-Location Radar Profile
    st.subheader("🕸️ Multi-Dimensional Microclimate Radar Profiles")
    radar_candidates = [
        ("apparent_temp", "Apparent Temp (°C)"),
        ("wet_bulb_temp", "Wet-Bulb (°C)"),
        ("relative_humidity", "Rel Humidity (%)"),
        ("aqi_overall", "Air Quality (AQI)"),
    ]
    radar_metrics = [c[0] for c in radar_candidates if c[0] in enriched_df.columns]

    if len(radar_metrics) >= 3 and len(locations) >= 2:
        radar_df = enriched_df.groupby("location_name")[radar_metrics].mean().reset_index()

        fig_radar = go.Figure()
        categories = [dict(radar_candidates).get(m, m) for m in radar_metrics]

        for _, row in radar_df.iterrows():
            loc = row["location_name"]
            values = [row[m] for m in radar_metrics]
            # close polygon
            values.append(values[0])
            cats_closed = categories + [categories[0]]

            fig_radar.add_trace(go.Scatterpolar(
                r=values,
                theta=cats_closed,
                fill="toself",
                name=loc,
            ))

        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=True,
            title="Multi-Indicator Microclimate Footprint",
            height=450,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # Missing Data Audit Across Locations
    st.markdown("---")
    st.subheader("🔍 Missing Data Completeness Audit")
    summary = DataCleaner.analyze_missing_values(enriched_df)
    if summary:
        audit_rows = []
        for col, s in summary.items():
            if col in numeric_metrics:
                audit_rows.append({
                    "Indicator": metric_labels.get(col, col),
                    "Valid Observations": s["valid_count"],
                    "Missing Observations": s["null_count"],
                    "Completeness (%)": round(100.0 - s["null_percent"], 1),
                })
        audit_df = pd.DataFrame(audit_rows)
        st.dataframe(audit_df, use_container_width=True)

