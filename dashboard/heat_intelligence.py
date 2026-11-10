"""
Dashboard Page: Heat Intelligence & Thermal Heatmaps
===================================================
Provides asynchronous job management, GeoJSON thermal tile visualization,
and Heat Intelligence report generation with temporary PDF download handling.
"""

import json
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from src.api.fortyguard_client import FortyGuardClient, FortyGuardAPIError
from src.database.db import DatabaseManager


def render_heat_intelligence_page(db: DatabaseManager):
    st.header("🔥 Heat Intelligence & High-Resolution Thermal Mapping")
    st.markdown(
        "Generate multi-dimensional intelligence reports and high-resolution thermal GeoJSON heatmaps "
        "powered by FortyGuard's Large Temperature Models (LTMs)."
    )

    client = FortyGuardClient()

    tab1, tab2, tab3 = st.tabs(["🗺️ Thermal Heatmaps", "📄 Heat Intelligence Reports", "📋 Active Task Status"])

    # -------------------------------------------------------------------------
    # TAB 1: Thermal Heatmaps
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("High-Resolution Thermal Heatmap")
        st.info(
            "Heatmaps generate micro-scale GeoJSON thermal polygon tiles (down to 60-100m resolution) "
            "over a defined polygon area of interest."
        )

        # Existing saved heatmaps
        existing_heatmaps = db.get_heatmaps()
        if existing_heatmaps:
            st.markdown("##### 📍 Explore Saved Thermal Heatmaps")
            map_options = {h["id"]: f"Activity: {h['activity_id'][:8]}... ({h['start_date']}, Status: {h['status']})" for h in existing_heatmaps}
            selected_map_id = st.selectbox("Select Heatmap", options=list(map_options.keys()), format_func=lambda x: map_options[x])

            tiles = db.get_heatmap_tiles(selected_map_id)
            if tiles:
                tile_df = pd.DataFrame(tiles)
                st.write(f"Loaded **{len(tiles)} thermal grid tiles**.")

                col_stat1, col_stat2, col_stat3 = st.columns(3)
                col_stat1.metric("Average Surface Temp", f"{tile_df['avg_temp'].mean():.2f} °C")
                col_stat2.metric("Min Grid Temp", f"{tile_df['min_temp'].min():.2f} °C")
                col_stat3.metric("Max Grid Temp", f"{tile_df['max_temp'].max():.2f} °C")

                # Parse polygon centroids for visualization
                coords_list = []
                for _, r in tile_df.iterrows():
                    try:
                        geom = json.loads(r["geometry_geojson"])
                        # GeoJSON coordinates are [[[lon, lat], ...]]
                        ring = geom["coordinates"][0]
                        avg_lon = sum(p[0] for p in ring) / len(ring)
                        avg_lat = sum(p[1] for p in ring) / len(ring)
                        coords_list.append({
                            "tile_id": r["tile_id"],
                            "lat": avg_lat,
                            "lon": avg_lon,
                            "avg_temp": r["avg_temp"],
                            "min_temp": r["min_temp"],
                            "max_temp": r["max_temp"],
                        })
                    except Exception:
                        pass

                if coords_list:
                    tile_viz_df = pd.DataFrame(coords_list)
                    fig_map = px.scatter_mapbox(
                        tile_viz_df,
                        lat="lat",
                        lon="lon",
                        color="avg_temp",
                        size="avg_temp",
                        color_continuous_scale="Turbo",
                        hover_data=["tile_id", "min_temp", "max_temp"],
                        zoom=13,
                        title="Thermal Grid Resolution (Phoenix Microclimate Distribution)",
                    )
                    fig_map.update_layout(
                        mapbox_style="carto-positron",
                        margin=dict(l=0, r=0, t=30, b=0),
                        height=500,
                    )
                    st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("---")
        with st.expander("🚀 Request New Asynchronous Heatmap"):
            st.warning("⚠️ **Credit Notice:** Heatmap generation consumes significant credits. Confirmation required.")
            h_date = st.date_input("Heatmap Date", value=date(2024, 7, 15), key="h_date")
            h_time = st.selectbox("Time (24h)", options=[f"{h:02d}:00" for h in range(24)], index=14, key="h_time")
            h_gran = st.selectbox("Spatial Granularity (Meters)", options=[60, 80, 100], index=2, key="h_gran")
            h_analytic = st.selectbox("Analytic Type", options=["tcm", "time_of_measure", "exceedance", "persistence"], key="h_analytic")
            h_map_type = st.selectbox("Map Type", options=["bm", "tcm", "tccm"], key="h_map_type")

            # Demo polygon: Phoenix Downtown
            default_geojson = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-112.08, 33.44],
                        [-112.07, 33.44],
                        [-112.07, 33.45],
                        [-112.08, 33.45],
                        [-112.08, 33.44],
                    ]
                ]
            }
            aoi_str = st.text_area("GeoJSON Polygon AOI", value=json.dumps(default_geojson, indent=2), height=150)
            h_confirm = st.checkbox("Confirm API Credit consumption for Heatmap generation", key="h_confirm")

            if st.button("Submit Heatmap Request"):
                if not h_confirm:
                    st.error("Please confirm API credit consumption checkbox.")
                else:
                    try:
                        aoi_dict = json.loads(aoi_str)
                        with st.spinner("Submitting heatmap to FortyGuard..."):
                            res = client.submit_heatmap(
                                polygon_aoi=aoi_dict,
                                start_date=h_date.strftime("%Y-%m-%d"),
                                start_time=h_time,
                                granularity=h_gran,
                                analytic_types=h_analytic,
                                map_type=h_map_type,
                            )
                        act_id = res.get("data", {}).get("activity_id")
                        db.save_heatmap_activity(
                            activity_id=act_id,
                            status="Processing",
                            polygon_geojson=aoi_dict,
                            start_date=h_date.strftime("%Y-%m-%d"),
                            granularity=h_gran,
                            analytic_type=h_analytic,
                            map_type=h_map_type,
                            raw_response=json.dumps(res),
                        )
                        st.success(f"Heatmap task queued successfully! Activity ID: `{act_id}`")
                    except Exception as e:
                        st.error(f"Error submitting heatmap: {e}")

    # -------------------------------------------------------------------------
    # TAB 2: Heat Intelligence Reports
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Multi-Dimensional Heat Intelligence Reports")
        st.markdown(
            "Compile comprehensive PDF intelligence dossiers evaluating spatial and temporal thermal impacts "
            "across five domains: Geographic, Environmental, Urban, Events, and Anthropogenic."
        )

        existing_reports = db.get_heat_intelligence_reports()
        if existing_reports:
            st.markdown("##### 📚 Generated Intelligence Reports")
            for rep in existing_reports:
                st.write(
                    f"• **Report `{rep['activity_id'][:8]}...`** — Date: {rep['date']} | Status: `{rep['status']}`"
                )
                if rep.get("download_link"):
                    st.markdown(f"📥 [Download Generated PDF Report]({rep['download_link']})")
            st.markdown("---")

        with st.expander("📝 Generate New Intelligence Dossier"):
            st.warning("⚠️ **Premium Credit Notice:** Heat Intelligence report compilation costs ~8,600 credits.")
            r_lat = st.number_input("Target Latitude", value=33.4484, format="%.4f", key="r_lat")
            r_lon = st.number_input("Target Longitude", value=-112.0740, format="%.4f", key="r_lon")
            r_temp = st.number_input("Local Temperature (°F or °C context)", value=104.5, key="r_temp")
            r_date = st.date_input("Analysis Date", value=date(2024, 7, 15), key="r_date")
            r_analyses = st.multiselect(
                "Domains to Evaluate",
                options=["geographic", "environmental", "urban", "events", "anthropogenic"],
                default=["geographic", "environmental", "urban", "events", "anthropogenic"],
            )
            r_confirm = st.checkbox("Confirm API Credit consumption for Heat Intelligence report", key="r_confirm")

            if st.button("Compile Heat Intelligence Report"):
                if not r_confirm:
                    st.error("Please confirm credit consumption checkbox.")
                else:
                    try:
                        with st.spinner("Submitting report job..."):
                            res = client.submit_heat_intelligence(
                                latitude=r_lat,
                                longitude=r_lon,
                                temperature=r_temp,
                                date=r_date.strftime("%Y-%m-%d"),
                                analysis=r_analyses,
                            )
                        act_id = res.get("data", {}).get("activity_id")
                        db.save_heat_intelligence_report(
                            activity_id=act_id,
                            status="Processing",
                            latitude=r_lat,
                            longitude=r_lon,
                            temperature=r_temp,
                            date=r_date.strftime("%Y-%m-%d"),
                            analyses=r_analyses,
                            raw_response=json.dumps(res),
                        )
                        st.success(f"Report task submitted! Activity ID: `{act_id}`. Poll status in Tab 3.")
                    except Exception as e:
                        st.error(f"Submission failed: {e}")

    # -------------------------------------------------------------------------
    # TAB 3: Active Task Polling
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Asynchronous Task Polling Tool")
        task_id_input = st.text_input("Enter Activity ID to Check Status", placeholder="e.g. 3b20997a-72bc-4014-8407-0779b5d7867d")
        if st.button("🔍 Check Task Status"):
            if not task_id_input:
                st.warning("Please provide an Activity ID.")
            else:
                try:
                    with st.spinner("Querying status endpoint..."):
                        status_res = client.check_status(task_id_input.strip())
                    st.json(status_res)
                    task_status = status_res.get("data", {}).get("status", "Unknown")
                    if task_status.lower() == "completed":
                        st.success("Activity is Completed!")
                        result_obj = status_res.get("data", {}).get("result", {})
                        if "download_link" in result_obj:
                            st.markdown(f"📥 [Download Report Link]({result_obj['download_link']})")
                except Exception as e:
                    st.error(f"Status check failed: {e}")

