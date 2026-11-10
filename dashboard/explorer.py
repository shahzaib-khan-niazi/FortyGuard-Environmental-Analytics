"""
Dashboard Page: Dataset Explorer & Multi-Format Exporter
========================================================
Interactive record search, raw vs cleaned dataset inspection,
missingness and outlier auditing, and direct CSV/Excel/JSON downloads.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from src.database.db import DatabaseManager
from src.processing.cleaning import DataCleaner
from src.analytics.analysis import EnvironmentalAnalytics
from src.exports.export import DataExporter


def render_explorer_page(db: DatabaseManager):
    st.header("🗄️ Dataset Explorer & Multi-Format Exporter")
    st.markdown(
        "Inspect, filter, audit, and download raw and processed environmental observations. "
        "Supports CSV, JSON, and comprehensive multi-tab Microsoft Excel workbooks."
    )

    raw_df = db.get_observations_df()
    if raw_df.empty:
        st.warning("⚠️ No observations found in the database. Please run collection first.")
        return

    exporter = DataExporter(db=db)
    clean_df, quality_audit = DataCleaner.clean_dataset(raw_df)
    enriched_df = EnvironmentalAnalytics.enrich_with_thermal_stress_indices(clean_df)

    # -------------------------------------------------------------------------
    # Filters
    # -------------------------------------------------------------------------
    st.subheader("🔍 Filter & Query Criteria")
    f_col1, f_col2, f_col3 = st.columns(3)

    with f_col1:
        locations_available = sorted(raw_df["location_name"].unique().tolist())
        selected_locations = st.multiselect(
            "Filter by Location",
            options=locations_available,
            default=locations_available,
        )

    with f_col2:
        search_query = st.text_input("Search Text (Name or State)", placeholder="e.g. Phoenix, AZ")

    with f_col3:
        view_mode = st.radio(
            "Dataset View Mode",
            options=["Enriched & Cleaned Data", "Raw Database Observations"],
            horizontal=True,
        )

    # Apply filters
    display_df = enriched_df if view_mode == "Enriched & Cleaned Data" else raw_df

    if selected_locations:
        display_df = display_df[display_df["location_name"].isin(selected_locations)]

    if search_query:
        mask = (
            display_df["location_name"].str.contains(search_query, case=False, na=False)
            | display_df["state"].str.contains(search_query, case=False, na=False)
        )
        display_df = display_df[mask]

    st.write(f"Showing **{len(display_df)} of {len(raw_df)}** records.")

    # -------------------------------------------------------------------------
    # Data Table View
    # -------------------------------------------------------------------------
    st.dataframe(display_df, use_container_width=True)

    # -------------------------------------------------------------------------
    # Data Quality & Outlier Audit
    # -------------------------------------------------------------------------
    with st.expander("📊 Data Quality, Missingness & Outlier Audit Report"):
        q_tab1, q_tab2 = st.tabs(["Missing Values Summary", "Outlier Flagging (IQR)"])

        with q_tab1:
            missing_dict = quality_audit.get("missing_summary", {})
            if missing_dict:
                q_rows = []
                for col, s in missing_dict.items():
                    q_rows.append({
                        "Column": col,
                        "Valid Values": s["valid_count"],
                        "Null Values": s["null_count"],
                        "Missing (%)": s["null_percent"],
                    })
                st.dataframe(pd.DataFrame(q_rows), use_container_width=True)

        with q_tab2:
            outlier_dict = quality_audit.get("outlier_summary", {})
            if outlier_dict:
                o_rows = []
                for col, s in outlier_dict.items():
                    o_rows.append({
                        "Metric": col,
                        "Lower Bound (Q1 - 1.5*IQR)": s["lower_bound"],
                        "Upper Bound (Q3 + 1.5*IQR)": s["upper_bound"],
                        "Outlier Count": s["outlier_count"],
                    })
                st.dataframe(pd.DataFrame(o_rows), use_container_width=True)

    # -------------------------------------------------------------------------
    # Direct Downloads
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📥 Export Datasets")
    st.markdown("Download active filtered records in your desired format:")

    exp_col1, exp_col2, exp_col3 = st.columns(3)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV Download
    csv_bytes = exporter.export_csv_bytes(display_df)
    exp_col1.download_button(
        label="📄 Download CSV",
        data=csv_bytes,
        file_name=f"fortyguard_observations_{timestamp_str}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # JSON Download
    json_bytes = exporter.export_json_bytes(display_df)
    exp_col2.download_button(
        label="🌐 Download JSON",
        data=json_bytes,
        file_name=f"fortyguard_observations_{timestamp_str}.json",
        mime="application/json",
        use_container_width=True,
    )

    # Multi-Sheet Excel Download
    excel_bytes = exporter.export_excel_bytes(observations_df=display_df)
    exp_col3.download_button(
        label="📊 Download Multi-Sheet Excel (.xlsx)",
        data=excel_bytes,
        file_name=f"fortyguard_intelligence_workbook_{timestamp_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.caption("ℹ️ Multi-sheet Excel workbook contains: Observations, Locations, Jobs, Heatmap Results, Reports, and Data Quality Audit sheets.")

