"""Pydantic schemas for CargoPulse operational analytics."""

from datetime import date, datetime

from pydantic import BaseModel


class CallAnalytics(BaseModel):
    """Analytics for one validated LNG terminal call."""

    validated_call_id: int
    mmsi: int
    imo: int | None
    vessel_name: str | None

    terminal_id: int
    berth_zone_code: str

    berth_arrival_time: datetime
    berth_departure_time: datetime

    berth_duration_minutes: float
    expected_duration_minutes: float | None
    duration_variance_minutes: float | None

    estimated_delay_minutes: float | None
    estimated_delay_hours: float | None

    delay_band: str
    delay_quality: str
    baseline_scope: str

    baseline_sample_size: int

    berth_detection_confidence: str
    berth_continuity: str
    movement_coverage: str

    inbound_transit_minutes: float | None
    outbound_transit_minutes: float | None

    arrival_metric_date: date

    arrival_day_terminal_arrivals: int
    arrival_day_terminal_departures: int
    arrival_day_max_occupied_berths: int

    arrival_day_terminal_utilisation_pct: float
    arrival_day_mean_occupied_berths: float


class BerthPerformance(BaseModel):
    """Aggregate performance metrics for one berth."""

    berth_zone_code: str

    total_calls: int
    scored_calls: int
    elevated_calls: int
    high_delay_calls: int
    severe_delay_calls: int

    median_duration_minutes: float
    p90_duration_minutes: float
    mean_estimated_delay_minutes: float

    occupied_minutes: float
    utilisation_pct: float


class TerminalDailyMetrics(BaseModel):
    """Daily LNG terminal operational metrics."""

    metric_date: date

    arrivals: int
    departures: int

    occupied_berth_minutes: float
    max_occupied_berths: int
    terminal_utilisation_pct: float
    mean_occupied_berths: float

    mean_arrival_delay_minutes: float | None
    severe_delay_arrivals: int
