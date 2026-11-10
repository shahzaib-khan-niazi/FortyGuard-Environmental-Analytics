"""
FortyGuard API Client
====================
Provides centralized, authenticated access to the FortyGuard Enterprise REST API (v1).
Features:
- Secure header-based authentication ('api-key')
- Configurable timeouts, retry policies for transient errors
- Rate limit handling and detailed error discrimination
- Asynchronous activity polling with callbacks
- Safe logging without leaking sensitive API credentials
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from urllib.parse import urljoin
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logger
logger = logging.getLogger("fortyguard.client")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [FortyGuardClient]: %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


class FortyGuardAPIError(Exception):
    """Base exception for FortyGuard API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class AuthenticationError(FortyGuardAPIError):
    """Raised when authentication fails (HTTP 401)."""
    pass


class OutOfCoverageError(FortyGuardAPIError):
    """Raised when location is outside FortyGuard supported US coverage (HTTP 400)."""
    pass


class ValidationError(FortyGuardAPIError):
    """Raised when request payload fails schema validation (HTTP 422)."""
    pass


class RateLimitError(FortyGuardAPIError):
    """Raised when request is throttled by rate limiting (HTTP 429)."""
    pass


class ActivityTimeoutError(FortyGuardAPIError):
    """Raised when asynchronous activity does not complete within max_wait_seconds."""
    pass


