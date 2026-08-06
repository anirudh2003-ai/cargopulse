"""Automatically enrich previously unseen vessels using USCG PSIX."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from enrichment.classification import (
    classify_psix_vessel,
)
from enrichment.uscg_psix_provider import (
    UscgPsixProvider,
)


def load_database_url() -> str:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"

    if not env_path.exists():
        raise FileNotFoundError(
            f".env was not found at {env_path}"
        )

    load_dotenv(dotenv_path=env_path)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from .env"
        )

    return database_url


def optional_integer(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def claim_queue_records(
    engine,
    limit: int,
) -> list[dict[str, Any]]:
    """
    Atomically claim pending queue records.

    FOR UPDATE SKIP LOCKED prevents two workers from processing
    the same vessel simultaneously.
    """

    claim_statement = text(
        """
        WITH selected AS (
            SELECT lookup_key
            FROM public.vessel_enrichment_queue
            WHERE
                queue_status = 'pending'
                OR (
                    queue_status = 'failed'
                    AND (
                        next_attempt_at IS NULL
                        OR next_attempt_at <= NOW()
                    )
                )
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
        )

        UPDATE public.vessel_enrichment_queue AS queue
        SET
            queue_status = 'processing',
            attempt_count = attempt_count + 1,
            last_attempt_at = NOW(),
            updated_at = NOW()
        FROM selected
        WHERE queue.lookup_key = selected.lookup_key

        RETURNING
            queue.lookup_key,
            queue.imo,
            queue.mmsi,
            queue.observed_vessel_name,
            queue.attempt_count
        """
    )

    with engine.begin() as connection:
        rows = connection.execute(
            claim_statement,
            {"limit": limit},
        ).mappings().all()

    return [dict(row) for row in rows]


def mark_needs_review(
    engine,
    lookup_key: str,
    reason: str,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE public.vessel_enrichment_queue
                SET
                    queue_status = 'needs_review',
                    last_error = :reason,
                    next_attempt_at = NULL,
                    updated_at = NOW()
                WHERE lookup_key = :lookup_key
                """
            ),
            {
                "lookup_key": lookup_key,
                "reason": reason,
            },
        )


