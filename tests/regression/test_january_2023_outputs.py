"""Regression tests for the validated January 2023 dataset."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from pipeline.config import load_settings

EXPECTED_COUNTS = {
    "confirmed_lng_calls": 34,
    "operational_calls": 34,
    "daily_metrics": 30,
    "historical_baselines": 90,
    "risk_scores": 30,
    "risk_explanations": 30,
}


@pytest.mark.regression
def test_validated_january_2023_counts():
    settings = load_settings()

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    query = text(
        """
        SELECT
            (
                SELECT COUNT(*)
                FROM public.confirmed_lng_port_calls
            ) AS confirmed_lng_calls,

            (
                SELECT COUNT(*)
                FROM dbt_dev.int_lng_call_operations
            ) AS operational_calls,

            (
                SELECT COUNT(*)
                FROM dbt_dev.lng_terminal_daily_metrics
            ) AS daily_metrics,

            (
                SELECT COUNT(*)
                FROM dbt_dev.lng_historical_duration_baseline_daily
            ) AS historical_baselines,

            (
                SELECT COUNT(*)
                FROM dbt_dev.lng_terminal_risk_score_daily
            ) AS risk_scores,

            (
                SELECT COUNT(*)
                FROM dbt_dev.lng_terminal_risk_explanations_daily
            ) AS risk_explanations
        """
    )

    try:
        with engine.connect() as connection:
            actual = dict(
                connection.execute(
                    query
                ).mappings().one()
            )
    finally:
        engine.dispose()

    assert actual == EXPECTED_COUNTS


@pytest.mark.regression
def test_highest_risk_day_is_preserved():
    settings = load_settings()

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    query = text(
        """
        SELECT
            metric_date,
            risk_score,
            risk_level
        FROM dbt_dev.lng_terminal_risk_score_daily
        ORDER BY risk_score DESC
        LIMIT 1
        """
    )

    try:
        with engine.connect() as connection:
            row = connection.execute(
                query
            ).mappings().one()
    finally:
        engine.dispose()

    assert str(row["metric_date"]) == "2023-01-18"
    assert float(row["risk_score"]) == 72.5
    assert row["risk_level"] == "high"
