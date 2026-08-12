"""Command-line interface for CargoPulse."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.logging_config import configure_logging, get_logger, log_event
from pipeline.runner import run_all
from pipeline.stages.enrich import run_enrich
from pipeline.stages.export import run_export
from pipeline.stages.ingest import run_ingest
from pipeline.stages.load import run_load
from pipeline.stages.quality_gate import run_quality_gate
from pipeline.stages.transform import run_transform
from pipeline.stages.validate_database import run_validate_database
from pipeline.stages.validate_raw import run_validate_raw


logger = get_logger("cargopulse.cli")


def build_parser() -> argparse.ArgumentParser:
    """Create the CargoPulse command-line parser."""

    parser = argparse.ArgumentParser(
        prog="cargopulse",
        description="CargoPulse LNG terminal intelligence pipeline.",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=[
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ],
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Clean raw NOAA AIS CSV into silver Parquet.",
    )

    ingest_parser.add_argument(
        "input_csv",
        type=Path,
    )

    ingest_parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    ingest_parser.add_argument(
        "--chunk-size",
        type=int,
        default=250_000,
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate silver AIS and PostgreSQL data.",
    )

    validate_parser.add_argument(
        "--parquet",
        type=Path,
        default=None,
    )

    load_parser = subparsers.add_parser(
        "load",
        help="Load silver AIS Parquet into PostgreSQL.",
    )

    load_parser.add_argument(
        "--parquet",
        type=Path,
        default=None,
    )

    load_parser.add_argument(
        "--batch-size",
        type=int,
        default=100_000,
    )

    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Queue and enrich unseen vessels through USCG PSIX.",
    )

    enrich_parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    enrich_parser.add_argument(
        "--skip-enrichment",
        action="store_true",
    )

    subparsers.add_parser(
        "transform",
        help="Run the complete dbt transformation DAG.",
    )

    subparsers.add_parser(
        "export",
        help="Export gold analytics datasets.",
    )

    subparsers.add_parser(
        "quality-gate",
        help="Run final analytics quality checks.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run the complete CargoPulse pipeline.",
    )

    run_parser.add_argument(
        "input_csv",
        type=Path,
    )

    run_parser.add_argument(
        "--enrichment-limit",
        type=int,
        default=50,
    )

    run_parser.add_argument(
        "--skip-enrichment",
        action="store_true",
    )

    return parser


def execute_command(
    arguments: argparse.Namespace,
) -> None:
    """Execute one CargoPulse CLI command."""

    if arguments.command == "ingest":
        run_ingest(
            input_csv=arguments.input_csv,
            output_path=arguments.output,
            chunk_size=arguments.chunk_size,
        )

    elif arguments.command == "validate":
        silver_rows = run_validate_raw(
            parquet_path=arguments.parquet,
        )

        database_results = run_validate_database()

        log_event(
            logger,
            "validation_complete",
            silver_rows=silver_rows,
            ais_positions=database_results["ais_positions"],
        )

    elif arguments.command == "load":
        run_load(
            parquet_path=arguments.parquet,
            batch_size=arguments.batch_size,
        )

    elif arguments.command == "enrich":
        if arguments.limit < 1:
            raise ValueError(
                "--limit must be at least 1"
            )

        run_enrich(
            enrichment_limit=arguments.limit,
            skip_enrichment=arguments.skip_enrichment,
        )

    elif arguments.command == "transform":
        run_transform()

    elif arguments.command == "export":
        run_export()

    elif arguments.command == "quality-gate":
        run_quality_gate()

    elif arguments.command == "run":
        if arguments.enrichment_limit < 1:
            raise ValueError(
                "--enrichment-limit must be at least 1"
            )

        run_all(
            input_csv=arguments.input_csv,
            enrichment_limit=arguments.enrichment_limit,
            skip_enrichment=arguments.skip_enrichment,
        )

    else:
        raise RuntimeError(
            f"Unknown command: {arguments.command}"
        )


def main() -> None:
    """CargoPulse CLI entry point."""

    parser = build_parser()

    arguments = parser.parse_args()

    configure_logging(
        arguments.log_level
    )

    try:
        execute_command(arguments)

    except KeyboardInterrupt:
        logger.warning(
            "pipeline_interrupted"
        )

        raise SystemExit(130)

    except Exception as error:
        logger.error(
            "command_failed command=%s error_type=%s error=%s",
            arguments.command,
            type(error).__name__,
            error,
        )

        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
