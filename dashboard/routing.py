"""
Dashboard Page: Temperature-Aware Routing
========================================
Asynchronous routing evaluation optimizing logistics and urban mobility
by balancing travel time with cumulative thermal exposure.
"""

import math
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from src.api.fortyguard_client import FortyGuardClient, FortyGuardAPIError
from src.database.db import DatabaseManager


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate straight-line distance in kilometers between two points."""
    r = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def render_routing_page(db: DatabaseManager):
    st.header("🚗 Temperature-Aware Urban Routing")
    st.markdown(
        "Evaluate route alternatives that minimize extreme heat exposure for pedestrians, "
        "active mobility, cold-chain transport, and outdoor workforce safety."
    )

    st.info(
        "📏 **Coverage Constraint:** FortyGuard enforces a **maximum straight-line distance of 200 km** "
        "between origin and destination coordinates within supported US coverage areas."
    )

    client = FortyGuardClient()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏁 Origin Coordinates")
        orig_lat = st.number_input("Origin Latitude", value=33.4484, format="%.4f", key="orig_lat")
        orig_lon = st.number_input("Origin Longitude", value=-112.0740, format="%.4f", key="orig_lon")
        st.caption("Default: Downtown Phoenix, AZ")

    with col2:
        st.subheader("🎯 Destination Coordinates")
        dest_lat = st.number_input("Destination Latitude", value=33.4255, format="%.4f", key="dest_lat")
        dest_lon = st.number_input("Destination Longitude", value=-111.9400, format="%.4f", key="dest_lon")
        st.caption("Default: Tempe / ASU Corridor, AZ")

    # Validate 200 km constraint
    dist_km = haversine_distance(orig_lat, orig_lon, dest_lat, dest_lon)
    if dist_km > 200.0:
        st.error(f"❌ Distance exceeds allowable limit: {dist_km:.1f} km (Max 200 km).")
        return
    else:
        st.success(f"✓ Straight-line route span: **{dist_km:.2f} km** (Within 200 km limit).")

    dep_time = st.text_input("Departure Time (ISO 8601 UTC)", value="2026-09-15T17:00:00Z")

    r_confirm = st.checkbox("Confirm Routing API credit consumption (~3,500 credits)", key="r_confirm_route")

    if st.button("🚀 Calculate Temperature-Aware Routes"):
        if not r_confirm:
            st.error("Please confirm credit consumption checkbox.")
        else:
            try:
                with st.spinner("Submitting asynchronous route optimization..."):
                    res = client.submit_routing(
                        origin_lat=orig_lat,
                        origin_lon=orig_lon,
                        dest_lat=dest_lat,
                        dest_lon=dest_lon,
                        departure_time=dep_time,
                    )
                st.success("Routing task submitted!")
                st.json(res)
            except Exception as e:
                st.warning(f"Note: {e} (Premium tier authorization required for live routing endpoint).")

    st.markdown("---")
    st.subheader("📊 Comparative Route Analysis (Thermal vs Duration Tradeoff)")

    # Demonstration Route Alternatives
    demo_routes = pd.DataFrame([
        {
            "Route Option": "Route A: Cool Corridor (Shaded Arterials)",
            "Distance (km)": 15.4,
            "Duration (mins)": 22.0,
            "Mean Thermal Exposure (°C)": 37.8,
            "Peak Heat Exposure (°C)": 39.5,
            "Thermal Stress Index": "Moderate",
        },
        {
            "Route Option": "Route B: Standard Highway (I-10 Corridor)",
            "Distance (km)": 13.8,
            "Duration (mins)": 18.0,
            "Mean Thermal Exposure (°C)": 43.2,
            "Peak Heat Exposure (°C)": 46.1,
            "Thermal Stress Index": "Severe Heat Sink",
        },
    ])

    st.dataframe(demo_routes, use_container_width=True)

    c_viz1, c_viz2 = st.columns(2)
    with c_viz1:
        fig_time = px.bar(
            demo_routes,
            x="Route Option",
            y="Duration (mins)",
            color="Route Option",
            title="Travel Time Comparison",
            color_discrete_sequence=["#2CA02C", "#1F77B4"],
        )
        st.plotly_chart(fig_time, use_container_width=True)

    with c_viz2:
        fig_heat = px.bar(
            demo_routes,
            x="Route Option",
            y="Mean Thermal Exposure (°C)",
            color="Mean Thermal Exposure (°C)",
            color_continuous_scale="Reds",
            title="Thermal Exposure (°C) Comparison",
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    st.success("💡 **Optimization Result:** Route A reduces cumulative thermal exposure by **5.4°C** with only a 4-minute travel delta.")

