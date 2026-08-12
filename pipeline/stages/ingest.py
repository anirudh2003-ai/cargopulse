"""AIS ingestion and cleaning stage."""

from __future__ import annotations

from pathlib import Path

from ingestion.clean_ais import clean_csv
from pipeline.config import load_settings
from pipeline.logging_config import get_logger, log_event


logger = get_logger("cargopulse.ingest")


def run_ingest(
    input_csv: Path,
    output_path: Path | None = None,
    chunk_size: int = 250_000,
) -> Path:
    """Clean raw NOAA AIS CSV into the silver Parquet dataset."""

    settings = load_settings()

    if output_path is None:
        output_path = settings.silver_ais_path

    log_event(
        logger,
        "ingestion_started",
        input=input_csv,
        output=output_path,
    )

    clean_csv(
        input_path=input_csv,
        output_path=output_path,
        chunk_size=chunk_size,
    )

    if not output_path.exists():
        raise RuntimeError(
            f"Ingestion did not create expected file: {output_path}"
        )

    log_event(
        logger,
        "ingestion_complete",
        output=output_path,
    )

    return output_path
