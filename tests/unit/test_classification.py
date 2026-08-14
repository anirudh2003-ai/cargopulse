"""Unit tests for vessel classification."""

from __future__ import annotations

import pytest

from enrichment.classification import classify_psix_vessel

pytestmark = pytest.mark.unit

@pytest.mark.parametrize(
    (
        "service_type",
        "service_sub_type",
        "cargo",
        "expected_type",
        "expected_status",
    ),
    [
        (
            "Tank Ship",
            "LNG",
            None,
            "LNG carrier",
            "confirmed_lng",
        ),
        (
            "Tank Ship",
            None,
            "Authorized liquefied natural gas vessel",
            "LNG carrier",
            "confirmed_lng",
        ),
        (
            "Tank Ship",
            "LPG",
            None,
            "LPG carrier",
            "confirmed_non_lng",
        ),
        (
            "Tank Ship",
            "CRUDE OIL",
            None,
            "CRUDE OIL",
            "confirmed_non_lng",
        ),
        (
            "Tank Ship",
            None,
            None,
            "Tank Ship",
            "needs_review",
        ),
        (
            None,
            None,
            None,
            None,
            "unknown",
        ),
    ],
)
def test_classification_rules(
    service_type,
    service_sub_type,
    cargo,
    expected_type,
    expected_status,
):
    result = classify_psix_vessel(
        service_type=service_type,
        service_sub_type=service_sub_type,
        cargo_authorization=cargo,
    )

    assert result == (
        expected_type,
        expected_status,
    )
