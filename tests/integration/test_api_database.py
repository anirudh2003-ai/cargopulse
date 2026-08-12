"""Integration tests for FastAPI against CargoPulse PostgreSQL."""

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_live_api_reads_validated_risk_data() -> None:
    response = client.get(
        "/api/v1/risk/latest"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["metric_date"] == "2023-01-30"
    assert body["risk_score"] == 52.8
    assert body["risk_level"] == "elevated"
    assert body["score_confidence"] == "high"


def test_live_api_reads_validated_call_data() -> None:
    response = client.get(
        "/api/v1/calls?limit=1"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["validated_call_id"] == 34
    assert body[0]["vessel_name"] == "GRACE FREESIA"
