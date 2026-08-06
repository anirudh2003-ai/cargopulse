"""Find the request format accepted by the USCG PSIX service."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET

import requests


URL = "https://cgmix.uscg.mil/xml/PSIXData.asmx"
IMO = "9872949"
VESSEL_NAME = "LNGSHIPS ATHENA"


def local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def make_request(
    *,
    label: str,
    namespace: str,
    vessel_id: str = "",
    vessel_name: str = "",
    vin: str = "",
    service: str = "",
) -> None:
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:cgm="{namespace}">
    <soapenv:Header />
    <soapenv:Body>
        <cgm:getVesselSummaryXMLString>
            <cgm:VesselID>{vessel_id}</cgm:VesselID>
            <cgm:VesselName>{vessel_name}</cgm:VesselName>
            <cgm:CallSign></cgm:CallSign>
            <cgm:VIN>{vin}</cgm:VIN>
            <cgm:HIN></cgm:HIN>
            <cgm:Flag></cgm:Flag>
            <cgm:Service>{service}</cgm:Service>
            <cgm:BuildYear></cgm:BuildYear>
        </cgm:getVesselSummaryXMLString>
    </soapenv:Body>
</soapenv:Envelope>
"""

    action = (
        f"{namespace.rstrip('/')}"
        "/getVesselSummaryXMLString"
    )

    print("\n" + "=" * 78)
    print(label)
    print(f"Namespace:  {namespace}")
    print(f"SOAPAction: {action}")
    print(
        f"VesselID={vessel_id!r}, "
        f"VIN={vin!r}, "
        f"Name={vessel_name!r}, "
        f"Service={service!r}"
    )

    try:
        response = requests.post(
            URL,
            data=envelope.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{action}"',
                "User-Agent": (
                    "CargoPulse/0.1 "
                    "(academic vessel intelligence project)"
                ),
            },
            timeout=30,
        )

        print(f"HTTP status: {response.status_code}")

        if response.status_code != 200:
            print(response.text[:1000])
            return

        outer_root = ET.fromstring(response.text)

        result_text: str | None = None

        for element in outer_root.iter():
            if (
                local_name(element.tag)
                == "getVesselSummaryXMLStringResult"
            ):
                result_text = element.text
                break

        if not result_text:
            print("No result element text was returned.")
            print(response.text[:1000])
            return

        inner_xml = html.unescape(result_text.strip())

        print(f"Embedded XML length: {len(inner_xml):,}")
        print(inner_xml[:1500])

        if (
            "LNGSHIPS ATHENA" in inner_xml.upper()
            or "<Table>" in inner_xml
            or "<VesselID>" in inner_xml
        ):
            print("\n>>> THIS VARIANT RETURNED VESSEL DATA <<<")
        else:
            print("\nNo vessel rows returned.")

    except Exception as error:
        print(f"ERROR: {type(error).__name__}: {error}")


def main() -> None:
    http_namespace = "http://cgmix.uscg.mil"
    https_namespace = "https://cgmix.uscg.mil"

    tests = [
        {
            "label": "1. HTTP namespace — IMO in VIN — blank service",
            "namespace": http_namespace,
            "vin": IMO,
        },
        {
            "label": "2. HTTP namespace — IMO in VesselID — blank service",
            "namespace": http_namespace,
            "vessel_id": IMO,
        },
        {
            "label": "3. HTTP namespace — vessel name — blank service",
            "namespace": http_namespace,
            "vessel_name": VESSEL_NAME,
        },
        {
            "label": "4. HTTPS namespace — IMO in VIN — blank service",
            "namespace": https_namespace,
            "vin": IMO,
        },
        {
            "label": "5. HTTPS namespace — IMO in VesselID — blank service",
            "namespace": https_namespace,
            "vessel_id": IMO,
        },
        {
            "label": "6. HTTPS namespace — vessel name — blank service",
            "namespace": https_namespace,
            "vessel_name": VESSEL_NAME,
        },
        {
            "label": "7. HTTP namespace — IMO in VIN — service ALL",
            "namespace": http_namespace,
            "vin": IMO,
            "service": "ALL",
        },
        {
            "label": "8. HTTPS namespace — IMO in VIN — service ALL",
            "namespace": https_namespace,
            "vin": IMO,
            "service": "ALL",
        },
    ]

    for test in tests:
        make_request(**test)


if __name__ == "__main__":
    main()
