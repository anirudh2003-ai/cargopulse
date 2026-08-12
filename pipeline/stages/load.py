"""PostgreSQL AIS loading stage."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from database.load_silver import load_parquet
from pipeline.config import load_settings
from pipeline.logging_config import get_logger, log_event


logger = get_logger("cargopulse.load")


def run_load(
    parquet_path: Path | None = None,
    batch_size: int = 100_000,
) -> int:
    """Load the silver AIS dataset into PostgreSQL."""

    settings = load_settings()

    if parquet_path is None:
        parquet_path = settings.silver_ais_path

    log_event(
        logger,
        "database_load_started",
        path=parquet_path,
        batch_size=batch_size,
    )

    load_parquet(
        parquet_path=parquet_path,
        batch_size=batch_size,
    )

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            position_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM public.ais_positions
                    """
                )
            ).scalar_one()
    finally:
        engine.dispose()

    if position_count <= 0:
        raise RuntimeError(
            "PostgreSQL ais_positions contains zero rows"
        )

    log_event(
        logger,
        "database_load_complete",
        rows=position_count,
    )

    return int(position_count)
