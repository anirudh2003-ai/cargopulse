"""Vessel enrichment pipeline stage."""

from __future__ import annotations

from pipeline.logging_config import get_logger, log_event
from pipeline.run import run_pipeline

logger = get_logger("cargopulse.enrich")


def run_enrich(
    enrichment_limit: int = 50,
    skip_enrichment: bool = False,
) -> None:
    """Queue unseen vessels and run PSIX enrichment."""

    log_event(
        logger,
        "enrichment_started",
        limit=enrichment_limit,
        skip_enrichment=skip_enrichment,
    )

    run_pipeline(
        enrichment_limit=enrichment_limit,
        skip_enrichment=skip_enrichment,
    )

    log_event(
        logger,
        "enrichment_complete",
    )
