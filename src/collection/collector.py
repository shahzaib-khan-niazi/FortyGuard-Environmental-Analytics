"""
Data Collection Orchestrator for FortyGuard Platform
===================================================
Coordinates user requests, location validation, API credit safeguards,
asynchronous polling, and local database ingestion.
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime

from src.api.fortyguard_client import (
    FortyGuardClient,
    FortyGuardAPIError,
    OutOfCoverageError,
    AuthenticationError,
    ValidationError,
)
from src.database.db import DatabaseManager

logger = logging.getLogger("fortyguard.collector")

# Curated catalog of supported US locations
SUPPORTED_US_LOCATIONS = [
    {
        "name": "Phoenix, AZ (Official Demo)",
        "latitude": 33.4484,
        "longitude": -112.0740,
        "state": "AZ",
        "notes": "Primary FortyGuard demonstration region. High urban heat island intensity.",
    },
    {
        "name": "Las Vegas, NV",
        "latitude": 36.1699,
        "longitude": -115.1398,
        "state": "NV",
        "notes": "Arid climate with severe summertime thermal exposure.",
    },
    {
        "name": "Austin, TX",
        "latitude": 30.2672,
        "longitude": -97.7431,
        "state": "TX",
        "notes": "Humid subtropical urban heat corridor.",
    },
    {
        "name": "Miami, FL",
        "latitude": 25.7617,
        "longitude": -80.1918,
        "state": "FL",
        "notes": "Tropical climate with high humidity and wet-bulb exposure.",
    },
    {
        "name": "Los Angeles, CA",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "state": "CA",
        "notes": "Mediterranean coastal basin with localized microclimates.",
    },
    {
        "name": "Houston, TX",
        "latitude": 29.7604,
        "longitude": -95.3698,
        "state": "TX",
        "notes": "High industrial density and severe summer heat index.",
    },
    {
        "name": "Atlanta, GA",
        "latitude": 33.7490,
        "longitude": -84.3880,
        "state": "GA",
        "notes": "Dense tree canopy vs downtown impervious surface heat contrast.",
    },
    {
        "name": "Chicago, IL",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "state": "IL",
        "notes": "Lake Michigan coastal influence and urban canyon geometry.",
    },
    {
        "name": "New York, NY",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "state": "NY",
        "notes": "Extremely dense urban fabric with canyon heat retention.",
    },
    {
        "name": "Dallas, TX",
        "latitude": 32.7767,
        "longitude": -96.7970,
        "state": "TX",
        "notes": "Inland Texas plains with prolonged heatwave persistence.",
    },
]

AVAILABLE_MEASUREMENTS = [
    {"id": "heat_index", "name": "Heat Index (°C)", "category": "Thermal"},
    {"id": "apparent_temperature", "name": "Apparent Temperature (°C)", "category": "Thermal"},
    {"id": "wet_bulb_temperature", "name": "Wet-Bulb Temperature (°C)", "category": "Thermal"},
    {"id": "relative_humidity", "name": "Relative Humidity (%)", "category": "Atmospheric"},
    {"id": "precipitation", "name": "Precipitation (mm)", "category": "Atmospheric"},
    {"id": "cloud_cover", "name": "Cloud Cover (octas)", "category": "Atmospheric"},
    {"id": "air_quality", "name": "Air Quality Index (AQI)", "category": "Air Quality"},
    {"id": "solar_irradiance", "name": "Solar Irradiance (W/m²)", "category": "Solar"},
]


class DataCollector:
    """Coordinates environmental data collection workflows."""

    def __init__(self, client: Optional[FortyGuardClient] = None, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.client = client or FortyGuardClient()
        self._seed_default_locations()

    def _seed_default_locations(self) -> None:
        """Seed pre-configured US locations if database is newly initialized."""
        try:
            existing = self.db.get_locations()
            if not existing:
                for loc in SUPPORTED_US_LOCATIONS:
                    self.db.upsert_location(
                        name=loc["name"],
                        latitude=loc["latitude"],
                        longitude=loc["longitude"],
                        state=loc["state"],
                        notes=loc["notes"],
                    )
                logger.info("Seeded %d default US locations into database.", len(SUPPORTED_US_LOCATIONS))
            self._seed_demo_observations_if_empty()
        except Exception as e:
            logger.warning("Could not seed default locations: %s", e)

    def _seed_demo_observations_if_empty(self) -> None:
        """Seed baseline demonstration observations if database is fresh."""
        try:
            if not self.db.get_observations_df().empty:
                return

            demo_records = [
                {
                    "loc_name": "Phoenix, AZ (Official Demo)",
                    "payload": {
                        "metadata": {"timezone": "America/Phoenix", "time_range": {"start": "2024-07-15T14:00:00-07:00"}, "timestamps": ["2024-07-15T14:00:00-07:00"]},
                        "locations": [{
                            "lat": 33.4484, "lon": -112.074, "elevation": 333.0, "temperature": 35.0,
                            "parameters": {
                                "heat_index_celsius": [33.4], "apparent_temperature_celsius": [40.7],
                                "relative_humidity_percent": [22.9], "precipitation_mm": [0.0],
                                "cloud_cover_octas": [0.0], "wet_bulb_temperature_celsius": [23.7],
                                "air_quality:idx": [58.4], "air_quality_pm2p5:idx": [58.0],
                                "air_quality_pm10:idx": [58.4], "air_quality_no2:idx": [1.0],
                                "aqi_us_co": [1.3], "air_quality_o3:idx": [40.4], "air_quality_so2:idx": [0.5],
                            },
                            "solar_irradiance": {"clear_sky": {"ghi": 926.59, "dni": 875.04, "dhi": 117.9}}
                        }]
                    }
                },
                {
                    "loc_name": "Miami, FL",
                    "payload": {
                        "metadata": {"timezone": "America/New_York", "time_range": {"start": "2024-07-15T14:00:00-04:00"}, "timestamps": ["2024-07-15T14:00:00-04:00"]},
                        "locations": [{
                            "lat": 25.7617, "lon": -80.1918, "elevation": 5.0, "temperature": 32.0,
                            "parameters": {
                                "heat_index_celsius": [42.2], "apparent_temperature_celsius": [34.5],
                                "relative_humidity_percent": [74.7], "precipitation_mm": [0.0],
                                "cloud_cover_octas": [8.0], "wet_bulb_temperature_celsius": [25.9],
                                "air_quality:idx": [53.0], "air_quality_pm2p5:idx": [53.0],
                                "air_quality_pm10:idx": [19.1], "air_quality_no2:idx": [0.1],
                                "aqi_us_co": [0.8], "air_quality_o3:idx": [20.1], "air_quality_so2:idx": [0.2],
                            },
                            "solar_irradiance": {"clear_sky": {"ghi": 910.74, "dni": 719.54, "dhi": 199.63}}
                        }]
                    }
                },
                {
                    "loc_name": "Las Vegas, NV",
                    "payload": {
                        "metadata": {"timezone": "America/Los_Angeles", "time_range": {"start": "2024-07-15T14:00:00-07:00"}, "timestamps": ["2024-07-15T14:00:00-07:00"]},
                        "locations": [{
                            "lat": 36.1699, "lon": -115.1398, "elevation": 620.0, "temperature": 38.0,
                            "parameters": {
                                "heat_index_celsius": [35.2], "apparent_temperature_celsius": [40.4],
                                "relative_humidity_percent": [11.6], "precipitation_mm": [0.0],
                                "cloud_cover_octas": [2.0], "wet_bulb_temperature_celsius": [20.1],
                                "air_quality:idx": [55.4], "air_quality_pm2p5:idx": [48.7],
                                "air_quality_pm10:idx": [16.0], "air_quality_no2:idx": [0.4],
                                "aqi_us_co": [1.6], "air_quality_o3:idx": [55.4], "air_quality_so2:idx": [0.3],
                            },
                            "solar_irradiance": {"clear_sky": {"ghi": 949.09, "dni": 889.09, "dhi": 123.55}}
                        }]
                    }
                },
                {
                    "loc_name": "New York, NY",
                    "payload": {
                        "metadata": {"timezone": "America/New_York", "time_range": {"start": "2024-07-15T14:00:00-04:00"}, "timestamps": ["2024-07-15T14:00:00-04:00"]},
                        "locations": [{
                            "lat": 40.7128, "lon": -74.006, "elevation": 32.0, "temperature": 29.0,
                            "parameters": {
                                "heat_index_celsius": [30.0], "apparent_temperature_celsius": [37.9],
                                "relative_humidity_percent": [53.4], "precipitation_mm": [0.0],
                                "cloud_cover_octas": [8.0], "wet_bulb_temperature_celsius": [25.9],
                                "air_quality:idx": [87.3], "air_quality_pm2p5:idx": [78.1],
                                "air_quality_pm10:idx": [31.1], "air_quality_no2:idx": [4.1],
                                "aqi_us_co": [2.9], "air_quality_o3:idx": [87.3], "air_quality_so2:idx": [5.5],
                            },
                            "solar_irradiance": {"clear_sky": {"ghi": 898.69, "dni": 827.19, "dhi": 136.76}}
                        }]
                    }
                }
            ]

            for d in demo_records:
                loc = self.db.get_location_by_name(d["loc_name"])
                if loc:
                    self.db.insert_environmental_observations(
                        location_id=loc["id"],
                        job_id=None,
                        result_payload=d["payload"],
                        raw_response_str="{}",
                    )
            logger.info("Seeded initial demonstration observations into database.")
        except Exception as e:
            logger.warning("Could not seed demo observations: %s", e)

    @staticmethod
    def validate_us_coordinates(latitude: float, longitude: float) -> Tuple[bool, str]:
        """
        Validate whether given coordinates fall within FortyGuard's supported US coverage bounds.
        Contiguous US roughly: Lat [24.0, 50.0], Lon [-125.0, -66.0].
        Alaska: Lat [51.0, 72.0], Lon [-180.0, -129.0].
        Hawaii: Lat [18.0, 23.0], Lon [-161.0, -154.0].
        """
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return False, "Coordinates must be valid lat [-90, 90] and lon [-180, 180]."

        is_contiguous_us = (24.0 <= latitude <= 50.0) and (-125.0 <= longitude <= -66.0)
        is_alaska = (51.0 <= latitude <= 72.0) and (-180.0 <= longitude <= -129.0)
        is_hawaii = (18.0 <= latitude <= 23.0) and (-161.0 <= longitude <= -154.0)

        if not (is_contiguous_us or is_alaska or is_hawaii):
            return False, (
                "FortyGuard currently supports US regions only. "
                "The coordinates provided appear to be outside the United States coverage area."
            )

        return True, "Valid US coordinates."

    def collect_point_data(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        reference_temperature: float,
        start_date: str,
        start_time: str = "14:00",
        filter_type: int = 1,
        selected_parameters: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute environmental point collection workflow:
        1. Validates US coordinates
        2. Upserts location in database
        3. Checks cache if requested
        4. Submits request to FortyGuard API
        5. Polls status until completed
        6. Ingests observations into database
        7. Returns summary dictionary
        """
        is_valid, msg = self.validate_us_coordinates(latitude, longitude)
        if not is_valid:
            raise OutOfCoverageError(msg)

        # Upsert location
        location_id = self.db.upsert_location(
            name=location_name,
            latitude=latitude,
            longitude=longitude,
        )

        job_params = {
            "location_name": location_name,
            "location_id": location_id,
            "latitude": latitude,
            "longitude": longitude,
            "reference_temperature": reference_temperature,
            "start_date": start_date,
            "start_time": start_time,
            "filter_type": filter_type,
            "selected_parameters": selected_parameters,
        }

        # Check existing cached observations
        if use_cache:
            existing_df = self.db.get_observations_df(
                location_ids=[location_id],
                start_date=start_date,
                end_date=start_date + "T23:59:59"
            )
            if not existing_df.empty:
                logger.info("Found cached observation for %s on %s. Returning cached.", location_name, start_date)
                return {
                    "success": True,
                    "cached": True,
                    "location_id": location_id,
                    "rows_inserted": 0,
                    "message": f"Retrieved {len(existing_df)} cached observation(s) from local database.",
                }

        job_id = self.db.create_job(job_type="env_params", parameters=job_params)

        start_time_exec = time.time()
        try:
            if progress_callback:
                progress_callback("Submitting request to FortyGuard API...", 0)

            # Limit to 3 parameters if selected to be safe with Basic/Startup plans
            analysis_param = selected_parameters[:3] if selected_parameters else None

            submit_res = self.client.get_env_params(
                latitude=latitude,
                longitude=longitude,
                temperature=reference_temperature,
                start_date=start_date,
                start_time=start_time,
                filter_type=filter_type,
                analysis=analysis_param,
            )

            duration_ms = (time.time() - start_time_exec) * 1000
            self.db.log_api_request("env_params", "POST", 200, duration_ms)

            activity_id = submit_res.get("data", {}).get("activity_id")
            if not activity_id:
                raise FortyGuardAPIError(
                    f"API did not return activity_id: {submit_res.get('message', 'Unknown response')}"
                )

            self.db.update_job_status(job_id, status="RUNNING", activity_id=activity_id)

            if progress_callback:
                progress_callback(f"Activity queued ({activity_id[:8]}...). Polling results...", 5)

            # Poll activity until completion
            completed_res = self.client.poll_activity(
                activity_id=activity_id,
                interval_seconds=2.5,
                max_wait_seconds=90.0,
                callback=progress_callback,
            )

            result_data = completed_res.get("data", {}).get("result", {})
            raw_str = json.dumps(completed_res)

            # Ingest observations
            inserted = self.db.insert_environmental_observations(
                location_id=location_id,
                job_id=job_id,
                result_payload=result_data,
                raw_response_str=raw_str,
            )

            self.db.update_job_status(job_id, status="COMPLETED", activity_id=activity_id)

            if progress_callback:
                progress_callback(f"Successfully collected {inserted} observation record(s)!", 100)

            return {
                "success": True,
                "cached": False,
                "job_id": job_id,
                "activity_id": activity_id,
                "location_id": location_id,
                "rows_inserted": inserted,
                "result": result_data,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time_exec) * 1000
            self.db.log_api_request("env_params", "POST", 400, duration_ms, is_error=True, error_message=str(e))
            self.db.update_job_status(job_id, status="FAILED", error_message=str(e))
            logger.error("Data collection failed for %s: %s", location_name, e)
            raise