def mark_failed(
    engine,
    lookup_key: str,
    error: Exception,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE public.vessel_enrichment_queue
                SET
                    queue_status = 'failed',
                    last_error = :error,
                    next_attempt_at =
                        NOW() + INTERVAL '1 hour',
                    updated_at = NOW()
                WHERE lookup_key = :lookup_key
                """
            ),
            {
                "lookup_key": lookup_key,
                "error": (
                    f"{type(error).__name__}: {error}"
                )[:2000],
            },
        )


def save_result(
    engine,
    queue_record: dict[str, Any],
    result,
) -> str:
    (
        _normalised_type,
        classification_status,
    ) = classify_psix_vessel(
        service_type=result.service_type,
        service_sub_type=result.service_sub_type,
        cargo_authorization=result.cargo_description,
    )

    registry_upsert = text(
        """
        INSERT INTO public.vessel_registry (
            imo,
            mmsi,
            ais_vessel_name,
            registry_vessel_name,
            psix_vessel_id,
            service_type,
            service_sub_type,
            cargo_authorization,
            flag,
            vessel_status,
            classification_status,
            source_name,
            source_reference,
            last_checked_at,
            created_at,
            updated_at
        )
        VALUES (
            :imo,
            :mmsi,
            :ais_vessel_name,
            :registry_vessel_name,
            :psix_vessel_id,
            :service_type,
            :service_sub_type,
            :cargo_authorization,
            :flag,
            :vessel_status,
            :classification_status,
            'USCG PSIX',
            :source_reference,
            NOW(),
            NOW(),
            NOW()
        )

        ON CONFLICT (imo)
        DO UPDATE SET
            mmsi = EXCLUDED.mmsi,

            ais_vessel_name =
                EXCLUDED.ais_vessel_name,

            registry_vessel_name =
                EXCLUDED.registry_vessel_name,

            psix_vessel_id =
                EXCLUDED.psix_vessel_id,

            service_type =
                EXCLUDED.service_type,

            service_sub_type =
                EXCLUDED.service_sub_type,

            cargo_authorization =
                EXCLUDED.cargo_authorization,

            flag =
                EXCLUDED.flag,

            vessel_status =
                EXCLUDED.vessel_status,

            classification_status =
                EXCLUDED.classification_status,

            source_name =
                EXCLUDED.source_name,

            source_reference =
                EXCLUDED.source_reference,

            last_checked_at = NOW(),
            updated_at = NOW()
        """
    )

    if classification_status in {
        "confirmed_lng",
        "confirmed_non_lng",
    }:
        queue_status = "completed"
    else:
        queue_status = "needs_review"

    queue_update = text(
        """
        UPDATE public.vessel_enrichment_queue
        SET
            queue_status = :queue_status,
            last_error = NULL,
            next_attempt_at = NULL,
            updated_at = NOW()
        WHERE lookup_key = :lookup_key
        """
    )

    imo = int(result.requested_imo)

    with engine.begin() as connection:
        connection.execute(
            registry_upsert,
            {
                "imo": imo,
                "mmsi": optional_integer(
                    queue_record.get("mmsi")
                ),
                "ais_vessel_name": (
                    queue_record.get(
                        "observed_vessel_name"
                    )
                ),
                "registry_vessel_name": (
                    result.vessel_name
                ),
                "psix_vessel_id": (
                    result.vessel_id
                ),
                "service_type": (
                    result.service_type
                ),
                "service_sub_type": (
                    result.service_sub_type
                ),
                "cargo_authorization": (
                    result.cargo_description
                ),
                "flag": result.flag,
                "vessel_status": result.status,
                "classification_status": (
                    classification_status
                ),
                "source_reference": (
                    f"USCG PSIX VesselID "
                    f"{result.vessel_id}; IMO {imo}"
                ),
            },
        )

        connection.execute(
            queue_update,
            {
                "queue_status": queue_status,
                "lookup_key": (
                    queue_record["lookup_key"]
                ),
            },
        )

    return classification_status


def process_queue(limit: int) -> None:
    database_url = load_database_url()

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    provider = UscgPsixProvider()

    records = claim_queue_records(
        engine=engine,
        limit=limit,
    )

    print(f"Queue records claimed: {len(records)}")

    for index, record in enumerate(
        records,
        start=1,
    ):
        lookup_key = record["lookup_key"]
        imo = optional_integer(record.get("imo"))
        vessel_name = record.get(
            "observed_vessel_name"
        )

        print("\n" + "=" * 70)
        print(
            f"[{index}/{len(records)}] "
            f"{vessel_name} — IMO {imo}"
        )

        if imo is None:
            print("No IMO available: needs review")

            mark_needs_review(
                engine,
                lookup_key,
                "USCG PSIX enrichment requires an IMO",
            )

            continue

        try:
            result = provider.lookup(imo)

            if result is None:
                print("No PSIX record found")

                mark_needs_review(
                    engine,
                    lookup_key,
                    "No USCG PSIX record found",
                )

                continue

            if str(result.vin) != str(imo):
                print(
                    "Returned identification does not "
                    "match the requested IMO"
                )

                mark_needs_review(
                    engine,
                    lookup_key,
                    (
                        "PSIX returned identification "
                        f"{result.vin} for requested "
                        f"IMO {imo}"
                    ),
                )

                continue

            classification_status = save_result(
                engine=engine,
                queue_record=record,
                result=result,
            )

            print(
                f"Registry vessel: "
                f"{result.vessel_name}"
            )
            print(
                f"Service subtype: "
                f"{result.service_sub_type}"
            )
            print(
                f"Classification: "
                f"{classification_status}"
            )

        except Exception as error:
            print(
                f"ERROR: {type(error).__name__}: "
                f"{error}"
            )

            mark_failed(
                engine,
                lookup_key,
                error,
            )

    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Maximum number of queued vessels "
            "to process."
        ),
    )

    arguments = parser.parse_args()

    process_queue(arguments.limit)


if __name__ == "__main__":
    main()
