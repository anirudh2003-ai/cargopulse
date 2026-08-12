"""Integration tests for CargoPulse vessel-enrichment edge cases.

These tests use the real PostgreSQL queue and registry tables but mock
the external USCG PSIX provider. Test rows are removed automatically.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from enrichment.run_enrichment import process_queue


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

FAILURE_LOOKUP_KEY = "test:psix-temporary-failure"
FAILURE_IMO = 9990001

AMBIGUOUS_LOOKUP_KEY = "test:psix-ambiguous"
AMBIGUOUS_IMO = 9990002
AMBIGUOUS_PSIX_ID = 9900002

NO_IMO_LOOKUP_KEY = "test:no-imo"
NO_IMO_MMSI = 999000003

TEST_LOOKUP_KEYS = [
    FAILURE_LOOKUP_KEY,
    AMBIGUOUS_LOOKUP_KEY,
    NO_IMO_LOOKUP_KEY,
]

TEST_IMOS = [
    FAILURE_IMO,
    AMBIGUOUS_IMO,
]


def create_test_engine() -> Engine:
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f".env was not found at {ENV_PATH}"
        )

    load_dotenv(dotenv_path=ENV_PATH)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from .env"
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def remove_test_records(engine: Engine) -> None:
    """Remove synthetic queue and registry records."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM public.vessel_enrichment_queue
                WHERE lookup_key = ANY(:lookup_keys)
                """
            ),
            {"lookup_keys": TEST_LOOKUP_KEYS},
        )

        connection.execute(
            text(
                """
                DELETE FROM public.vessel_registry
                WHERE imo = ANY(:imos)
                """
            ),
            {"imos": TEST_IMOS},
        )


@pytest.fixture()
def engine() -> Engine:
    test_engine = create_test_engine()

    remove_test_records(test_engine)

    try:
        yield test_engine
    finally:
        remove_test_records(test_engine)
        test_engine.dispose()


def read_queue_record(
    engine: Engine,
    lookup_key: str,
) -> dict:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    lookup_key,
                    imo,
                    mmsi,
                    queue_status,
                    attempt_count,
                    last_attempt_at,
                    next_attempt_at,
                    last_error
                FROM public.vessel_enrichment_queue
                WHERE lookup_key = :lookup_key
                """
            ),
            {"lookup_key": lookup_key},
        ).mappings().one()

    return dict(row)


def test_temporary_failure_becomes_failed(
    engine: Engine,
) -> None:
    """A temporary provider error must be retried later."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.vessel_enrichment_queue (
                    lookup_key,
                    imo,
                    mmsi,
                    observed_vessel_name,
                    queue_status
                )
                VALUES (
                    :lookup_key,
                    :imo,
                    :mmsi,
                    :vessel_name,
                    'pending'
                )
                """
            ),
            {
                "lookup_key": FAILURE_LOOKUP_KEY,
                "imo": FAILURE_IMO,
                "mmsi": 999000001,
                "vessel_name": "TEST API FAILURE",
            },
        )

    with patch(
        "enrichment.run_enrichment.UscgPsixProvider"
    ) as provider_class:
        provider = provider_class.return_value

        provider.lookup.side_effect = TimeoutError(
            "Simulated temporary PSIX timeout"
        )

        process_queue(limit=1)

        provider.lookup.assert_called_once_with(
            FAILURE_IMO
        )

    queue_record = read_queue_record(
        engine,
        FAILURE_LOOKUP_KEY,
    )

    print("\nTemporary-failure result:")
    print(queue_record)

    assert queue_record["queue_status"] == "failed"
    assert queue_record["attempt_count"] == 1
    assert queue_record["last_attempt_at"] is not None
    assert queue_record["next_attempt_at"] is not None
    assert queue_record["last_error"] is not None
    assert "TimeoutError" in queue_record["last_error"]


def test_ambiguous_result_becomes_needs_review(
    engine: Engine,
) -> None:
    """A broad Tank Ship result without a subtype is ambiguous."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.vessel_enrichment_queue (
                    lookup_key,
                    imo,
                    mmsi,
                    observed_vessel_name,
                    queue_status
                )
                VALUES (
                    :lookup_key,
                    :imo,
                    :mmsi,
                    :vessel_name,
                    'pending'
                )
                """
            ),
            {
                "lookup_key": AMBIGUOUS_LOOKUP_KEY,
                "imo": AMBIGUOUS_IMO,
                "mmsi": 999000002,
                "vessel_name": "TEST AMBIGUOUS VESSEL",
            },
        )

    fake_psix_result = SimpleNamespace(
        requested_imo=AMBIGUOUS_IMO,
        vessel_id=AMBIGUOUS_PSIX_ID,
        vessel_name="TEST AMBIGUOUS VESSEL",
        vin=str(AMBIGUOUS_IMO),
        service_type="Tank Ship",
        service_sub_type=None,
        cargo_description=None,
        flag="TEST FLAG",
        status="Active",
    )

    with patch(
        "enrichment.run_enrichment.UscgPsixProvider"
    ) as provider_class:
        provider = provider_class.return_value
        provider.lookup.return_value = fake_psix_result

        process_queue(limit=1)

        provider.lookup.assert_called_once_with(
            AMBIGUOUS_IMO
        )

    queue_record = read_queue_record(
        engine,
        AMBIGUOUS_LOOKUP_KEY,
    )

    with engine.connect() as connection:
        registry_record = connection.execute(
            text(
                """
                SELECT
                    imo,
                    service_type,
                    service_sub_type,
                    classification_status
                FROM public.vessel_registry
                WHERE imo = :imo
                """
            ),
            {"imo": AMBIGUOUS_IMO},
        ).mappings().one()

    print("\nAmbiguous-result queue record:")
    print(queue_record)

    print("\nAmbiguous-result registry record:")
    print(dict(registry_record))

    assert queue_record["queue_status"] == "needs_review"
    assert queue_record["attempt_count"] == 1
    assert queue_record["next_attempt_at"] is None

    assert (
        registry_record["classification_status"]
        == "needs_review"
    )

    assert registry_record["service_type"] == "Tank Ship"
    assert registry_record["service_sub_type"] is None


def test_vessel_without_imo_becomes_needs_review(
    engine: Engine,
) -> None:
    """An MMSI-only vessel must not be sent to the IMO lookup."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO public.vessel_enrichment_queue (
                    lookup_key,
                    imo,
                    mmsi,
                    observed_vessel_name,
                    queue_status
                )
                VALUES (
                    :lookup_key,
                    NULL,
                    :mmsi,
                    :vessel_name,
                    'pending'
                )
                """
            ),
            {
                "lookup_key": NO_IMO_LOOKUP_KEY,
                "mmsi": NO_IMO_MMSI,
                "vessel_name": "TEST MMSI-ONLY VESSEL",
            },
        )

    with patch(
        "enrichment.run_enrichment.UscgPsixProvider"
    ) as provider_class:
        provider = provider_class.return_value

        process_queue(limit=1)

        # No IMO means the external lookup must not run.
        provider.lookup.assert_not_called()

    queue_record = read_queue_record(
        engine,
        NO_IMO_LOOKUP_KEY,
    )

    print("\nNo-IMO result:")
    print(queue_record)

    assert queue_record["queue_status"] == "needs_review"
    assert queue_record["attempt_count"] == 1
    assert queue_record["next_attempt_at"] is None
    assert queue_record["last_error"] is not None
    assert "requires an IMO" in queue_record["last_error"]
