"""Diagnose USCG PSIX vessel-summary searches."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pprint import pprint

from enrichment.uscg_psix_provider import UscgPsixProvider


def search_summary(
    provider: UscgPsixProvider,
    *,
    vin: str = "%",
    vessel_name: str = "%",
) -> None:
    """
    Search PSIX while using wildcards for unused text fields.

    This avoids accidentally requesting records whose unused
    fields are literally empty.
    """

    body = f"""
<getVesselSummaryXMLString
    xmlns="https://cgmix.uscg.mil">
    <VesselID>%</VesselID>
    <VesselName>{vessel_name}</VesselName>
    <CallSign>%</CallSign>
    <VIN>{vin}</VIN>
    <HIN>%</HIN>
    <Flag>%</Flag>
    <Service>ALL</Service>
    <BuildYear></BuildYear>
</getVesselSummaryXMLString>
"""

    soap_xml = provider._post_soap(
        operation="getVesselSummaryXMLString",
        operation_body=body,
    )

    inner_root = provider._extract_inner_xml(
        soap_xml,
        "getVesselSummaryXMLStringResult",
    )

    inner_xml = ET.tostring(
        inner_root,
        encoding="unicode",
    )

    records = provider._extract_records(inner_root)

    print("\n" + "=" * 70)
    print(
        f"Search: VIN={vin!r}, "
        f"vessel_name={vessel_name!r}"
    )
    print(f"Inner root tag: {inner_root.tag}")
    print(f"Inner XML length: {len(inner_xml):,}")
    print(f"Records returned: {len(records)}")

    print("\nFirst 2,000 characters of embedded XML:")
    print(inner_xml[:2000])

    if records:
        print("\nFirst returned records:")

        for record in records[:5]:
            pprint(record)


def main() -> None:
    provider = UscgPsixProvider()

    # Candidate LNG vessel by IMO.
    search_summary(
        provider,
        vin="9872949",
        vessel_name="%",
    )

    # Candidate LNG vessel by name.
    search_summary(
        provider,
        vin="%",
        vessel_name="LNGSHIPS ATHENA%",
    )

    # A vessel known to have had historical USCG/PSIX records.
    search_summary(
        provider,
        vin="%",
        vessel_name="CARLA MAERSK%",
    )


if __name__ == "__main__":
    main()