"""Tests for CargoPulse risk API endpoints."""

from datetime import date

from fastapi.testclient import TestClient

import api.routes.risk as risk_routes
from api.db.database import get_engine
from api.main import app

LATEST_RISK = {
    "metric_date": date(2023, 1, 30),
    "risk_score": 52.8,
    "risk_level": "elevated",
    "score_confidence": "high",
    "risk_trend": "rising",
    "risk_headline": "ELEVATED — 52.8 / 100",
    "terminal_utilisation_pct": 99.9,
    "max_occupied_berths": 3,
    "active_calls": 3,
    "active_delayed_calls": 1,
    "active_severe_calls": 0,
    "active_mean_delay_hours": 9.38,
    "risk_change_1d": 4.9,
    "previous_risk_level": "moderate",
    "primary_driver": "Terminal utilisation 99.9%",
    "primary_driver_points": 20.0,
    "secondary_driver": "Trailing 3-day utilisation 81.4%",
    "secondary_driver_points": 12.2,
    "tertiary_driver": "All 3 berths occupied at peak",
    "tertiary_driver_points": 10.0,
    "risk_explanation": "Primary drivers",
    "utilisation_3d_avg": 81.4,
    "arrivals_3d": 2.0,
    "departures_3d": 2.0,
    "vessel_balance_3d": 0.0,
    "capacity_points": 20.0,
    "saturation_points": 10.0,
    "active_delay_points": 6.7,
    "active_severe_points": 0.0,
    "delay_intensity_points": 3.9,
    "utilisation_3d_points": 12.2,
    "backlog_points": 0.0,
}


def setup_module() -> None:
    app.dependency_overrides[get_engine] = lambda: object()


def teardown_module() -> None:
    app.dependency_overrides.clear()


def test_latest_risk(monkeypatch) -> None:
    monkeypatch.setattr(
        risk_routes,
        "fetch_latest_risk",
        lambda engine: LATEST_RISK,
    )

    client = TestClient(app)

    response = client.get("/api/v1/risk/latest")

    assert response.status_code == 200

    body = response.json()

    assert body["metric_date"] == "2023-01-30"
    assert body["risk_score"] == 52.8
    assert body["risk_level"] == "elevated"
    assert body["score_confidence"] == "high"


def test_daily_risk_limit(monkeypatch) -> None:
    records = [
        {
            key: value
            for key, value in LATEST_RISK.items()
            if key in {
                "metric_date",
                "risk_score",
                "risk_level",
                "score_confidence",
                "risk_trend",
                "risk_headline",
                "terminal_utilisation_pct",
                "max_occupied_berths",
                "active_calls",
                "active_delayed_calls",
                "active_severe_calls",
                "active_mean_delay_hours",
            }
        }
    ]

    def fake_history(engine, limit):
        assert limit == 1
        return records

    monkeypatch.setattr(
        risk_routes,
        "fetch_risk_history",
        fake_history,
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/risk/daily?limit=1"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_risk_by_date_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        risk_routes,
        "fetch_risk_by_date",
        lambda engine, metric_date: None,
    )

    client = TestClient(app)

    response = client.get(
        "/api/v1/risk/2022-01-01"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "No risk data available for 2022-01-01"
        )
    }


def test_daily_risk_rejects_invalid_limit() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/v1/risk/daily?limit=0"
    )

    assert response.status_code == 422
