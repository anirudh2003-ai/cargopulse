"""Validation for the cleaned AIS Parquet dataset."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from ingestion.clean_ais import COLUMN_MAPPING
from pipeline.config import load_settings
from pipeline.logging_config import get_logger, log_event

logger = get_logger("cargopulse.validate_raw")


def run_validate_raw(
    parquet_path: Path | None = None,
) -> int:
    """Validate the silver AIS Parquet file."""

    settings = load_settings()

    if parquet_path is None:
        parquet_path = settings.silver_ais_path

    log_event(
        logger,
        "raw_validation_started",
        path=parquet_path,
    )

    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Silver AIS file does not exist: {parquet_path}"
        )

    parquet_file = pq.ParquetFile(parquet_path)

    row_count = parquet_file.metadata.num_rows

    if row_count <= 0:
        raise RuntimeError(
            "Silver AIS Parquet contains zero rows"
        )

    actual_columns = set(
        parquet_file.schema_arrow.names
    )

    required_columns = set(
        COLUMN_MAPPING.values()
    )

    missing_columns = sorted(
        required_columns - actual_columns
    )

    if missing_columns:
        raise RuntimeError(
            "Silver AIS Parquet is missing columns: "
            f"{missing_columns}"
        )

    log_event(
        logger,
        "raw_validation_complete",
        rows=row_count,
        columns=len(actual_columns),
    )

    return row_count
