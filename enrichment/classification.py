"""Conservative vessel-classification rules."""

from __future__ import annotations

NON_LNG_SUBTYPES = {
    "LPG",
    "CRUDE OIL",
    "OIL",
    "CHEMICAL",
    "PRODUCT",
    "PETROLEUM PRODUCT",
}


def classify_psix_vessel(
    service_type: str | None,
    service_sub_type: str | None,
    cargo_authorization: str | None,
) -> tuple[str | None, str]:
    """
    Return:
        normalised vessel type,
        classification status

    A vessel is confirmed as LNG only when PSIX provides
    explicit LNG evidence.
    """

    service_type_clean = (
        service_type.strip()
        if service_type
        else ""
    )

    subtype = (
        service_sub_type.strip().upper()
        if service_sub_type
        else ""
    )

    cargo = (
        cargo_authorization.strip().lower()
        if cargo_authorization
        else ""
    )

    if subtype == "LNG":
        return "LNG carrier", "confirmed_lng"

    if (
        "lng vessel" in cargo
        or "liquefied natural gas" in cargo
    ):
        return "LNG carrier", "confirmed_lng"

    if subtype == "LPG":
        return "LPG carrier", "confirmed_non_lng"

    if subtype in NON_LNG_SUBTYPES:
        return service_sub_type, "confirmed_non_lng"

    if service_sub_type:
        return service_sub_type, "needs_review"

    if service_type_clean:
        return service_type_clean, "needs_review"

    return None, "unknown"
