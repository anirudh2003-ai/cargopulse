"""Test USCG PSIX coverage for validated terminal-call vessels."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import pandas as pd

from enrichment.uscg_psix_provider import (
    UscgPsixProvider,
)

INPUT_PATH = Path(
    "data/reference/lng_candidates.csv"
)

OUTPUT_PATH = Path(
    "data/reference/psix_test_results.csv"
)


def optional_integer(value: Any) -> int | None:
    """Convert a pandas value to an integer when present."""

    if pd.isna(value):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main(limit: int | None) -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Candidate file does not exist: {INPUT_PATH}"
        )

    candidates = pd.read_csv(
        INPUT_PATH,
        dtype={
            "imo": "Int64",
            "mmsi": "Int64",
        },
    )

    required_columns = {
        "imo",
        "mmsi",
        "vessel_name",
    }

    missing_columns = required_columns.difference(
        candidates.columns
    )

    if missing_columns:
        raise ValueError(
            "Candidate file is missing columns: "
            f"{sorted(missing_columns)}"
        )

    candidates = (
        candidates
        .dropna(subset=["imo"])
        .drop_duplicates(subset=["imo"])
        .reset_index(drop=True)
    )

    if limit is not None:
        candidates = candidates.head(limit)

    provider = UscgPsixProvider()
    results: list[dict[str, Any]] = []

    total = len(candidates)

    print(f"Unique vessels selected: {total}")

    for index, candidate in enumerate(
        candidates.itertuples(index=False),
        start=1,
    ):
        imo = int(candidate.imo)
        mmsi = optional_integer(candidate.mmsi)
        expected_name = str(candidate.vessel_name)

        print("\n" + "=" * 70)
        print(
            f"[{index}/{total}] "
            f"{expected_name} — IMO {imo}"
        )

        output: dict[str, Any] = {
            "imo": imo,
            "mmsi": mmsi,
            "expected_vessel_name": expected_name,
            "psix_found": False,
            "psix_vessel_id": None,
            "psix_vessel_name": None,
            "returned_identification": None,
            "service_type": None,
            "service_sub_type": None,
            "cargo_description": None,
            "flag": None,
            "status": None,
            "combined_type": None,
            "error": None,
        }

        try:
            result = provider.lookup(imo)

            if result is None:
                output["error"] = "No PSIX record"
                print("PSIX result: NOT FOUND")

            else:
                output.update(
                    {
                        "psix_found": True,
                        "psix_vessel_id": result.vessel_id,
                        "psix_vessel_name": result.vessel_name,
                        "returned_identification": result.vin,
                        "service_type": result.service_type,
                        "service_sub_type": (
                            result.service_sub_type
                        ),
                        "cargo_description": (
                            result.cargo_description
                        ),
                        "flag": result.flag,
                        "status": result.status,
                        "combined_type": result.combined_type,
                    }
                )

                print(
                    f"Returned vessel: "
                    f"{result.vessel_name}"
                )
                print(
                    f"Returned IMO:    {result.vin}"
                )
                print(
                    f"Service type:    "
                    f"{result.service_type}"
                )
                print(
                    f"Service subtype: "
                    f"{result.service_sub_type}"
                )
                print(
                    f"Cargo:           "
                    f"{result.cargo_description}"
                )

                if str(result.vin) != str(imo):
                    output["error"] = (
                        "Returned identification does not "
                        "match requested IMO"
                    )

                    print(
                        "WARNING: returned identification "
                        "does not match requested IMO"
                    )

        except Exception as error:
            output["error"] = (
                f"{type(error).__name__}: {error}"
            )

            print(f"ERROR: {output['error']}")

        results.append(output)

        # Save after each lookup so progress is retained.
        pd.DataFrame(results).to_csv(
            OUTPUT_PATH,
            index=False,
        )

        # Avoid sending requests too rapidly.
        if index < total:
            time.sleep(1)

    results_frame = pd.DataFrame(results)

    found_count = int(
        results_frame["psix_found"]
        .fillna(False)
        .sum()
    )

    lng_count = int(
        results_frame["service_sub_type"]
        .fillna("")
        .str.strip()
        .str.upper()
        .eq("LNG")
        .sum()
    )

    print("\n" + "=" * 70)
    print("PSIX test completed")
    print(f"Vessels tested:     {len(results_frame)}")
    print(f"PSIX records found: {found_count}")
    print(f"Explicit LNG:       {lng_count}")
    print(f"Output saved to:    {OUTPUT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of vessels to test.",
    )

    arguments = parser.parse_args()

    main(arguments.limit)
