"""Tests for the CargoPulse health endpoint."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from api.db.database import get_engine
from api.main import app


def test_health_endpoint() -> None:
    test_engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    app.dependency_overrides[get_engine] = (
        lambda: test_engine
    )

    try:
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "database": "ok",
        }

    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
