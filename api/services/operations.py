"""Read-only queries for CargoPulse operational analytics."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


CALL_COLUMNS = """
    validated_call_id,
    mmsi,
    imo,
    vessel_name,
    terminal_id,
    berth_zone_code,
    berth_arrival_time,
    berth_departure_time,
    berth_duration_minutes,
    expected_duration_minutes,
    duration_variance_minutes,
    estimated_delay_minutes,
    estimated_delay_hours,
    delay_band,
    delay_quality,
    baseline_scope,
    baseline_sample_size,
    berth_detection_confidence,
    berth_continuity,
    movement_coverage,
    inbound_transit_minutes,
    outbound_transit_minutes,
    arrival_metric_date,
    arrival_day_terminal_arrivals,
    arrival_day_terminal_departures,
    arrival_day_max_occupied_berths,
    arrival_day_terminal_utilisation_pct,
    arrival_day_mean_occupied_berths
"""


def fetch_calls(
    engine: Engine,
    limit: int,
) -> list[dict[str, Any]]:
    """Return recent validated LNG calls."""

    query = text(
        f"""
        SELECT
            {CALL_COLUMNS}
        FROM dbt_dev.lng_call_analytics
        ORDER BY berth_arrival_time DESC
        LIMIT :limit
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"limit": limit},
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def fetch_call_by_id(
    engine: Engine,
    validated_call_id: int,
) -> dict[str, Any] | None:
    """Return one validated LNG call."""

    query = text(
        f"""
        SELECT
            {CALL_COLUMNS}
        FROM dbt_dev.lng_call_analytics
        WHERE validated_call_id = :validated_call_id
        """
    )

    with engine.connect() as connection:
        row = connection.execute(
            query,
            {
                "validated_call_id": validated_call_id,
            },
        ).mappings().one_or_none()

    if row is None:
        return None

    return dict(row)


def fetch_berth_performance(
    engine: Engine,
) -> list[dict[str, Any]]:
    """Return aggregate berth performance."""

    query = text(
        """
        SELECT
            berth_zone_code,
            total_calls,
            scored_calls,
            elevated_calls,
            high_delay_calls,
            severe_delay_calls,
            median_duration_minutes,
            p90_duration_minutes,
            mean_estimated_delay_minutes,
            occupied_minutes,
            utilisation_pct
        FROM dbt_dev.lng_berth_performance
        ORDER BY berth_zone_code
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            query
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def fetch_terminal_daily_metrics(
    engine: Engine,
    limit: int,
) -> list[dict[str, Any]]:
    """Return recent daily terminal metrics."""

    query = text(
        """
        SELECT
            metric_date,
            arrivals,
            departures,
            occupied_berth_minutes,
            max_occupied_berths,
            terminal_utilisation_pct,
            mean_occupied_berths,
            mean_arrival_delay_minutes,
            severe_delay_arrivals
        FROM dbt_dev.lng_terminal_daily_metrics
        ORDER BY metric_date DESC
        LIMIT :limit
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"limit": limit},
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]
