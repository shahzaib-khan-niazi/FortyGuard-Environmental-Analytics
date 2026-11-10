"""
FortyGuard Environmental Intelligence Platform
==============================================
Main Streamlit Application Entrypoint.
Orchestrates multi-page navigation, styling, session state, and database connections.
"""

import os
import streamlit as st
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

from src.database.db import DatabaseManager
from src.api.fortyguard_client import FortyGuardClient

# Dashboard page renderers
from dashboard.overview import render_overview_page
from dashboard.collection import render_collection_page
from dashboard.environmental import render_environmental_page
from dashboard.locations import render_locations_page
from dashboard.heat_intelligence import render_heat_intelligence_page
from dashboard.segmentation import render_segmentation_page
from dashboard.routing import render_routing_page
from dashboard.explorer import render_explorer_page

# -----------------------------------------------------------------------------
# Streamlit Application Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="FortyGuard Environmental Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Portfolio Theme Styling
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 4px solid #1E88E5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .sidebar-brand {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0.5rem;
    }
    .status-badge-ok {
        color: #2E7D32;
        background-color: #E8F5E9;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_database_manager() -> DatabaseManager:
    """Singleton database manager instance."""
    return DatabaseManager()


def check_api_status() -> bool:
    """Verify if API key is present."""
    api_key = os.getenv("FORTYGUARD_API_KEY")
    if not api_key:
        try:
            if "FORTYGUARD_API_KEY" in st.secrets:
                api_key = st.secrets["FORTYGUARD_API_KEY"]
        except Exception:
            pass
    return bool(api_key and len(api_key) > 5)


def main():
    db = get_database_manager()
    api_ready = check_api_status()

    # -------------------------------------------------------------------------
    # Sidebar Navigation & Telemetry
    # -------------------------------------------------------------------------
    with st.sidebar:
        st.markdown("<div class='sidebar-brand'>🌍 FortyGuard Platform</div>", unsafe_allow_html=True)
        st.caption("Environmental Intelligence & Analytics Suite")

        if api_ready:
            st.markdown(
                "<span class='status-badge-ok'>● API Key Configured</span>",
                unsafe_allow_html=True,
            )
        else:
            st.error("⚠️ API Key Missing in .env")

        st.markdown("---")
        st.subheader("Navigation")
        pages = {
            "🌐 Overview": render_overview_page,
            "🛰️ Data Collection": render_collection_page,
            "📈 Environmental Analytics": render_environmental_page,
            "🏙️ Location Comparison": render_locations_page,
            "🔥 Heat Intelligence & Heatmaps": render_heat_intelligence_page,
            "🗺️ Satellite & Street View": render_segmentation_page,
            "🚗 Temperature-Aware Routing": render_routing_page,
            "🗄️ Dataset Explorer & Exports": render_explorer_page,
        }

        selected_page = st.radio(
            "Select Module",
            options=list(pages.keys()),
            index=0,
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### 📌 Portfolio Metadata")
        st.caption(
            "**Engine:** Python 3.11 / Streamlit\n"
            "**API:** FortyGuard Enterprise v1\n"
            "**Storage:** SQLite (ACID compliant)\n"
            "**Coverage:** Supported US Regions\n"
            "**Architecture:** Asynchronous polling, caching, data engineering."
        )

    # -------------------------------------------------------------------------
    # Render Selected Page
    # -------------------------------------------------------------------------
    page_func = pages[selected_page]
    page_func(db)


if __name__ == "__main__":
    main()

