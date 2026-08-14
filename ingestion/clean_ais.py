"""Clean NOAA AIS data and save it as compressed Parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

COLUMN_MAPPING = {
    "MMSI": "mmsi",
    "BaseDateTime": "recorded_at",
    "LAT": "latitude",
    "LON": "longitude",
    "SOG": "speed_knots",
    "COG": "course_degrees",
    "Heading": "heading_degrees",
    "VesselName": "vessel_name",
    "IMO": "imo",
    "CallSign": "call_sign",
    "VesselType": "vessel_type",
    "Status": "status",
    "Length": "length_metres",
    "Width": "width_metres",
    "Draft": "draught_metres",
    "Cargo": "cargo",
    "TransceiverClass": "transceiver_class",
}


def clean_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Validate and standardise one AIS data chunk."""

    chunk = chunk.rename(columns=COLUMN_MAPPING)

    # Preserve vessel identifiers as text.
    chunk["mmsi"] = chunk["mmsi"].astype("string").str.strip()
    chunk["imo"] = chunk["imo"].astype("string").str.strip()

    # Convert timestamps to timezone-aware UTC values.
    chunk["recorded_at"] = pd.to_datetime(
        chunk["recorded_at"],
        errors="coerce",
        utc=True,
    )

    numeric_columns = [
        "latitude",
        "longitude",
        "speed_knots",
        "course_degrees",
        "heading_degrees",
        "vessel_type",
        "status",
        "length_metres",
        "width_metres",
        "draught_metres",
        "cargo",
    ]

    for column in numeric_columns:
        chunk[column] = pd.to_numeric(
            chunk[column],
            errors="coerce",
        )

    for column in [
    "vessel_type",
    "status",
    "cargo",
]:
        chunk[column] = chunk[column].astype("Int64")

    # Remove records missing fields required to identify a position.
    chunk = chunk.dropna(
        subset=[
            "mmsi",
            "recorded_at",
            "latitude",
            "longitude",
        ]
    )

    # Validate MMSI.
    chunk = chunk[
        chunk["mmsi"].str.fullmatch(r"\d{9}", na=False)
    ]

    # Validate geographic coordinates.
    chunk = chunk[
        chunk["latitude"].between(-90, 90)
        & chunk["longitude"].between(-180, 180)
    ]

    # Convert AIS unavailable values into null values.
    chunk.loc[
        ~chunk["heading_degrees"].between(0, 359),
        "heading_degrees",
    ] = pd.NA

    chunk.loc[
        ~chunk["course_degrees"].between(0, 359.9),
        "course_degrees",
    ] = pd.NA

    chunk.loc[
        ~chunk["speed_knots"].between(0, 102.2),
        "speed_knots",
    ] = pd.NA

    # Remove clearly impossible dimensions.
    chunk.loc[
        ~chunk["length_metres"].between(1, 500),
        "length_metres",
    ] = pd.NA

    chunk.loc[
        ~chunk["width_metres"].between(1, 100),
        "width_metres",
    ] = pd.NA

    chunk.loc[
        ~chunk["draught_metres"].between(0, 30),
        "draught_metres",
    ] = pd.NA

    # Clean text fields.
    for column in [
        "vessel_name",
        "call_sign",
        "transceiver_class",
    ]:
        chunk[column] = (
            chunk[column]
            .astype("string")
            .str.strip()
            .replace("", pd.NA)
        )

    # The database key will be MMSI plus timestamp.
    chunk = chunk.drop_duplicates(
        subset=["mmsi", "recorded_at"],
        keep="first",
    )

    return chunk


def clean_csv(
    input_path: Path,
    output_path: Path,
    chunk_size: int,
) -> None:
    """Clean a large AIS CSV in chunks."""

    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output_path.unlink()

    writer: pq.ParquetWriter | None = None
    input_rows = 0
    output_rows = 0

    try:
        for chunk_number, chunk in enumerate(
            pd.read_csv(
                input_path,
                chunksize=chunk_size,
                dtype={
                    "MMSI": "string",
                    "IMO": "string",
                },
                low_memory=False,
            ),
            start=1,
        ):
            input_rows += len(chunk)

            cleaned = clean_chunk(chunk)
            output_rows += len(cleaned)

            table = pa.Table.from_pandas(
                cleaned,
                preserve_index=False,
            )

            if writer is None:
                writer = pq.ParquetWriter(
                    output_path,
                    table.schema,
                    compression="snappy",
                )

            writer.write_table(table)

            print(
                f"Chunk {chunk_number}: "
                f"{len(chunk):,} input, "
                f"{len(cleaned):,} retained"
            )

    finally:
        if writer is not None:
            writer.close()

    removed_rows = input_rows - output_rows

    print("\nCleaning complete")
    print(f"Input rows:   {input_rows:,}")
    print(f"Output rows:  {output_rows:,}")
    print(f"Rows removed: {removed_rows:,}")
    print(f"Saved to:     {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input_csv",
        type=Path,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/silver/ais_positions.parquet"),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=250_000,
    )

    arguments = parser.parse_args()

    clean_csv(
        input_path=arguments.input_csv,
        output_path=arguments.output,
        chunk_size=arguments.chunk_size,
    )


if __name__ == "__main__":
    main()
