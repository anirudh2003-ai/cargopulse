"""Pydantic schemas for CargoPulse risk analytics."""

from datetime import date

from pydantic import BaseModel


class RiskSummary(BaseModel):
    """Summary of terminal operational supply risk."""

    metric_date: date
    risk_score: float
    risk_level: str
    score_confidence: str
    risk_trend: str
    risk_headline: str

    terminal_utilisation_pct: float
    max_occupied_berths: int

    active_calls: int
    active_delayed_calls: int
    active_severe_calls: int

    active_mean_delay_hours: float | None


class RiskDetail(RiskSummary):
    """Detailed explainable operational risk record."""

    risk_change_1d: float | None
    previous_risk_level: str | None

    primary_driver: str | None
    primary_driver_points: float | None

    secondary_driver: str | None
    secondary_driver_points: float | None

    tertiary_driver: str | None
    tertiary_driver_points: float | None

    risk_explanation: str

    utilisation_3d_avg: float
    arrivals_3d: float
    departures_3d: float
    vessel_balance_3d: float

    capacity_points: float
    saturation_points: float
    active_delay_points: float
    active_severe_points: float
    delay_intensity_points: float
    utilisation_3d_points: float
    backlog_points: float
