"""Load tested USCG PSIX results into vessel_registry."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from enrichment.classification import (
    classify_psix_vessel,
)

INPUT_PATH = Path(
    "data/reference/psix_test_results.csv"
)


def optional_string(value: Any) -> str | None:
    """Convert a pandas value to a cleaned optional string."""

    if pd.isna(value):
        return None

    cleaned = str(value).strip()

    return cleaned or None


def optional_integer(value: Any) -> int | None:
    """Convert a pandas value to an optional integer."""

    if pd.isna(value):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def boolean_value(value: Any) -> bool:
    """Safely interpret CSV boolean values."""

    if isinstance(value, bool):
        return value

    if pd.isna(value):
        return False

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def identification_digits(
    value: Any,
) -> str | None:
    """Extract digits from a returned PSIX identification."""

    text_value = optional_string(value)

    if not text_value:
        return None

    digits = re.sub(r"\D", "", text_value)

    return digits or None


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"

    if not env_path.exists():
        raise FileNotFoundError(
            f".env file not found at: {env_path}"
        )

    load_dotenv(dotenv_path=env_path)

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from .env"
        )

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Missing PSIX results file: {INPUT_PATH}"
        )

    results = pd.read_csv(
        INPUT_PATH,
        dtype={
            "imo": "Int64",
            "mmsi": "Int64",
            "psix_vessel_id": "Int64",
        },
    )

    required_columns = {
        "imo",
        "mmsi",
        "expected_vessel_name",
        "psix_found",
        "psix_vessel_id",
        "psix_vessel_name",
        "returned_identification",
        "service_type",
        "service_sub_type",
        "cargo_description",
        "flag",
        "status",
        "error",
    }

    missing_columns = required_columns.difference(
        results.columns
    )

    if missing_columns:
        raise ValueError(
            "PSIX results file is missing columns: "
            f"{sorted(missing_columns)}"
        )

    print(f"Rows read from CSV: {len(results)}")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    upsert_statement = text(
        """
        INSERT INTO vessel_registry (
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

    loaded_count = 0
    skipped_count = 0
    classification_counts: dict[str, int] = {}

    with engine.begin() as connection:
        for row in results.itertuples(index=False):
            imo = optional_integer(row.imo)

            if imo is None:
                print("Skipping row with no IMO")
                skipped_count += 1
                continue

            if not boolean_value(row.psix_found):
                print(
                    f"Skipping IMO {imo}: "
                    "PSIX record was not found"
                )
                skipped_count += 1
                continue

            error = optional_string(row.error)

            if error:
                print(
                    f"Skipping IMO {imo}: {error}"
                )
                skipped_count += 1
                continue

            returned_imo = identification_digits(
                row.returned_identification
            )

            if returned_imo != str(imo):
                print(
                    f"Skipping IMO {imo}: PSIX returned "
                    f"identification {returned_imo}"
                )
                skipped_count += 1
                continue

            service_type = optional_string(
                row.service_type
            )

            service_sub_type = optional_string(
                row.service_sub_type
            )

            cargo_authorization = optional_string(
                row.cargo_description
            )

            (
                _normalised_type,
                classification_status,
            ) = classify_psix_vessel(
                service_type=service_type,
                service_sub_type=service_sub_type,
                cargo_authorization=cargo_authorization,
            )

            classification_counts[
                classification_status
            ] = (
                classification_counts.get(
                    classification_status,
                    0,
                )
                + 1
            )

            psix_vessel_id = optional_integer(
                row.psix_vessel_id
            )

            source_reference = (
                f"USCG PSIX VesselID "
                f"{psix_vessel_id}; IMO {imo}"
            )

            connection.execute(
                upsert_statement,
                {
                    "imo": imo,
                    "mmsi": optional_integer(
                        row.mmsi
                    ),
                    "ais_vessel_name": (
                        optional_string(
                            row.expected_vessel_name
                        )
                    ),
                    "registry_vessel_name": (
                        optional_string(
                            row.psix_vessel_name
                        )
                    ),
                    "psix_vessel_id": (
                        psix_vessel_id
                    ),
                    "service_type": service_type,
                    "service_sub_type": (
                        service_sub_type
                    ),
                    "cargo_authorization": (
                        cargo_authorization
                    ),
                    "flag": optional_string(
                        row.flag
                    ),
                    "vessel_status": (
                        optional_string(row.status)
                    ),
                    "classification_status": (
                        classification_status
                    ),
                    "source_reference": (
                        source_reference
                    ),
                },
            )

            loaded_count += 1

    engine.dispose()

    print("\nLoad complete")
    print(f"Rows loaded:  {loaded_count}")
    print(f"Rows skipped: {skipped_count}")

    print("\nClassifications:")

    for status, count in sorted(
        classification_counts.items()
    ):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
