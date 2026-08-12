"""Final CargoPulse pipeline quality gate."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from pipeline.config import load_settings
from pipeline.logging_config import get_logger, log_event


logger = get_logger("cargopulse.quality_gate")


def run_quality_gate() -> dict[str, int]:
    """Validate critical final analytics outputs."""

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
                FROM dbt_dev.lng_call_analytics
            ) AS call_analytics,

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
            ) AS risk_explanations,

            (
                SELECT COUNT(*)
                FROM dbt_dev.lng_terminal_risk_score_daily
                WHERE risk_score < 0
                   OR risk_score > 100
            ) AS invalid_risk_scores
        """
    )

    log_event(
        logger,
        "quality_gate_started",
    )

    try:
        with engine.connect() as connection:
            row = connection.execute(
                query
            ).mappings().one()
    finally:
        engine.dispose()

    results = {
        key: int(value)
        for key, value in row.items()
    }

    required_outputs = [
        "call_analytics",
        "daily_metrics",
        "historical_baselines",
        "risk_scores",
        "risk_explanations",
    ]

    for output in required_outputs:
        if results[output] <= 0:
            raise RuntimeError(
                f"Quality gate failed: {output} is empty"
            )

    if results["invalid_risk_scores"] != 0:
        raise RuntimeError(
            "Quality gate failed: invalid risk scores found"
        )

    log_event(
        logger,
        "quality_gate_passed",
        **results,
    )

    return results
