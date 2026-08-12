"""HTTP client for the CargoPulse Streamlit dashboard."""

from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_API_URL = "http://127.0.0.1:8000"


def get_api_base_url() -> str:
    """Return the configured CargoPulse API base URL."""

    return os.getenv(
        "CARGOPULSE_API_URL",
        DEFAULT_API_URL,
    ).rstrip("/")


def get_json(
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    """Fetch JSON data from the CargoPulse API."""

    url = f"{get_api_base_url()}{path}"

    response = requests.get(
        url,
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def get_health() -> dict[str, Any]:
    """Return API health information."""

    return get_json("/health")


def get_latest_risk() -> dict[str, Any]:
    """Return the latest terminal risk record."""

    return get_json(
        "/api/v1/risk/latest"
    )


def get_risk_history(
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return recent risk history."""

    return get_json(
        "/api/v1/risk/daily",
        params={
            "limit": limit,
        },
    )


def get_terminal_daily(
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return recent terminal metrics."""

    return get_json(
        "/api/v1/terminal/daily",
        params={
            "limit": limit,
        },
    )


def get_berths() -> list[dict[str, Any]]:
    """Return berth performance metrics."""

    return get_json(
        "/api/v1/berths"
    )


def get_calls(
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent LNG terminal calls."""

    return get_json(
        "/api/v1/calls",
        params={
            "limit": limit,
        },
    )
