"""Pydantic schemas for API health checks."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health status returned by the CargoPulse API."""

    status: Literal["ok"]
    database: Literal["ok"]