class FortyGuardClient:
    """Enterprise REST API client for FortyGuard Temperature API."""

    DEFAULT_BASE_URL = "https://api.fortyguard.com/v1/"
    DEFAULT_TIMEOUT = 25  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ):
        """
        Initialize the FortyGuard client.

        :param api_key: Optional FortyGuard API key (defaults to FORTYGUARD_API_KEY from .env)
        :param base_url: API base URL (defaults to https://api.fortyguard.com/v1/)
        :param timeout: Request timeout in seconds
        :param max_retries: Max retries for transient 5xx HTTP errors
        :param backoff_factor: Multiplier for exponential backoff between retries
        """
        self.api_key = api_key or os.getenv("FORTYGUARD_API_KEY")
        if not self.api_key:
            # Fallback to Streamlit secrets if running on Streamlit Cloud
            try:
                import streamlit as st
                if "FORTYGUARD_API_KEY" in st.secrets:
                    self.api_key = st.secrets["FORTYGUARD_API_KEY"]
            except Exception:
                pass

        if not self.api_key:
            raise AuthenticationError(
                "Missing FortyGuard API key. Set FORTYGUARD_API_KEY in your .env file "
                "or pass api_key to FortyGuardClient()."
            )

        raw_base_url = base_url or os.getenv("FORTYGUARD_BASE_URL", self.DEFAULT_BASE_URL)
        self.base_url = raw_base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.session = requests.Session()
        self.session.headers.update({
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "FortyGuard-Analytics-Platform/1.0",
        })

    def _mask_key(self) -> str:
        """Return masked API key for safe logging."""
        if not self.api_key or len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def _full_url(self, endpoint: str) -> str:
        """Construct full URL cleanly avoiding double slashes."""
        clean_endpoint = endpoint.lstrip("/")
        return urljoin(self.base_url, clean_endpoint)

    def _handle_response_error(self, response: requests.Response) -> None:
        """Inspect HTTP response and raise appropriate typed exception."""
        status_code = response.status_code
        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        message = data.get("message")
        if not message and isinstance(data.get("details"), dict):
            message = data["details"].get("message")
        if not message and isinstance(data.get("detail"), list):
            message = str(data["detail"])
        if not message:
            message = f"HTTP {status_code}: {response.text[:200]}"

        if status_code == 401:
            logger.error("Authentication failed: %s (Key: %s)", message, self._mask_key())
            raise AuthenticationError(message, status_code=status_code, response_data=data)

        if status_code == 400:
            if data.get("code") == "OUT_OF_COVERAGE" or "coverage" in message.lower():
                logger.warning("Location out of coverage: %s", message)
                raise OutOfCoverageError(message, status_code=status_code, response_data=data)
            logger.warning("Bad request (400): %s", message)
            raise FortyGuardAPIError(f"Bad Request (400): {message}", status_code=status_code, response_data=data)

        if status_code == 422:
            logger.warning("Validation error (422): %s", message)
            raise ValidationError(f"Validation Error (422): {message}", status_code=status_code, response_data=data)

        if status_code == 429:
            logger.warning("Rate limit reached (429): %s", message)
            raise RateLimitError(f"Rate Limit Exceeded (429): {message}", status_code=status_code, response_data=data)

        if status_code >= 500:
            logger.error("FortyGuard server error (%s): %s", status_code, message)
            raise FortyGuardAPIError(f"Server Error ({status_code}): {message}", status_code=status_code, response_data=data)

        logger.error("API error (%s): %s", status_code, message)
        raise FortyGuardAPIError(f"API Error ({status_code}): {message}", status_code=status_code, response_data=data)

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        idempotent: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request with retry logic for transient errors.
        
        :param method: GET, POST, etc.
        :param endpoint: Relative endpoint path (e.g. 'env_params')
        :param params: Optional query parameters
        :param json_data: Optional JSON payload
        :param idempotent: If True, safe to retry on 5xx or connection drops
        """
        url = self._full_url(endpoint)
        max_attempts = self.max_retries if (idempotent or method.upper() == "GET") else 2

        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug("Request %s %s (attempt %d/%d)", method.upper(), url, attempt, max_attempts)
                resp = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )

                if resp.status_code < 400:
                    try:
                        return resp.json()
                    except Exception as e:
                        raise FortyGuardAPIError(
                            f"Failed to parse JSON response: {e}. Body: {resp.text[:200]}",
                            status_code=resp.status_code,
                        )

                # If status >= 500 and attempt < max_attempts, sleep and retry
                if resp.status_code >= 500 and attempt < max_attempts:
                    sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                    logger.warning(
                        "Received HTTP %s, retrying in %.2fs (attempt %d/%d)...",
                        resp.status_code, sleep_time, attempt, max_attempts
                    )
                    time.sleep(sleep_time)
                    continue

                self._handle_response_error(resp)

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_attempts:
                    sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                    logger.warning("Connection error '%s', retrying in %.2fs...", e, sleep_time)
                    time.sleep(sleep_time)
                    continue
                logger.error("Request failed after %d attempts: %s", max_attempts, e)
                raise FortyGuardAPIError(f"Network connection error: {e}")

        raise FortyGuardAPIError(f"Request failed after {max_attempts} attempts.")

    # -------------------------------------------------------------------------
    # Core API Capabilities
    # -------------------------------------------------------------------------

    def test_connection(self) -> Dict[str, Any]:
        """
        Safely test API connectivity and credential validity.
        Uses a lightweight test payload for Phoenix, AZ.
        """
        test_payload = {
            "latitude": 33.4484,
            "longitude": -112.0740,
            "temperature": 35.0,
            "date_time": {
                "start_date": "2024-07-15",
                "start_time": "14:00",
                "filter_type": 1,
            },
        }
        res = self.request("POST", "env_params", json_data=test_payload)
        return {
            "success": True,
            "activity_id": res.get("data", {}).get("activity_id"),
            "message": res.get("message", "Connected successfully"),
        }

    def get_env_params(
        self,
        latitude: float,
        longitude: float,
        temperature: float,
        start_date: str,
        start_time: str = "14:00",
        filter_type: int = 1,
        end_date: Optional[str] = None,
        end_time: Optional[str] = None,
        analysis: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a request for point-level environmental measurements.
        Returns the submission response containing an activity_id.
        """
        dt_obj: Dict[str, Any] = {
            "start_date": start_date,
            "filter_type": filter_type,
        }
        if filter_type in (1, 2):
            dt_obj["start_time"] = start_time
        if filter_type == 2 and end_time:
            dt_obj["end_time"] = end_time
        if filter_type == 4 and end_date:
            dt_obj["end_date"] = end_date

        payload: Dict[str, Any] = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "temperature": float(temperature),
            "date_time": dt_obj,
        }
        if analysis:
            payload["analysis"] = analysis

        return self.request("POST", "env_params", json_data=payload)

    def check_status(self, activity_id: str) -> Dict[str, Any]:
        """
        Poll the status of an asynchronous activity.
        GET /v1/status/{activity_id}
        """
        if not activity_id:
            raise ValidationError("activity_id is required.")
        return self.request("GET", f"status/{activity_id}", idempotent=True)

    def poll_activity(
        self,
        activity_id: str,
        interval_seconds: float = 3.0,
        max_wait_seconds: float = 90.0,
        callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Poll status endpoint until activity reaches 'Completed' or 'Failed'.
        
        :param activity_id: Task UUID
        :param interval_seconds: Sleep duration between checks
        :param max_wait_seconds: Maximum total wait before ActivityTimeoutError
        :param callback: Optional hook callback(status_str, elapsed_seconds)
        :return: Completed activity data dictionary
        """
        start_time = time.time()
        attempt = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                raise ActivityTimeoutError(
                    f"Activity {activity_id} timed out after {int(elapsed)} seconds."
                )

            res = self.check_status(activity_id)
            data = res.get("data", {})
            status = data.get("status", res.get("message", "Processing"))
            attempt += 1

            if callback:
                try:
                    callback(status, int(elapsed))
                except Exception as cb_err:
                    logger.warning("Callback error during polling: %s", cb_err)

            if status.lower() == "completed":
                logger.info("Activity %s completed in %.1fs", activity_id, elapsed)
                return res
            elif status.lower() == "failed":
                error_msg = data.get("error_message") or res.get("message") or "Unknown error"
                logger.error("Activity %s failed: %s", activity_id, error_msg)
                raise FortyGuardAPIError(f"Activity {activity_id} failed: {error_msg}", response_data=res)

            time.sleep(interval_seconds)

    # -------------------------------------------------------------------------
    # Asynchronous Heatmap
    # -------------------------------------------------------------------------

    def submit_heatmap(
        self,
        polygon_aoi: Dict[str, Any],
        start_date: str,
        start_time: str = "14:00",
        filter_type: int = 1,
        end_date: Optional[str] = None,
        end_time: Optional[str] = None,
        granularity: int = 100,
        analytic_types: str = "tcm",
        map_type: str = "tcm",
    ) -> Dict[str, Any]:
        """
        Submit an asynchronous thermal heatmap generation job.
        
        :param polygon_aoi: GeoJSON Polygon dictionary
        :param start_date: YYYY-MM-DD
        :param start_time: HH:MM
        :param filter_type: 1 (hour), 2 (hours range), 3 (day), 4 (days range)
        :param granularity: Spatial resolution (60, 80, 100)
        :param analytic_types: 'tcm', 'time_of_measure', 'exceedance', 'persistence'
        :param map_type: 'bm', 'tcm', 'tccm'
        """
        dt_obj: Dict[str, Any] = {
            "start_date": start_date,
            "filter_type": filter_type,
        }
        if filter_type in (1, 2):
            dt_obj["start_time"] = start_time
        if filter_type == 2 and end_time:
            dt_obj["end_time"] = end_time
        if filter_type == 4 and end_date:
            dt_obj["end_date"] = end_date

        payload = {
            "polygon_aoi": polygon_aoi,
            "date_time": dt_obj,
            "granularity": granularity,
            "analytic_types": analytic_types,
            "map_type": map_type,
        }
        return self.request("POST", "heatmap", json_data=payload)

    # -------------------------------------------------------------------------
    # Heat Intelligence Reports
    # -------------------------------------------------------------------------

    def submit_heat_intelligence(
        self,
        latitude: float,
        longitude: float,
        temperature: float,
        date: str,
        analysis: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Submit a Heat Intelligence report generation request.
        
        :param latitude: Float latitude coordinate
        :param longitude: Float longitude coordinate
        :param temperature: Reference temperature in Fahrenheit or Celsius
        :param date: YYYY-MM-DD
        :param analysis: Categories ('geographic', 'environmental', 'urban', 'events', 'anthropogenic')
        """
        analysis_list = analysis or ["geographic", "environmental", "urban", "events", "anthropogenic"]
        payload = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "temperature": float(temperature),
            "date": date,
            "analysis": analysis_list,
        }
        return self.request("POST", "heat_intelligence", json_data=payload)

    # -------------------------------------------------------------------------
    # Satellite View Segmentation
    # -------------------------------------------------------------------------

    def submit_satellite(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        start_time: str = "14:00",
        filter_type: int = 1,
        granularity: int = 100,
    ) -> Dict[str, Any]:
        """
        Submit Satellite view semantic segmentation analysis.
        """
        payload = {
            "sat": {
                "latitude": float(latitude),
                "longitude": float(longitude),
            },
            "date_time": {
                "start_date": start_date,
                "start_time": start_time,
                "filter_type": filter_type,
            },
            "granularity": granularity,
        }
        return self.request("POST", "satellite", json_data=payload)

    # -------------------------------------------------------------------------
    # Street View Segmentation
    # -------------------------------------------------------------------------

    def submit_streetview(
        self,
        latitude: float,
        longitude: float,
        vertical_angle: float = 0.0,
        horizontal_angle: float = 0.0,
        back_view: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit Street view semantic segmentation analysis.
        """
        payload = {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "vertical_angle": float(vertical_angle),
            "horizontal_angle": float(horizontal_angle),
            "back_view": bool(back_view),
        }
        return self.request("POST", "streetview", json_data=payload)

    # -------------------------------------------------------------------------
    # Temperature-Aware Routing
    # -------------------------------------------------------------------------

    def submit_routing(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        departure_time: str,
    ) -> Dict[str, Any]:
        """
        Submit a Temperature-Aware Routing calculation request.
        
        :param origin_lat: Origin latitude
        :param origin_lon: Origin longitude
        :param dest_lat: Destination latitude
        :param dest_lon: Destination longitude
        :param departure_time: ISO 8601 string (e.g. '2026-09-15T17:00:00Z')
        """
        payload = {
            "origin": {"lat": float(origin_lat), "lon": float(origin_lon)},
            "destination": {"lat": float(dest_lat), "lon": float(dest_lon)},
            "departure_time": departure_time,
        }
        return self.request("POST", "routing", json_data=payload)
