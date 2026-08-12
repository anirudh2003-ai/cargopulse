"""Tests for the CargoPulse OpenAPI contract."""

from fastapi.testclient import TestClient

from api.main import app


def test_expected_api_routes_are_documented() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    expected_paths = {
        "/health",
        "/api/v1/risk/latest",
        "/api/v1/risk/daily",
        "/api/v1/risk/{metric_date}",
        "/api/v1/calls",
        "/api/v1/calls/{validated_call_id}",
        "/api/v1/berths",
        "/api/v1/terminal/daily",
    }

    assert expected_paths.issubset(paths.keys())
