"""
Dashboard Page: Environmental Analytics
=======================================
Interactive Plotly charts, thermal stress indicators, atmospheric distributions,
and correlation matrices for collected FortyGuard microclimate observations.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.database.db import DatabaseManager
from src.analytics.analysis import EnvironmentalAnalytics
from src.processing.cleaning import DataCleaner


def render_environmental_page(db: DatabaseManager):
    st.header("📈 Environmental Analytics & Microclimate Insights")

    raw_df = db.get_observations_df()
    if raw_df.empty:
        st.warning("⚠️ No observations recorded in the database yet. Please run data collection first.")
        return

    # Clean & enrich dataset
    clean_df, quality_audit = DataCleaner.clean_dataset(raw_df)
    enriched_df = EnvironmentalAnalytics.enrich_with_thermal_stress_indices(clean_df)

    # Sidebar / Filter options
    all_locations = sorted(enriched_df["location_name"].unique().tolist())
    selected_locs = st.multiselect(
        "Filter Locations",
        options=all_locations,
        default=all_locations,
        help="Select one or more locations to visualize",
    )

    if not selected_locs:
        st.info("Select at least one location above.")
        return

    filtered_df = enriched_df[enriched_df["location_name"].isin(selected_locs)].copy()

    # 1. Thermal Comparison
    st.subheader("🌡️ 1. Thermal Stress & Temperature Metrics")
    thermal_metrics = [
        col for col in ["reference_temp", "apparent_temp", "heat_index", "wet_bulb_temp"]
        if col in filtered_df.columns and filtered_df[col].notna().sum() > 0
    ]

    if thermal_metrics:
        melted_thermal = filtered_df.melt(
            id_vars=["location_name", "timestamp"],
            value_vars=thermal_metrics,
            var_name="Thermal Metric",
            value_name="Temperature (°C)",
        )
        label_map = {
            "reference_temp": "Reference Temp",
            "apparent_temp": "Apparent ('Feels Like')",
            "heat_index": "Heat Index",
            "wet_bulb_temp": "Wet-Bulb Temp",
        }
        melted_thermal["Thermal Metric"] = melted_thermal["Thermal Metric"].map(lambda x: label_map.get(x, x))

        fig_thermal = px.bar(
            melted_thermal,
            x="location_name",
            y="Temperature (°C)",
            color="Thermal Metric",
            barmode="group",
            title="Comparison of Reference vs Perceived (Apparent) & Wet-Bulb Temperatures",
            color_discrete_sequence=["#636EFA", "#EF553B", "#FFA15A", "#00CC96"],
        )
        fig_thermal.update_layout(height=420)
        st.plotly_chart(fig_thermal, use_container_width=True)

        # Derived Thermal Delta
        if "calc_thermal_delta" in filtered_df.columns and filtered_df["calc_thermal_delta"].notna().sum() > 0:
            st.markdown("##### 🔍 Thermal Comfort Delta (Apparent Temp − Reference Temp)")
            fig_delta = px.bar(
                filtered_df,
                x="location_name",
                y="calc_thermal_delta",
                color="calc_thermal_delta",
                color_continuous_scale="Reds",
                title="Microclimate Thermal Amplification (°C Above Ambient)",
                labels={"calc_thermal_delta": "Thermal Delta (°C)", "location_name": "Location"},
            )
            fig_delta.update_layout(height=350)
            st.plotly_chart(fig_delta, use_container_width=True)

    # 2. Atmospheric & Moisture
    st.markdown("---")
    st.subheader("💧 2. Atmospheric & Moisture Conditions")
    col_a, col_b = st.columns(2)

    with col_a:
        if "relative_humidity" in filtered_df.columns and filtered_df["relative_humidity"].notna().sum() > 0:
            fig_rh = px.bar(
                filtered_df,
                x="location_name",
                y="relative_humidity",
                color="relative_humidity",
                color_continuous_scale="Teal",
                title="Relative Humidity (%)",
                labels={"relative_humidity": "Humidity (%)"},
            )
            fig_rh.update_layout(height=350)
            st.plotly_chart(fig_rh, use_container_width=True)

    with col_b:
        if "cloud_cover" in filtered_df.columns and filtered_df["cloud_cover"].notna().sum() > 0:
            fig_cloud = px.bar(
                filtered_df,
                x="location_name",
                y="cloud_cover",
                title="Cloud Cover (Octas)",
                labels={"cloud_cover": "Cloud Cover (0-8)"},
                color_discrete_sequence=["#AB63FA"],
            )
            fig_cloud.update_layout(height=350)
            st.plotly_chart(fig_cloud, use_container_width=True)

    # 3. Air Quality Breakdown
    st.markdown("---")
    st.subheader("💨 3. Air Quality & Atmospheric Pollution")
    aqi_cols = [
        c for c in ["aqi_overall", "aqi_pm25", "aqi_pm10", "aqi_no2", "aqi_o3", "aqi_co", "aqi_so2"]
        if c in filtered_df.columns and filtered_df[c].notna().sum() > 0
    ]

    if aqi_cols:
        melted_aqi = filtered_df.melt(
            id_vars=["location_name"],
            value_vars=aqi_cols,
            var_name="Pollutant Metric",
            value_name="Index Value",
        )
        fig_aqi = px.bar(
            melted_aqi,
            x="location_name",
            y="Index Value",
            color="Pollutant Metric",
            barmode="group",
            title="US EPA Air Quality Index (AQI) Metrics",
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_aqi.update_layout(height=400)
        st.plotly_chart(fig_aqi, use_container_width=True)

    # 4. Solar Irradiance
    st.markdown("---")
    st.subheader("☀️ 4. Solar Irradiance (Clear-Sky Modeling)")
    solar_cols = [c for c in ["ghi", "dni", "dhi"] if c in filtered_df.columns and filtered_df[c].notna().sum() > 0]
    if solar_cols:
        melted_solar = filtered_df.melt(
            id_vars=["location_name"],
            value_vars=solar_cols,
            var_name="Component",
            value_name="Irradiance (W/m²)",
        )
        label_solar = {
            "ghi": "GHI (Global Horizontal)",
            "dni": "DNI (Direct Normal)",
            "dhi": "DHI (Diffuse Horizontal)",
        }
        melted_solar["Component"] = melted_solar["Component"].map(lambda x: label_solar.get(x, x))
        fig_solar = px.bar(
            melted_solar,
            x="location_name",
            y="Irradiance (W/m²)",
            color="Component",
            barmode="group",
            title="Solar Irradiance Flux Components (W/m²)",
            color_discrete_sequence=["#FFC107", "#FF9800", "#FF5722"],
        )
        fig_solar.update_layout(height=380)
        st.plotly_chart(fig_solar, use_container_width=True)

    # 5. Correlation Analysis
    st.markdown("---")
    st.subheader("🔗 5. Correlation Analysis")
    corr_df = EnvironmentalAnalytics.compute_correlation_matrix(filtered_df)
    if not corr_df.empty:
        fig_corr = px.imshow(
            corr_df,
            text_auto=True,
            aspect="auto",
            color_continuous_scale="RdBu_r",
            title="Pairwise Correlation Matrix of Environmental Indicators",
        )
        fig_corr.update_layout(height=480)
        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("Insufficient observation records to compute statistical correlation matrix.")

    # 6. Descriptive Statistics Table
    st.markdown("---")
    st.subheader("📑 6. Descriptive Statistics Summary")
    stats_df = EnvironmentalAnalytics.compute_descriptive_stats(filtered_df)
    if not stats_df.empty:
        st.dataframe(stats_df, use_container_width=True)

