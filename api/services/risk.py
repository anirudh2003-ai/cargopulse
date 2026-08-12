"""Read-only database queries for CargoPulse risk analytics."""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


RISK_DETAIL_COLUMNS = """
    metric_date,
    risk_score,
    risk_level,
    score_confidence,
    risk_change_1d,
    previous_risk_level,
    risk_trend,
    primary_driver,
    primary_driver_points,
    secondary_driver,
    secondary_driver_points,
    tertiary_driver,
    tertiary_driver_points,
    risk_headline,
    risk_explanation,
    terminal_utilisation_pct,
    max_occupied_berths,
    active_calls,
    active_delayed_calls,
    active_severe_calls,
    active_mean_delay_hours,
    utilisation_3d_avg,
    arrivals_3d,
    departures_3d,
    vessel_balance_3d,
    capacity_points,
    saturation_points,
    active_delay_points,
    active_severe_points,
    delay_intensity_points,
    utilisation_3d_points,
    backlog_points
"""


RISK_SUMMARY_COLUMNS = """
    metric_date,
    risk_score,
    risk_level,
    score_confidence,
    risk_trend,
    risk_headline,
    terminal_utilisation_pct,
    max_occupied_berths,
    active_calls,
    active_delayed_calls,
    active_severe_calls,
    active_mean_delay_hours
"""


def fetch_latest_risk(
    engine: Engine,
) -> dict[str, Any] | None:
    """Return the most recent terminal risk record."""

    query = text(
        f"""
        SELECT
            {RISK_DETAIL_COLUMNS}
        FROM dbt_dev.lng_terminal_risk_explanations_daily
        ORDER BY metric_date DESC
        LIMIT 1
        """
    )

    with engine.connect() as connection:
        row = connection.execute(
            query
        ).mappings().one_or_none()

    if row is None:
        return None

    return dict(row)


def fetch_risk_history(
    engine: Engine,
    limit: int,
) -> list[dict[str, Any]]:
    """Return recent terminal risk history."""

    query = text(
        f"""
        SELECT
            {RISK_SUMMARY_COLUMNS}
        FROM dbt_dev.lng_terminal_risk_explanations_daily
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


def fetch_risk_by_date(
    engine: Engine,
    metric_date: date,
) -> dict[str, Any] | None:
    """Return detailed risk for one date."""

    query = text(
        f"""
        SELECT
            {RISK_DETAIL_COLUMNS}
        FROM dbt_dev.lng_terminal_risk_explanations_daily
        WHERE metric_date = :metric_date
        """
    )

    with engine.connect() as connection:
        row = connection.execute(
            query,
            {
                "metric_date": metric_date,
            },
        ).mappings().one_or_none()

    if row is None:
        return None

    return dict(row)
