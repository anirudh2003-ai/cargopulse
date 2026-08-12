"""Export CargoPulse gold analytics datasets."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine

from pipeline.config import load_settings
from pipeline.logging_config import get_logger, log_event


logger = get_logger("cargopulse.export")


EXPORTS = {
    "lng_call_analytics": (
        "validated_call_id",
        "lng_call_analytics.csv",
    ),
    "lng_terminal_daily_metrics": (
        "metric_date",
        "lng_terminal_daily_metrics.csv",
    ),
    "lng_berth_performance": (
        "berth_zone_code",
        "lng_berth_performance.csv",
    ),
    "lng_terminal_risk_score_daily": (
        "metric_date",
        "lng_terminal_risk_score_daily.csv",
    ),
    "lng_terminal_risk_explanations_daily": (
        "metric_date",
        "lng_terminal_risk_explanations_daily.csv",
    ),
}


def run_export() -> dict[str, int]:
    """Export consumer-facing dbt models to data/gold."""

    settings = load_settings()

    settings.gold_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    results: dict[str, int] = {}

    log_event(
        logger,
        "gold_export_started",
    )

    try:
        for table_name, (
            order_column,
            filename,
        ) in EXPORTS.items():

            query = (
                f"SELECT * "
                f"FROM dbt_dev.{table_name} "
                f"ORDER BY {order_column}"
            )

            dataframe = pd.read_sql_query(
                query,
                engine,
            )

            output_path = (
                settings.gold_dir / filename
            )

            dataframe.to_csv(
                output_path,
                index=False,
            )

            results[table_name] = len(dataframe)

            log_event(
                logger,
                "gold_dataset_exported",
                dataset=table_name,
                rows=len(dataframe),
                path=output_path,
            )

    finally:
        engine.dispose()

    log_event(
        logger,
        "gold_export_complete",
        datasets=len(results),
    )

    return results
