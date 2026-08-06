from pathlib import Path

import pandas as pd


RAW_FOLDER = Path("data/raw")

csv_files = list(RAW_FOLDER.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError("No CSV file found in data/raw")

csv_path = csv_files[0]

print(f"Inspecting: {csv_path}")

sample = pd.read_csv(
    csv_path,
    nrows=5,
    dtype={"MMSI": "string", "IMO": "string"},
    low_memory=False,
)

print("\nColumns:")
for column in sample.columns:
    print(f"- {column}")

print("\nFirst five records:")
print(sample.to_string(index=False))

total_rows = 0
missing_counts = None

for chunk in pd.read_csv(
    csv_path,
    chunksize=250_000,
    dtype={"MMSI": "string", "IMO": "string"},
    low_memory=False,
):
    total_rows += len(chunk)

    chunk_missing = chunk.isna().sum()

    if missing_counts is None:
        missing_counts = chunk_missing
    else:
        missing_counts = missing_counts.add(
            chunk_missing,
            fill_value=0,
        )

print(f"\nTotal rows: {total_rows:,}")

print("\nMissing values:")
print(missing_counts.sort_values(ascending=False))
