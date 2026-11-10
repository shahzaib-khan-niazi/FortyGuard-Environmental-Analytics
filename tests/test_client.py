"""
Unit tests for FortyGuard API Client
====================================
Uses mocked responses so tests run quickly without consuming live API credits.
"""

import pytest
from unittest.mock import MagicMock, patch
import requests

from src.api.fortyguard_client import (
    FortyGuardClient,
    AuthenticationError,
    OutOfCoverageError,
    ValidationError,
    RateLimitError,
    FortyGuardAPIError,
    ActivityTimeoutError,
)


def test_missing_api_key_raises_error(monkeypatch):
    """Test that client raises AuthenticationError if no API key is provided."""
    monkeypatch.delenv("FORTYGUARD_API_KEY", raising=False)
    with pytest.raises(AuthenticationError):
        FortyGuardClient(api_key=None)


def test_client_header_initialization():
    """Verify that the client sets the 'api-key' header correctly."""
    client = FortyGuardClient(api_key="test_dummy_key_12345")
    assert client.session.headers.get("api-key") == "test_dummy_key_12345"
    assert "https://api.fortyguard.com/v1/" in client.base_url


@patch("requests.Session.request")
def test_successful_env_params(mock_request):
    """Test successful submission of env_params."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "error": False,
        "status_code": 200,
        "message": "Environment Parameters Analysis Submitted Successfully",
        "data": {"activity_id": "act-1234-uuid"},
    }
    mock_request.return_value = mock_resp

    client = FortyGuardClient(api_key="test_dummy_key_12345")
    res = client.get_env_params(
        latitude=33.4484,
        longitude=-112.0740,
        temperature=35.0,
        start_date="2024-07-15",
    )
    assert res["error"] is False
    assert res["data"]["activity_id"] == "act-1234-uuid"


@patch("requests.Session.request")
def test_authentication_failure_401(mock_request):
    """Test handling of 401 Unauthorized."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {
        "error": True,
        "status_code": 401,
        "details": {"message": "Invalid or unknown API key."},
    }
    mock_request.return_value = mock_resp

    client = FortyGuardClient(api_key="bad_key")
    with pytest.raises(AuthenticationError) as exc_info:
        client.get_env_params(latitude=33.4484, longitude=-112.0740, temperature=35.0, start_date="2024-07-15")
    assert "Invalid or unknown API key" in str(exc_info.value)


@patch("requests.Session.request")
def test_out_of_coverage_400(mock_request):
    """Test handling of 400 Out of Coverage."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "error": True,
        "status_code": 400,
        "message": "The requested location is outside supported U.S. coverage.",
        "code": "OUT_OF_COVERAGE",
    }
    mock_request.return_value = mock_resp

    client = FortyGuardClient(api_key="valid_key")
    with pytest.raises(OutOfCoverageError):
        client.get_env_params(latitude=24.86, longitude=67.00, temperature=35.0, start_date="2024-07-15")


@patch("requests.Session.request")
def test_validation_error_422(mock_request):
    """Test handling of 422 Unprocessable Entity."""
    mock_resp = MagicMock()
    mock_resp.status_code = 422
    mock_resp.json.return_value = {
        "error": True,
        "status_code": 422,
        "message": "Field 'latitude' is required.",
    }
    mock_request.return_value = mock_resp

    client = FortyGuardClient(api_key="valid_key")
    with pytest.raises(ValidationError):
        client.request("POST", "env_params", json_data={})


@patch("requests.Session.request")
def test_rate_limit_error_429(mock_request):
    """Test handling of 429 Rate Limit."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.json.return_value = {
        "error": True,
        "status_code": 429,
        "message": "Too Many Requests. Rate limit exceeded.",
    }
    mock_request.return_value = mock_resp

    client = FortyGuardClient(api_key="valid_key")
    with pytest.raises(RateLimitError):
        client.request("GET", "status/act-123")


@patch("requests.Session.request")
def test_poll_activity_success(mock_request):
    """Test polling helper transitioning from Processing to Completed."""
    processing_resp = MagicMock()
    processing_resp.status_code = 200
    processing_resp.json.return_value = {
        "error": False,
        "status_code": 200,
        "data": {"activity_id": "act-123", "status": "Processing"},
    }

    completed_resp = MagicMock()
    completed_resp.status_code = 200
    completed_resp.json.return_value = {
        "error": False,
        "status_code": 200,
        "data": {
            "activity_id": "act-123",
            "status": "Completed",
            "result": {"metadata": {}, "locations": []},
        },
    }

    mock_request.side_effect = [processing_resp, completed_resp]

    client = FortyGuardClient(api_key="valid_key")
    status_updates = []

    def hook(status, elapsed):
        status_updates.append(status)

    res = client.poll_activity("act-123", interval_seconds=0.01, max_wait_seconds=5.0, callback=hook)
    assert res["data"]["status"] == "Completed"
    assert "Processing" in status_updates


@patch("requests.Session.request")
def test_poll_activity_timeout(mock_request):
    """Test polling timeout raising ActivityTimeoutError."""
    processing_resp = MagicMock()
    processing_resp.status_code = 200
    processing_resp.json.return_value = {
        "error": False,
        "status_code": 200,
        "data": {"activity_id": "act-123", "status": "Processing"},
    }
    mock_request.return_value = processing_resp

    client = FortyGuardClient(api_key="valid_key")
    with pytest.raises(ActivityTimeoutError):
        client.poll_activity("act-123", interval_seconds=0.01, max_wait_seconds=0.05)

