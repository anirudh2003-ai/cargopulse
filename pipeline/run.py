"""Run CargoPulse vessel enrichment as one pipeline command."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from enrichment.run_enrichment import process_queue


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENV_PATH = PROJECT_ROOT / ".env"

ENQUEUE_SQL_PATH = (
    PROJECT_ROOT
    / "enrichment"
    / "enqueue_unseen_vessels.sql"
)


def load_database_url() -> str:
    """Load DATABASE_URL from the project .env file."""

    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f".env file was not found at: {ENV_PATH}"
        )

    load_dotenv(dotenv_path=ENV_PATH)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from .env"
        )

    return database_url


def verify_required_objects(engine: Engine) -> None:
    """Confirm the required tables and views exist."""

    required_objects = [
        "public.validated_terminal_calls",
        "public.vessel_registry",
        "public.vessel_enrichment_queue",
        "public.confirmed_lng_port_calls",
    ]

    with engine.connect() as connection:
        for object_name in required_objects:
            exists = connection.execute(
                text(
                    """
                    SELECT to_regclass(:object_name)
                    """
                ),
                {"object_name": object_name},
            ).scalar_one_or_none()

            if exists is None:
                raise RuntimeError(
                    f"Required database object does not exist: "
                    f"{object_name}"
                )


def execute_sql_file(
    engine: Engine,
    sql_path: Path,
) -> int:
    """Execute a SQL file and return affected row count."""

    if not sql_path.exists():
        raise FileNotFoundError(
            f"SQL file does not exist: {sql_path}"
        )

    sql = sql_path.read_text(encoding="utf-8").strip()

    if not sql:
        raise RuntimeError(
            f"SQL file is empty: {sql_path}"
        )

    with engine.begin() as connection:
        result = connection.exec_driver_sql(sql)

        if result.rowcount is None or result.rowcount < 0:
            return 0

        return int(result.rowcount)


def get_pipeline_counts(
    engine: Engine,
) -> dict[str, Any]:
    """Return the current CargoPulse enrichment counts."""

    query = text(
        """
        SELECT
            (
                SELECT COUNT(*)
                FROM public.validated_terminal_calls
            ) AS validated_calls,

            (
                SELECT COUNT(*)
                FROM public.vessel_registry
            ) AS registry_vessels,

            (
                SELECT COUNT(*)
                FROM public.vessel_registry
                WHERE classification_status = 'confirmed_lng'
            ) AS confirmed_lng_vessels,

            (
                SELECT COUNT(*)
                FROM public.vessel_enrichment_queue
                WHERE queue_status = 'pending'
            ) AS pending_queue,

            (
                SELECT COUNT(*)
                FROM public.vessel_enrichment_queue
                WHERE queue_status = 'processing'
            ) AS processing_queue,

            (
                SELECT COUNT(*)
                FROM public.vessel_enrichment_queue
                WHERE queue_status = 'completed'
            ) AS completed_queue,

            (
                SELECT COUNT(*)
                FROM public.vessel_enrichment_queue
                WHERE queue_status = 'needs_review'
            ) AS needs_review_queue,

            (
                SELECT COUNT(*)
                FROM public.vessel_enrichment_queue
                WHERE queue_status = 'failed'
            ) AS failed_queue,

            (
                SELECT COUNT(*)
                FROM public.confirmed_lng_port_calls
            ) AS confirmed_lng_calls
        """
    )

    with engine.connect() as connection:
        row = connection.execute(
            query
        ).mappings().one()

    return dict(row)


def print_counts(
    title: str,
    counts: dict[str, Any],
) -> None:
    """Print pipeline counts in a readable format."""

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    print(
        f"Validated terminal calls: "
        f"{counts['validated_calls']}"
    )

    print(
        f"Registry vessels:         "
        f"{counts['registry_vessels']}"
    )

    print(
        f"Confirmed LNG vessels:    "
        f"{counts['confirmed_lng_vessels']}"
    )

    print(
        f"Pending queue:             "
        f"{counts['pending_queue']}"
    )

    print(
        f"Processing queue:          "
        f"{counts['processing_queue']}"
    )

    print(
        f"Completed queue:           "
        f"{counts['completed_queue']}"
    )

    print(
        f"Needs review:              "
        f"{counts['needs_review_queue']}"
    )

    print(
        f"Failed queue:              "
        f"{counts['failed_queue']}"
    )

    print(
        f"Confirmed LNG calls:       "
        f"{counts['confirmed_lng_calls']}"
    )


def run_pipeline(
    enrichment_limit: int,
    skip_enrichment: bool,
) -> None:
    """Run unseen-vessel queueing and PSIX enrichment."""

    database_url = load_database_url()

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        print("Checking required database objects...")

        verify_required_objects(engine)

        before_counts = get_pipeline_counts(engine)

        print_counts(
            "Before pipeline",
            before_counts,
        )

        print("\nStage 1: Queueing unseen vessels...")

        affected_rows = execute_sql_file(
            engine,
            ENQUEUE_SQL_PATH,
        )

        print(
            f"Queue rows inserted or updated: "
            f"{affected_rows}"
        )

        queued_counts = get_pipeline_counts(engine)

        print(
            f"Pending vessels after queueing: "
            f"{queued_counts['pending_queue']}"
        )

        if skip_enrichment:
            print(
                "\nStage 2: PSIX enrichment skipped."
            )
        else:
            print(
                "\nStage 2: Running PSIX enrichment..."
            )

            process_queue(
                limit=enrichment_limit
            )

        after_counts = get_pipeline_counts(engine)

        print_counts(
            "After pipeline",
            after_counts,
        )

        print("\nPipeline completed successfully.")

        if after_counts["pending_queue"] > 0:
            print(
                "\nSome vessels remain pending. "
                "Run the pipeline again to process "
                "the next batch."
            )

        if after_counts["needs_review_queue"] > 0:
            print(
                "\nSome vessels require review because "
                "PSIX did not return sufficiently clear "
                "classification evidence."
            )

        if after_counts["failed_queue"] > 0:
            print(
                "\nSome vessel lookups failed temporarily. "
                "They will become eligible for retry after "
                "their next_attempt_at time."
            )

    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Queue unseen vessels, enrich them through "
            "USCG PSIX and update CargoPulse classifications."
        )
    )

    parser.add_argument(
        "--enrichment-limit",
        type=int,
        default=50,
        help=(
            "Maximum number of queued vessels to enrich. "
            "Default: 50."
        ),
    )

    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help=(
            "Queue unseen vessels without calling PSIX."
        ),
    )

    arguments = parser.parse_args()

    if arguments.enrichment_limit < 1:
        parser.error(
            "--enrichment-limit must be at least 1"
        )

    try:
        run_pipeline(
            enrichment_limit=(
                arguments.enrichment_limit
            ),
            skip_enrichment=(
                arguments.skip_enrichment
            ),
        )

    except Exception as error:
        print(
            f"\nPipeline failed: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )

        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
