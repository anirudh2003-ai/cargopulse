"""Tests for the CargoPulse dashboard API client."""

import dashboard.api_client as api_client


class FakeResponse:
    """Minimal requests response used by dashboard tests."""

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return self.payload


def test_get_api_base_url_default(monkeypatch) -> None:
    monkeypatch.delenv(
        "CARGOPULSE_API_URL",
        raising=False,
    )

    assert (
        api_client.get_api_base_url()
        == "http://127.0.0.1:8000"
    )


def test_get_api_base_url_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "CARGOPULSE_API_URL",
        "http://api:8000/",
    )

    assert (
        api_client.get_api_base_url()
        == "http://api:8000"
    )


def test_get_json(monkeypatch) -> None:
    captured = {}

    def fake_get(
        url,
        params=None,
        timeout=None,
    ):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout

        return FakeResponse(
            {
                "status": "ok",
            }
        )

    monkeypatch.setattr(
        api_client.requests,
        "get",
        fake_get,
    )

    result = api_client.get_json(
        "/health"
    )

    assert result == {
        "status": "ok",
    }

    assert (
        captured["url"]
        == "http://127.0.0.1:8000/health"
    )

    assert captured["timeout"] == 10


def test_get_risk_history_passes_limit(
    monkeypatch,
) -> None:
    captured = {}

    def fake_get_json(
        path,
        *,
        params=None,
    ):
        captured["path"] = path
        captured["params"] = params

        return []

    monkeypatch.setattr(
        api_client,
        "get_json",
        fake_get_json,
    )

    result = api_client.get_risk_history(
        limit=7
    )

    assert result == []

    assert (
        captured["path"]
        == "/api/v1/risk/daily"
    )

    assert captured["params"] == {
        "limit": 7,
    }
