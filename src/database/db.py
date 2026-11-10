"""
Database Manager for FortyGuard Platform
========================================
Handles SQLite connection pooling, parameterized queries, schema creation,
and high-level CRUD operations for all entities in the FortyGuard ecosystem.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from src.database.schema import SCHEMA_SQL

logger = logging.getLogger("fortyguard.database")


class DatabaseManager:
    """Encapsulates SQLite database operations with thread safety and data integrity."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager.
        :param db_path: Path to SQLite database file. Defaults to data/fortyguard.db.
        """
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "fortyguard.db",
        )
        self.db_path = db_path or os.getenv("DATABASE_PATH", default_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a new SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Apply schema DDL to create tables and indexes."""
        try:
            with self.get_connection() as conn:
                conn.executescript(SCHEMA_SQL)
                conn.commit()
            logger.info("Database initialized successfully at %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize database: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Locations
    # -------------------------------------------------------------------------

    def upsert_location(
        self,
        name: str,
        latitude: float,
        longitude: float,
        elevation: Optional[float] = None,
        timezone: str = "UTC",
        state: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Insert or update a location and return its primary key ID."""
        sql = """
        INSERT INTO locations (name, latitude, longitude, elevation, timezone, state, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            elevation = COALESCE(excluded.elevation, locations.elevation),
            timezone = excluded.timezone,
            state = COALESCE(excluded.state, locations.state),
            notes = COALESCE(excluded.notes, locations.notes)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (name, latitude, longitude, elevation, timezone, state, notes))
            conn.commit()
            if cur.lastrowid and cur.lastrowid > 0:
                return cur.lastrowid
            # If updated an existing record:
            cur.execute("SELECT id FROM locations WHERE name = ?", (name,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_locations(self) -> List[Dict[str, Any]]:
        """Retrieve all locations."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM locations ORDER BY name ASC")
            return [dict(r) for r in cur.fetchall()]

    def get_location_by_id(self, location_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a location by ID."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_location_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a location by Name."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM locations WHERE name = ?", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    # -------------------------------------------------------------------------
    # Collection Jobs
    # -------------------------------------------------------------------------

    def create_job(self, job_type: str, parameters: Dict[str, Any], activity_id: Optional[str] = None) -> int:
        """Create a new collection job record."""
        sql = """
        INSERT INTO collection_jobs (job_type, status, parameters_json, activity_id)
        VALUES (?, 'RUNNING', ?, ?)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (job_type, json.dumps(parameters), activity_id))
            conn.commit()
            return cur.lastrowid

    def update_job_status(
        self,
        job_id: int,
        status: str,
        activity_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update job status and completion time."""
        sql = """
        UPDATE collection_jobs
        SET status = ?,
            activity_id = COALESCE(?, activity_id),
            error_message = ?,
            completed_at = CASE WHEN ? IN ('COMPLETED', 'FAILED') THEN CURRENT_TIMESTAMP ELSE completed_at END
        WHERE id = ?
        """
        with self.get_connection() as conn:
            conn.execute(sql, (status, activity_id, error_message, status, job_id))
            conn.commit()

    def get_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent collection jobs."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM collection_jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Environmental Observations
    # -------------------------------------------------------------------------

    def insert_environmental_observations(
        self,
        location_id: int,
        job_id: Optional[int],
        result_payload: Dict[str, Any],
        raw_response_str: str,
    ) -> int:
        """
        Parse and persist FortyGuard completed result data into environmental_observations table.
        Returns number of inserted rows.
        """
        metadata = result_payload.get("metadata", {})
        timestamps = metadata.get("timestamps", [])
        locations_data = result_payload.get("locations", [])
        if not locations_data:
            return 0

        # Usually 1 location returned for env_params
        loc_item = locations_data[0]
        params = loc_item.get("parameters", {})
        solar = loc_item.get("solar_irradiance", {})
        clear_sky = solar.get("clear_sky", {}) if isinstance(solar, dict) else {}

        ref_temp = loc_item.get("temperature")

        # Time range or timestamps
        n_points = len(timestamps)
        if n_points == 0:
            start_ts = metadata.get("time_range", {}).get("start", "1970-01-01T00:00:00Z")
            timestamps = [start_ts]
            n_points = 1

        sql = """
        INSERT INTO environmental_observations (
            location_id, job_id, timestamp, reference_temp,
            heat_index, apparent_temp, wet_bulb_temp, relative_humidity,
            precipitation, cloud_cover, aqi_overall, aqi_pm25, aqi_pm10,
            aqi_no2, aqi_co, aqi_o3, aqi_so2, methane_ppb, co2_ppm,
            ghi, dni, dhi, raw_response
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(location_id, timestamp) DO UPDATE SET
            reference_temp = COALESCE(excluded.reference_temp, environmental_observations.reference_temp),
            heat_index = COALESCE(excluded.heat_index, environmental_observations.heat_index),
            apparent_temp = COALESCE(excluded.apparent_temp, environmental_observations.apparent_temp),
            wet_bulb_temp = COALESCE(excluded.wet_bulb_temp, environmental_observations.wet_bulb_temp),
            relative_humidity = COALESCE(excluded.relative_humidity, environmental_observations.relative_humidity),
            precipitation = COALESCE(excluded.precipitation, environmental_observations.precipitation),
            cloud_cover = COALESCE(excluded.cloud_cover, environmental_observations.cloud_cover),
            aqi_overall = COALESCE(excluded.aqi_overall, environmental_observations.aqi_overall),
            aqi_pm25 = COALESCE(excluded.aqi_pm25, environmental_observations.aqi_pm25),
            aqi_pm10 = COALESCE(excluded.aqi_pm10, environmental_observations.aqi_pm10),
            aqi_no2 = COALESCE(excluded.aqi_no2, environmental_observations.aqi_no2),
            aqi_co = COALESCE(excluded.aqi_co, environmental_observations.aqi_co),
            aqi_o3 = COALESCE(excluded.aqi_o3, environmental_observations.aqi_o3),
            aqi_so2 = COALESCE(excluded.aqi_so2, environmental_observations.aqi_so2),
            methane_ppb = COALESCE(excluded.methane_ppb, environmental_observations.methane_ppb),
            co2_ppm = COALESCE(excluded.co2_ppm, environmental_observations.co2_ppm),
            ghi = COALESCE(excluded.ghi, environmental_observations.ghi),
            dni = COALESCE(excluded.dni, environmental_observations.dni),
            dhi = COALESCE(excluded.dhi, environmental_observations.dhi),
            raw_response = excluded.raw_response
        """

        def _get_val(param_key: str, idx: int) -> Optional[float]:
            val_list = params.get(param_key)
            if isinstance(val_list, list) and idx < len(val_list):
                return val_list[idx]
            if isinstance(val_list, (int, float)):
                return float(val_list)
            return None

        inserted_count = 0
        with self.get_connection() as conn:
            cur = conn.cursor()
            for i, ts in enumerate(timestamps):
                h_idx = _get_val("heat_index_celsius", i)
                app_temp = _get_val("apparent_temperature_celsius", i)
                wb_temp = _get_val("wet_bulb_temperature_celsius", i)
                rel_hum = _get_val("relative_humidity_percent", i)
                precip = _get_val("precipitation_mm", i)
                cloud = _get_val("cloud_cover_octas", i)

                aqi_tot = _get_val("air_quality:idx", i)
                aqi_pm25 = _get_val("air_quality_pm2p5:idx", i)
                aqi_pm10 = _get_val("air_quality_pm10:idx", i)
                aqi_no2 = _get_val("air_quality_no2:idx", i)
                aqi_co = _get_val("aqi_us_co", i)
                aqi_o3 = _get_val("air_quality_o3:idx", i)
                aqi_so2 = _get_val("air_quality_so2:idx", i)
                methane = _get_val("methane_ppb", i)
                co2 = _get_val("co2_ppm", i)

                ghi_val = clear_sky.get("ghi") if i == 0 else None
                dni_val = clear_sky.get("dni") if i == 0 else None
                dhi_val = clear_sky.get("dhi") if i == 0 else None

                cur.execute(sql, (
                    location_id, job_id, ts, ref_temp,
                    h_idx, app_temp, wb_temp, rel_hum,
                    precip, cloud, aqi_tot, aqi_pm25, aqi_pm10,
                    aqi_no2, aqi_co, aqi_o3, aqi_so2, methane, co2,
                    ghi_val, dni_val, dhi_val, raw_response_str
                ))
                inserted_count += 1
            conn.commit()

        # Update location elevation if returned
        elevation = loc_item.get("elevation")
        tz_name = metadata.get("timezone")
        if elevation is not None or tz_name:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE locations SET elevation = COALESCE(?, elevation), timezone = COALESCE(?, timezone) WHERE id = ?",
                    (elevation, tz_name, location_id)
                )
                conn.commit()

        return inserted_count

    def get_observations_df(
        self,
        location_ids: Optional[List[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Query environmental observations and return a structured Pandas DataFrame
        joined with location metadata.
        """
        sql = """
        SELECT
            o.id AS observation_id,
            o.timestamp,
            l.id AS location_id,
            l.name AS location_name,
            l.latitude,
            l.longitude,
            l.elevation,
            l.state,
            o.reference_temp,
            o.heat_index,
            o.apparent_temp,
            o.wet_bulb_temp,
            o.relative_humidity,
            o.precipitation,
            o.cloud_cover,
            o.aqi_overall,
            o.aqi_pm25,
            o.aqi_pm10,
            o.aqi_no2,
            o.aqi_co,
            o.aqi_o3,
            o.aqi_so2,
            o.methane_ppb,
            o.co2_ppm,
            o.ghi,
            o.dni,
            o.dhi,
            o.created_at
        FROM environmental_observations o
        JOIN locations l ON o.location_id = l.id
        WHERE 1=1
        """
        params: List[Any] = []
        if location_ids:
            placeholders = ",".join(["?"] * len(location_ids))
            sql += f" AND o.location_id IN ({placeholders})"
            params.extend(location_ids)
        if start_date:
            sql += " AND o.timestamp >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND o.timestamp <= ?"
            params.append(end_date)

        sql += " ORDER BY o.timestamp ASC, l.name ASC"

        with self.get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        return df

    # -------------------------------------------------------------------------
    # Heatmaps
    # -------------------------------------------------------------------------

    def save_heatmap_activity(
        self,
        activity_id: str,
        status: str,
        polygon_geojson: Dict[str, Any],
        start_date: str,
        granularity: int = 100,
        analytic_type: str = "tcm",
        map_type: str = "tcm",
        raw_response: Optional[str] = None,
    ) -> int:
        """Save a new heatmap submission."""
        sql = """
        INSERT INTO heatmap_activities (
            activity_id, status, polygon_geojson, start_date,
            granularity, analytic_type, map_type, raw_response
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            raw_response = COALESCE(excluded.raw_response, heatmap_activities.raw_response),
            completed_at = CASE WHEN excluded.status = 'Completed' THEN CURRENT_TIMESTAMP ELSE heatmap_activities.completed_at END
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (
                activity_id, status, json.dumps(polygon_aoi := polygon_geojson),
                start_date, granularity, analytic_type, map_type, raw_response
            ))
            conn.commit()
            cur.execute("SELECT id FROM heatmap_activities WHERE activity_id = ?", (activity_id,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def save_heatmap_results(self, heatmap_id: int, result_payload: Dict[str, Any]) -> int:
        """Parse GeoJSON features from heatmap response and save into heatmap_results."""
        map_data = result_payload.get("map_data", {})
        features = map_data.get("features", [])
        if not features:
            return 0

        sql = """
        INSERT INTO heatmap_results (
            heatmap_id, tile_id, avg_temp, min_temp, max_temp,
            geometry_geojson, properties_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        count = 0
        with self.get_connection() as conn:
            cur = conn.cursor()
            # Clear previous results for this heatmap if re-saving
            cur.execute("DELETE FROM heatmap_results WHERE heatmap_id = ?", (heatmap_id,))
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                tile_id = props.get("tile_id", count)
                avg_t = props.get("average_temperature")
                min_t = props.get("min_temperature")
                max_t = props.get("max_temperature")

                cur.execute(sql, (
                    heatmap_id,
                    tile_id,
                    avg_t,
                    min_t,
                    max_t,
                    json.dumps(geom),
                    json.dumps(props),
                ))
                count += 1
            conn.commit()
        return count

    def get_heatmaps(self) -> List[Dict[str, Any]]:
        """Get all heatmap activities."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM heatmap_activities ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_heatmap_tiles(self, heatmap_id: int) -> List[Dict[str, Any]]:
        """Get tiles for a specific heatmap."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM heatmap_results WHERE heatmap_id = ?", (heatmap_id,))
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Heat Intelligence Reports
    # -------------------------------------------------------------------------

    def save_heat_intelligence_report(
        self,
        activity_id: str,
        status: str,
        latitude: float,
        longitude: float,
        temperature: float,
        date: str,
        analyses: List[str],
        download_link: Optional[str] = None,
        raw_response: Optional[str] = None,
    ) -> int:
        """Save or update Heat Intelligence report activity."""
        sql = """
        INSERT INTO heat_intelligence_reports (
            activity_id, status, latitude, longitude, temperature,
            date, analyses_json, download_link, raw_response,
            completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'Completed' THEN CURRENT_TIMESTAMP ELSE NULL END)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            download_link = COALESCE(excluded.download_link, heat_intelligence_reports.download_link),
            raw_response = COALESCE(excluded.raw_response, heat_intelligence_reports.raw_response),
            completed_at = CASE WHEN excluded.status = 'Completed' THEN CURRENT_TIMESTAMP ELSE heat_intelligence_reports.completed_at END
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (
                activity_id, status, latitude, longitude, temperature,
                date, json.dumps(analyses), download_link, raw_response, status
            ))
            conn.commit()
            cur.execute("SELECT id FROM heat_intelligence_reports WHERE activity_id = ?", (activity_id,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_heat_intelligence_reports(self) -> List[Dict[str, Any]]:
        """Get all heat intelligence reports."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM heat_intelligence_reports ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Segmentation (Satellite & Street View)
    # -------------------------------------------------------------------------

    def save_satellite_segmentation(
        self,
        activity_id: Optional[str],
        status: str,
        latitude: float,
        longitude: float,
        date_time: Dict[str, Any],
        granularity: int = 100,
        classes: Optional[Dict[str, Any]] = None,
        imagery_metadata: Optional[Dict[str, Any]] = None,
        raw_response: Optional[str] = None,
    ) -> int:
        """Save Satellite segmentation record."""
        sql = """
        INSERT INTO satellite_segmentation (
            activity_id, status, latitude, longitude, date_time_json,
            granularity, classes_json, imagery_metadata_json, raw_response
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (
                activity_id, status, latitude, longitude, json.dumps(date_time),
                granularity, json.dumps(classes or {}), json.dumps(imagery_metadata or {}), raw_response
            ))
            conn.commit()
            return cur.lastrowid

    def get_satellite_segmentations(self) -> List[Dict[str, Any]]:
        """Get all satellite segmentation records."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM satellite_segmentation ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]

    def save_street_view_segmentation(
        self,
        activity_id: Optional[str],
        status: str,
        latitude: float,
        longitude: float,
        vertical_angle: float = 0.0,
        horizontal_angle: float = 0.0,
        back_view: bool = False,
        classes: Optional[Dict[str, Any]] = None,
        raw_response: Optional[str] = None,
    ) -> int:
        """Save Street View segmentation record."""
        sql = """
        INSERT INTO street_view_segmentation (
            activity_id, status, latitude, longitude,
            vertical_angle, horizontal_angle, back_view,
            classes_json, raw_response
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (
                activity_id, status, latitude, longitude,
                vertical_angle, horizontal_angle, 1 if back_view else 0,
                json.dumps(classes or {}), raw_response
            ))
            conn.commit()
            return cur.lastrowid

    def get_street_view_segmentations(self) -> List[Dict[str, Any]]:
        """Get all street view segmentation records."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM street_view_segmentation ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Routing Activities
    # -------------------------------------------------------------------------

    def save_routing_activity(
        self,
        activity_id: str,
        status: str,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: str,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        raw_response: Optional[str] = None,
    ) -> int:
        """Save or update routing activity."""
        sql = """
        INSERT INTO routing_activities (
            activity_id, status, origin_lat, origin_lon,
            dest_lat, dest_lon, departure_time,
            alternatives_json, metrics_json, raw_response
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            alternatives_json = COALESCE(excluded.alternatives_json, routing_activities.alternatives_json),
            metrics_json = COALESCE(excluded.metrics_json, routing_activities.metrics_json),
            raw_response = COALESCE(excluded.raw_response, routing_activities.raw_response)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (
                activity_id, status, origin_lat, origin_lon,
                dest_lat, dest_lon, departure_time,
                json.dumps(alternatives or []), json.dumps(metrics or {}), raw_response
            ))
            conn.commit()
            cur.execute("SELECT id FROM routing_activities WHERE activity_id = ?", (activity_id,))
            row = cur.fetchone()
            return row["id"] if row else 0

    def get_routing_activities(self) -> List[Dict[str, Any]]:
        """Get all routing activities."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM routing_activities ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Telemetry & Request Logging
    # -------------------------------------------------------------------------

    def log_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        duration_ms: float = 0.0,
        is_error: bool = False,
        error_message: Optional[str] = None,
    ) -> int:
        """Log API request performance and status."""
        sql = """
        INSERT INTO api_request_logs (
            endpoint, method, status_code, duration_ms, is_error, error_message
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (
                endpoint, method, status_code, duration_ms, 1 if is_error else 0, error_message
            ))
            conn.commit()
            return cur.lastrowid

    # -------------------------------------------------------------------------
    # Platform KPI Summary
    # -------------------------------------------------------------------------

    def get_platform_overview_metrics(self) -> Dict[str, Any]:
        """Fetch consolidated KPIs for overview dashboard."""
        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) AS c FROM locations")
            total_locations = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM environmental_observations")
            total_observations = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM collection_jobs WHERE status = 'COMPLETED'")
            completed_jobs = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM collection_jobs WHERE status = 'FAILED'")
            failed_jobs = cur.fetchone()["c"]

            cur.execute("SELECT MAX(timestamp) AS latest FROM environmental_observations")
            latest_timestamp = cur.fetchone()["latest"]

            cur.execute("SELECT COUNT(*) AS c FROM heatmap_activities")
            total_heatmaps = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM heat_intelligence_reports")
            total_reports = cur.fetchone()["c"]

            # Count non-null indicators
            indicators = []
            cur.execute("PRAGMA table_info(environmental_observations)")
            cols = [col["name"] for col in cur.fetchall()]
            check_cols = [
                "apparent_temp", "heat_index", "wet_bulb_temp", "relative_humidity",
                "precipitation", "cloud_cover", "aqi_overall", "aqi_pm25", "aqi_pm10",
                "aqi_no2", "aqi_co", "aqi_o3", "aqi_so2", "ghi"
            ]
            for col in check_cols:
                if col in cols:
                    cur.execute(f"SELECT COUNT(*) AS c FROM environmental_observations WHERE {col} IS NOT NULL")
                    if cur.fetchone()["c"] > 0:
                        indicators.append(col)

            return {
                "total_locations": total_locations,
                "total_observations": total_observations,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "latest_timestamp": latest_timestamp or "No data collected yet",
                "available_indicators": indicators,
                "total_heatmaps": total_heatmaps,
                "total_reports": total_reports,
            }

