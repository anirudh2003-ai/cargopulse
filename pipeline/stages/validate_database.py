"""Database data-quality validation stage."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from pipeline.config import load_settings
from pipeline.logging_config import get_logger, log_event

logger = get_logger("cargopulse.validate_database")


def run_validate_database() -> dict[str, int]:
    """Validate core PostgreSQL data after loading and enrichment."""

    settings = load_settings()

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    log_event(
        logger,
        "database_validation_started",
    )

    query = text(
        """
        SELECT
            (
                SELECT COUNT(*)
                FROM public.ais_positions
            ) AS ais_positions,

            (
                SELECT COUNT(*)
                FROM public.ais_positions
                WHERE location IS NULL
            ) AS missing_locations,

            (
                SELECT COUNT(*)
                FROM public.vessel_registry
            ) AS registry_vessels,

            (
                SELECT COUNT(*)
                FROM public.vessel_enrichment_queue
                WHERE queue_status = 'processing'
            ) AS stuck_processing
        """
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

    if results["ais_positions"] <= 0:
        raise RuntimeError(
            "Data quality failure: no AIS positions"
        )

    if results["missing_locations"] != 0:
        raise RuntimeError(
            "Data quality failure: "
            f"{results['missing_locations']} AIS rows "
            "have missing PostGIS locations"
        )

    if results["stuck_processing"] != 0:
        raise RuntimeError(
            "Data quality failure: "
            f"{results['stuck_processing']} enrichment records "
            "remain in processing state"
        )

    log_event(
        logger,
        "database_validation_complete",
        **results,
    )

    return results
