"""
Database Schema Definition for FortyGuard Environmental Intelligence Platform
==============================================================================
Defines the SQLite DDL statements and table schemas for structured storage
of locations, observations, async jobs, analytics, and request telemetry.
"""

SCHEMA_SQL = """
-- 1. Locations Table
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    elevation REAL,
    timezone TEXT DEFAULT 'UTC',
    state TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_locations_coords ON locations(latitude, longitude);

-- 2. Collection Jobs Table
CREATE TABLE IF NOT EXISTS collection_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL, -- 'env_params', 'heatmap', 'heat_intelligence', etc.
    status TEXT NOT NULL,   -- 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    activity_id TEXT,
    parameters_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON collection_jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_activity_id ON collection_jobs(activity_id);

-- 3. Environmental Observations Table
CREATE TABLE IF NOT EXISTS environmental_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    job_id INTEGER,
    timestamp TEXT NOT NULL,
    reference_temp REAL,
    heat_index REAL,
    apparent_temp REAL,
    wet_bulb_temp REAL,
    relative_humidity REAL,
    precipitation REAL,
    cloud_cover REAL,
    aqi_overall REAL,
    aqi_pm25 REAL,
    aqi_pm10 REAL,
    aqi_no2 REAL,
    aqi_co REAL,
    aqi_o3 REAL,
    aqi_so2 REAL,
    methane_ppb REAL,
    co2_ppm REAL,
    ghi REAL,
    dni REAL,
    dhi REAL,
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(location_id) REFERENCES locations(id) ON DELETE CASCADE,
    FOREIGN KEY(job_id) REFERENCES collection_jobs(id) ON DELETE SET NULL,
    UNIQUE(location_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_obs_location ON environmental_observations(location_id);
CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON environmental_observations(timestamp);

-- 4. Heatmap Activities Table
CREATE TABLE IF NOT EXISTS heatmap_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    polygon_geojson TEXT NOT NULL,
    start_date TEXT NOT NULL,
    granularity INTEGER DEFAULT 100,
    analytic_type TEXT DEFAULT 'tcm',
    map_type TEXT DEFAULT 'tcm',
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_heatmap_activity ON heatmap_activities(activity_id);

-- 5. Heatmap Results (Polygon Tiles) Table
CREATE TABLE IF NOT EXISTS heatmap_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    heatmap_id INTEGER NOT NULL,
    tile_id INTEGER,
    avg_temp REAL,
    min_temp REAL,
    max_temp REAL,
    geometry_geojson TEXT,
    properties_json TEXT,
    FOREIGN KEY(heatmap_id) REFERENCES heatmap_activities(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_heat_results_map ON heatmap_results(heatmap_id);

-- 6. Heat Intelligence Reports Table
CREATE TABLE IF NOT EXISTS heat_intelligence_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    temperature REAL NOT NULL,
    date TEXT NOT NULL,
    analyses_json TEXT,
    download_link TEXT,
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 7. Satellite Segmentation Table
CREATE TABLE IF NOT EXISTS satellite_segmentation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT,
    status TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    date_time_json TEXT NOT NULL,
    granularity INTEGER DEFAULT 100,
    classes_json TEXT,
    imagery_metadata_json TEXT,
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Street-View Segmentation Table
CREATE TABLE IF NOT EXISTS street_view_segmentation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT,
    status TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    vertical_angle REAL DEFAULT 0.0,
    horizontal_angle REAL DEFAULT 0.0,
    back_view INTEGER DEFAULT 0,
    classes_json TEXT,
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Routing Activities Table
CREATE TABLE IF NOT EXISTS routing_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    origin_lat REAL NOT NULL,
    origin_lon REAL NOT NULL,
    dest_lat REAL NOT NULL,
    dest_lon REAL NOT NULL,
    departure_time TEXT NOT NULL,
    alternatives_json TEXT,
    metrics_json TEXT,
    raw_response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. API Request Telemetry Logs Table
CREATE TABLE IF NOT EXISTS api_request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    duration_ms REAL,
    is_error INTEGER DEFAULT 0,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_logs_time ON api_request_logs(timestamp);
"""

