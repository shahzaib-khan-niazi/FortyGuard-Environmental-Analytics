"""
Dashboard Page: Satellite and Street-View Semantic Segmentation
==============================================================
Evaluates overhead urban canopy and ground-level streetscape segmentation
to quantify building facades, vegetation, and impervious materials.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import date

from src.api.fortyguard_client import FortyGuardClient, FortyGuardAPIError
from src.database.db import DatabaseManager


def render_segmentation_page(db: DatabaseManager):
    st.header("🛰️ Spatial Semantic Segmentation (Satellite & Street-View)")
    st.markdown(
        "Semantic segmentation decomposes urban imagery into material classes "
        "(e.g., asphalt roads, building roofs, tree canopies, low vegetation, water). "
        "These metrics explain localized urban heat island formation."
    )

    st.info(
        "ℹ️ **Model Estimate & Imagery Disclaimer:** "
        "Segmentation class percentages are machine-learning estimates and not guaranteed ground truth. "
        "Satellite imagery capture dates reflect catalog availability and may not exactly match requested query dates."
    )

    client = FortyGuardClient()
    tab1, tab2 = st.tabs(["🛰️ Satellite Semantic Segmentation", "🏙️ Ground Street-View Segmentation"])

    # -------------------------------------------------------------------------
    # TAB 1: Satellite View
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("Satellite Land Cover Segmentation")
        st.caption("Available on API Premium plans (~14,400 credits per request).")

        col1, col2 = st.columns(2)
        with col1:
            s_lat = st.number_input("Target Latitude", value=33.4484, format="%.4f", key="s_lat")
            s_lon = st.number_input("Target Longitude", value=-112.0740, format="%.4f", key="s_lon")
        with col2:
            s_date = st.date_input("Imagery Date", value=date(2024, 7, 15), key="s_date")
            s_gran = st.selectbox("Tile Granularity", options=[60, 80, 100], index=2, key="s_gran")

        s_confirm = st.checkbox("Confirm satellite request credit consumption", key="s_confirm")
        if st.button("🚀 Analyze Satellite Land Cover"):
            if not s_confirm:
                st.error("Please confirm credit consumption checkbox.")
            else:
                try:
                    with st.spinner("Submitting satellite segmentation request..."):
                        res = client.submit_satellite(
                            latitude=s_lat,
                            longitude=s_lon,
                            start_date=s_date.strftime("%Y-%m-%d"),
                            granularity=s_gran,
                        )
                    st.success("Analysis complete!")
                    st.json(res)
                except Exception as e:
                    st.warning(f"Note: {e} (Premium tier authorization may be required for this endpoint).")

        st.markdown("---")
        st.markdown("##### 📊 Benchmark Demonstration: Phoenix Land Cover Profile")
        demo_sat = pd.DataFrame([
            {"Class": "Impervious Asphalt / Pavement", "Coverage (%)": 38.4, "Albedo": 0.12},
            {"Class": "Building Roofs", "Coverage (%)": 29.1, "Albedo": 0.20},
            {"Class": "Bare Soil / Desert Substrate", "Coverage (%)": 20.3, "Albedo": 0.35},
            {"Class": "Urban Tree Canopy", "Coverage (%)": 8.7, "Albedo": 0.18},
            {"Class": "Irrigated Turf / Low Vegetation", "Coverage (%)": 3.5, "Albedo": 0.22},
        ])
        fig_sat = px.pie(
            demo_sat,
            names="Class",
            values="Coverage (%)",
            title="Typical Overhead Urban Surface Segmentation (Phoenix Downtown)",
            color_discrete_sequence=px.colors.diverging.Portland,
        )
        st.plotly_chart(fig_sat, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 2: Street View
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Street-Level Facade & Sky-View Factor Analysis")
        st.caption("Available on API Premium plans (~8,600 credits per request).")

        c_a, c_b = st.columns(2)
        with c_a:
            sv_lat = st.number_input("Street Latitude", value=33.4484, format="%.4f", key="sv_lat")
            sv_lon = st.number_input("Street Longitude", value=-112.0740, format="%.4f", key="sv_lon")
        with c_b:
            v_angle = st.slider("Vertical Viewing Angle", min_value=-45, max_value=45, value=0)
            h_angle = st.slider("Horizontal Viewing Angle", min_value=-180, max_value=180, value=0)
            back_view = st.checkbox("Include 180° Rear Street View", value=False)

        sv_confirm = st.checkbox("Confirm street-view credit consumption", key="sv_confirm")
        if st.button("🚀 Analyze Street View Segmentation"):
            if not sv_confirm:
                st.error("Please confirm credit consumption checkbox.")
            else:
                try:
                    with st.spinner("Submitting street-view segmentation..."):
                        res = client.submit_streetview(
                            latitude=sv_lat,
                            longitude=sv_lon,
                            vertical_angle=v_angle,
                            horizontal_angle=h_angle,
                            back_view=back_view,
                        )
                    st.success("Street-view segmentation completed!")
                    st.json(res)
                except Exception as e:
                    st.warning(f"Note: {e} (Premium tier authorization may be required for this endpoint).")

        st.markdown("---")
        st.markdown("##### 📊 Benchmark Demonstration: Ground-Level Canyon Composition")
        demo_street = pd.DataFrame([
            {"Feature": "Visible Open Sky (Sky-View Factor)", "Percentage (%)": 42.0},
            {"Feature": "Building Facades & Walls", "Percentage (%)": 31.5},
            {"Feature": "Road Surface & Sidewalks", "Percentage (%)": 21.0},
            {"Feature": "Street Trees & Greenery", "Percentage (%)": 5.5},
        ])
        fig_street = px.bar(
            demo_street,
            x="Feature",
            y="Percentage (%)",
            color="Feature",
            title="Ground Perspective Urban Canyon Composition",
            color_discrete_sequence=px.colors.qualitative.Prism,
        )
        st.plotly_chart(fig_street, use_container_width=True)

