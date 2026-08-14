"""CargoPulse end-to-end pipeline runner."""

from __future__ import annotations

from pathlib import Path

from pipeline.logging_config import get_logger, log_event
from pipeline.stages.enrich import run_enrich
from pipeline.stages.export import run_export
from pipeline.stages.ingest import run_ingest
from pipeline.stages.load import run_load
from pipeline.stages.quality_gate import run_quality_gate
from pipeline.stages.transform import run_transform
from pipeline.stages.validate_database import (
    run_validate_database,
)
from pipeline.stages.validate_raw import run_validate_raw

logger = get_logger("cargopulse.runner")


def run_all(
    input_csv: Path,
    enrichment_limit: int = 50,
    skip_enrichment: bool = False,
) -> None:
    """Run the complete CargoPulse data pipeline."""

    log_event(
        logger,
        "pipeline_started",
        input=input_csv,
    )

    silver_path = run_ingest(
        input_csv=input_csv,
    )

    run_validate_raw(
        parquet_path=silver_path,
    )

    run_load(
        parquet_path=silver_path,
    )

    run_enrich(
        enrichment_limit=enrichment_limit,
        skip_enrichment=skip_enrichment,
    )

    run_validate_database()

    run_transform()

    run_export()

    run_quality_gate()

    log_event(
        logger,
        "pipeline_complete",
        status="success",
    )
