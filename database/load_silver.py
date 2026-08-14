"""Load cleaned AIS Parquet data into PostgreSQL/PostGIS."""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from dotenv import load_dotenv
from sqlalchemy import create_engine

COPY_COLUMNS = [
    "mmsi",
    "recorded_at",
    "latitude",
    "longitude",
    "speed_knots",
    "course_degrees",
    "heading_degrees",
    "vessel_name",
    "imo",
    "call_sign",
    "vessel_type",
    "status",
    "length_metres",
    "width_metres",
    "draught_metres",
    "cargo",
    "transceiver_class",
]


def prepare_batch(batch_dataframe: pd.DataFrame) -> pd.DataFrame:
    """Prepare one Parquet batch for PostgreSQL COPY."""

    dataframe = batch_dataframe.copy()

    missing_columns = [
        column
        for column in COPY_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Parquet file is missing columns: {missing_columns}"
        )

    dataframe["mmsi"] = pd.to_numeric(
        dataframe["mmsi"],
        errors="coerce",
    ).astype("Int64")

    # NOAA IMO values may be numeric or formatted as IMO1234567.
    imo_digits = (
        dataframe["imo"]
        .astype("string")
        .str.extract(r"(\d{7})", expand=False)
    )

    dataframe["imo"] = pd.to_numeric(
        imo_digits,
        errors="coerce",
    ).astype("Int64")

    integer_columns = [
        "vessel_type",
        "status",
        "cargo",
    ]

    for column in integer_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        ).astype("Int64")

    float_columns = [
        "latitude",
        "longitude",
        "speed_knots",
        "course_degrees",
        "heading_degrees",
        "length_metres",
        "width_metres",
        "draught_metres",
    ]

    for column in float_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe["recorded_at"] = pd.to_datetime(
        dataframe["recorded_at"],
        errors="coerce",
        utc=True,
    )

    text_columns = [
        "vessel_name",
        "call_sign",
        "transceiver_class",
    ]

    for column in text_columns:
        dataframe[column] = (
            dataframe[column]
            .astype("string")
            .str.strip()
            .replace("", pd.NA)
        )

    dataframe = dataframe.dropna(
        subset=[
            "mmsi",
            "recorded_at",
            "latitude",
            "longitude",
        ]
    )

    return dataframe[COPY_COLUMNS]


def copy_batch(cursor, dataframe: pd.DataFrame) -> None:
    """Use PostgreSQL COPY to load one batch efficiently."""

    buffer = io.StringIO()

    dataframe.to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="",
    )

    buffer.seek(0)

    columns = ", ".join(COPY_COLUMNS)

    copy_statement = f"""
        COPY staging_ais_positions ({columns})
        FROM STDIN
        WITH (
            FORMAT CSV,
            NULL ''
        )
    """

    cursor.copy_expert(copy_statement, buffer)


def load_parquet(
    parquet_path: Path,
    batch_size: int,
) -> None:
    """Load Parquet records and populate final database tables."""

    if not parquet_path.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {parquet_path}"
        )

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from .env")

    engine = create_engine(database_url)
    parquet_file = pq.ParquetFile(parquet_path)

    connection = engine.raw_connection()
    cursor = connection.cursor()

    loaded_rows = 0

    try:
        cursor.execute("TRUNCATE staging_ais_positions;")
        connection.commit()

        print(f"Loading: {parquet_path}")
        print(
            f"Parquet rows: "
            f"{parquet_file.metadata.num_rows:,}"
        )

        for batch_number, record_batch in enumerate(
            parquet_file.iter_batches(
                batch_size=batch_size,
            ),
            start=1,
        ):
            dataframe = record_batch.to_pandas()
            dataframe = prepare_batch(dataframe)

            copy_batch(cursor, dataframe)
            connection.commit()

            loaded_rows += len(dataframe)

            print(
                f"Batch {batch_number}: "
                f"{len(dataframe):,} loaded "
                f"({loaded_rows:,} total)"
            )

        print("\nCreating vessel records...")

        cursor.execute(
            """
            INSERT INTO vessels (
                mmsi,
                imo,
                vessel_name,
                call_sign,
                vessel_type,
                length_metres,
                width_metres,
                cargo,
                transceiver_class
            )
            SELECT DISTINCT ON (mmsi)
                mmsi,
                imo,
                vessel_name,
                call_sign,
                vessel_type,
                length_metres,
                width_metres,
                cargo,
                transceiver_class
            FROM staging_ais_positions
            WHERE mmsi IS NOT NULL
            ORDER BY
                mmsi,
                (imo IS NOT NULL) DESC,
                (vessel_name IS NOT NULL) DESC,
                recorded_at DESC
            ON CONFLICT (mmsi)
            DO UPDATE SET
                imo = COALESCE(
                    EXCLUDED.imo,
                    vessels.imo
                ),
                vessel_name = COALESCE(
                    EXCLUDED.vessel_name,
                    vessels.vessel_name
                ),
                call_sign = COALESCE(
                    EXCLUDED.call_sign,
                    vessels.call_sign
                ),
                vessel_type = COALESCE(
                    EXCLUDED.vessel_type,
                    vessels.vessel_type
                ),
                length_metres = COALESCE(
                    EXCLUDED.length_metres,
                    vessels.length_metres
                ),
                width_metres = COALESCE(
                    EXCLUDED.width_metres,
                    vessels.width_metres
                ),
                cargo = COALESCE(
                    EXCLUDED.cargo,
                    vessels.cargo
                ),
                transceiver_class = COALESCE(
                    EXCLUDED.transceiver_class,
                    vessels.transceiver_class
                );
            """
        )

        connection.commit()

        print("Creating AIS position records...")

        cursor.execute(
            """
            INSERT INTO ais_positions (
                mmsi,
                recorded_at,
                latitude,
                longitude,
                speed_knots,
                course_degrees,
                heading_degrees,
                status,
                draught_metres
            )
            SELECT
                mmsi,
                recorded_at,
                latitude,
                longitude,
                speed_knots,
                course_degrees,
                heading_degrees,
                status,
                draught_metres
            FROM staging_ais_positions
            WHERE
                mmsi IS NOT NULL
                AND recorded_at IS NOT NULL
                AND latitude IS NOT NULL
                AND longitude IS NOT NULL
            ON CONFLICT (mmsi, recorded_at)
            DO NOTHING;
            """
        )

        connection.commit()

        cursor.execute("ANALYZE vessels;")
        cursor.execute("ANALYZE ais_positions;")
        connection.commit()

        cursor.execute("SELECT COUNT(*) FROM vessels;")
        vessel_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM ais_positions;")
        position_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM ais_positions
            WHERE location IS NULL;
            """
        )
        missing_locations = cursor.fetchone()[0]

        print("\nDatabase load complete")
        print(f"Staging rows:     {loaded_rows:,}")
        print(f"Unique vessels:   {vessel_count:,}")
        print(f"AIS positions:    {position_count:,}")
        print(f"Missing locations:{missing_locations:,}")

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load cleaned AIS Parquet into PostGIS."
    )

    parser.add_argument(
        "parquet_file",
        type=Path,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100_000,
    )

    arguments = parser.parse_args()

    load_parquet(
        parquet_path=arguments.parquet_file,
        batch_size=arguments.batch_size,
    )


if __name__ == "__main__":
    main()
