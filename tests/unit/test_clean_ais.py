"""Unit tests for AIS cleaning."""

from __future__ import annotations

import pandas as pd
import pytest

from ingestion.clean_ais import clean_chunk

pytestmark = pytest.mark.unit

def make_row(**overrides):
    row = {
        "MMSI": "123456789",
        "BaseDateTime": "2023-01-01T12:00:00Z",
        "LAT": 29.50,
        "LON": -93.75,
        "SOG": 10.5,
        "COG": 180.0,
        "Heading": 181.0,
        "VesselName": " TEST VESSEL ",
        "IMO": "IMO1234567",
        "CallSign": " TEST123 ",
        "VesselType": 80,
        "Status": 0,
        "Length": 280.0,
        "Width": 45.0,
        "Draft": 11.5,
        "Cargo": 80,
        "TransceiverClass": " A ",
    }

    row.update(overrides)

    return row


def test_clean_chunk_keeps_valid_row():
    dataframe = pd.DataFrame(
        [make_row()]
    )

    result = clean_chunk(dataframe)

    assert len(result) == 1

    row = result.iloc[0]

    assert row["mmsi"] == "123456789"
    assert row["vessel_name"] == "TEST VESSEL"
    assert row["call_sign"] == "TEST123"
    assert row["transceiver_class"] == "A"

    assert row["recorded_at"].tzinfo is not None


def test_clean_chunk_removes_invalid_position():
    dataframe = pd.DataFrame(
        [
            make_row(
                LAT=95.0,
            )
        ]
    )

    result = clean_chunk(dataframe)

    assert result.empty


def test_clean_chunk_converts_unavailable_values_to_null():
    dataframe = pd.DataFrame(
        [
            make_row(
                SOG=102.3,
                COG=360.0,
                Heading=511,
                Length=0,
                Width=101,
                Draft=31,
            )
        ]
    )

    result = clean_chunk(dataframe)

    assert len(result) == 1

    row = result.iloc[0]

    assert pd.isna(row["speed_knots"])
    assert pd.isna(row["course_degrees"])
    assert pd.isna(row["heading_degrees"])
    assert pd.isna(row["length_metres"])
    assert pd.isna(row["width_metres"])
    assert pd.isna(row["draught_metres"])


def test_clean_chunk_removes_duplicate_positions():
    row = make_row()

    dataframe = pd.DataFrame(
        [
            row,
            row.copy(),
        ]
    )

    result = clean_chunk(dataframe)

    assert len(result) == 1
