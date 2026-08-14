"""Tests for CargoPulse operational API endpoints."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

import api.routes.operations as operations_routes
from api.db.database import get_engine
from api.main import app

CALL_RECORD = {
    "validated_call_id": 34,
    "mmsi": 311001111,
    "imo": 9903920,
    "vessel_name": "GRACE FREESIA",
    "terminal_id": 1,
    "berth_zone_code": "SPL_BERTH_2",
    "berth_arrival_time": datetime(
        2023,
        1,
        29,
        13,
        54,
        59,
        tzinfo=timezone.utc,
    ),
    "berth_departure_time": datetime(
        2023,
        1,
        30,
        23,
        58,
        0,
        tzinfo=timezone.utc,
    ),
    "berth_duration_minutes": 2043.02,
    "expected_duration_minutes": 2694.35,
    "duration_variance_minutes": -651.33,
    "estimated_delay_minutes": 0.0,
    "estimated_delay_hours": 0.0,
    "delay_band": "unscored",
    "delay_quality": "censored",
    "baseline_scope": "berth",
    "baseline_sample_size": 7,
    "berth_detection_confidence": "high",
    "berth_continuity": "continuous",
    "movement_coverage": "inbound_only",
    "inbound_transit_minutes": 39.67,
    "outbound_transit_minutes": None,
    "arrival_metric_date": date(2023, 1, 29),
    "arrival_day_terminal_arrivals": 2,
    "arrival_day_terminal_departures": 1,
    "arrival_day_max_occupied_berths": 3,
    "arrival_day_terminal_utilisation_pct": 88.64,
    "arrival_day_mean_occupied_berths": 2.66,
}


BERTH_RECORD = {
    "berth_zone_code": "SPL_BERTH_1",
    "total_calls": 12,
    "scored_calls": 11,
    "elevated_calls": 2,
    "high_delay_calls": 0,
    "severe_delay_calls": 1,
    "median_duration_minutes": 2571.7,
    "p90_duration_minutes": 3094.74,
    "mean_estimated_delay_minutes": 168.63,
    "occupied_minutes": 29274.87,
    "utilisation_pct": 67.77,
}


TERMINAL_RECORD = {
    "metric_date": date(2023, 1, 30),
    "arrivals": 0,
    "departures": 0,
    "occupied_berth_minutes": 4316.37,
    "max_occupied_berths": 3,
    "terminal_utilisation_pct": 99.92,
    "mean_occupied_berths": 3.0,
    "mean_arrival_delay_minutes": None,
    "severe_delay_arrivals": 0,
}


def setup_module() -> None:
    app.dependency_overrides[get_engine] = lambda: object()


def teardown_module() -> None:
    app.dependency_overrides.clear()


def test_list_calls(monkeypatch) -> None:
    def fake_fetch_calls(engine, limit):
        assert limit == 1
        return [CALL_RECORD]

    monkeypatch.setattr(
        operations_routes,
        "fetch_calls",
        fake_fetch_calls,
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/calls?limit=1"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["validated_call_id"] == 34
    assert body[0]["vessel_name"] == "GRACE FREESIA"


def test_call_by_id(monkeypatch) -> None:
    def fake_fetch_call(engine, validated_call_id):
        assert validated_call_id == 34
        return CALL_RECORD

    monkeypatch.setattr(
        operations_routes,
        "fetch_call_by_id",
        fake_fetch_call,
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/calls/34"
    )

    assert response.status_code == 200
    assert response.json()["imo"] == 9903920


def test_call_by_id_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        operations_routes,
        "fetch_call_by_id",
        lambda engine, validated_call_id: None,
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/calls/999999"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "No LNG call found for "
            "validated_call_id=999999"
        )
    }


def test_berth_performance(monkeypatch) -> None:
    monkeypatch.setattr(
        operations_routes,
        "fetch_berth_performance",
        lambda engine: [BERTH_RECORD],
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/berths"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["berth_zone_code"] == "SPL_BERTH_1"
    assert body[0]["total_calls"] == 12


def test_terminal_daily(monkeypatch) -> None:
    def fake_terminal_daily(engine, limit):
        assert limit == 1
        return [TERMINAL_RECORD]

    monkeypatch.setattr(
        operations_routes,
        "fetch_terminal_daily_metrics",
        fake_terminal_daily,
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/terminal/daily?limit=1"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["metric_date"] == "2023-01-30"


def test_terminal_daily_rejects_invalid_limit() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/v1/terminal/daily?limit=0"
    )

    assert response.status_code == 422
