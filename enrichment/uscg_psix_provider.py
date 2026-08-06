"""Client for the free USCG PSIX XML web service."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PSIX_URL = "https://cgmix.uscg.mil/xml/PSIXData.asmx"
USCG_NAMESPACE = "https://cgmix.uscg.mil"
SOAP_NAMESPACE = "http://schemas.xmlsoap.org/soap/envelope/"


@dataclass
class PsixResult:
    requested_imo: int
    vessel_id: int
    vessel_name: str | None
    vin: str | None
    service_type: str | None
    service_sub_type: str | None
    cargo_description: str | None
    flag: str | None
    status: str | None
    raw_summary: dict[str, Any]
    raw_particulars: dict[str, Any]

    @property
    def combined_type(self) -> str | None:
        values = [
            self.service_type,
            self.service_sub_type,
            self.cargo_description,
        ]

        cleaned = [
            str(value).strip()
            for value in values
            if value is not None and str(value).strip()
        ]

        return " | ".join(cleaned) if cleaned else None

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        output["combined_type"] = self.combined_type
        return output


class PsixError(RuntimeError):
    """Raised when PSIX returns an invalid or unexpected response."""


class UscgPsixProvider:
    def __init__(
        self,
        timeout_seconds: int = 30,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[
                429,
                500,
                502,
                503,
                504,
            ],
            allowed_methods=["POST"],
        )

        self.session.mount(
            "https://",
            HTTPAdapter(max_retries=retry),
        )

        self.session.headers.update(
            {
                "User-Agent": (
                    "CargoPulse/0.1 "
                    "(academic vessel intelligence project)"
                )
            }
        )

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", maxsplit=1)[-1]

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _digits_to_integer(
        value: str | None,
    ) -> int | None:
        if not value:
            return None

        digits = re.sub(r"\D", "", value)
        return int(digits) if digits else None

    def _post_soap(
        self,
        operation: str,
        operation_body: str,
    ) -> str:
        envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap="{SOAP_NAMESPACE}">
    <soap:Body>
        {operation_body}
    </soap:Body>
</soap:Envelope>
"""

        response = self.session.post(
            PSIX_URL,
            data=envelope.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": (
                    f'"{USCG_NAMESPACE}/{operation}"'
                ),
            },
            timeout=self.timeout_seconds,
        )

        response.raise_for_status()

        return response.text

    def _extract_inner_xml(
        self,
        soap_xml: str,
        result_element_name: str,
    ) -> ET.Element:
        try:
            outer_root = ET.fromstring(soap_xml)
        except ET.ParseError as error:
            raise PsixError(
                "PSIX returned invalid SOAP XML"
            ) from error

        result_text: str | None = None

        for element in outer_root.iter():
            if (
                self._local_name(element.tag)
                == result_element_name
            ):
                result_text = element.text
                break

        if not result_text:
            raise PsixError(
                f"Missing {result_element_name} "
                "in PSIX response"
            )

        inner_xml = result_text.strip()

        # The returned dataset may be escaped inside the SOAP XML.
        for _ in range(3):
            if "&lt;" not in inner_xml:
                break

            inner_xml = html.unescape(inner_xml)

        try:
            return ET.fromstring(inner_xml)
        except ET.ParseError as error:
            raise PsixError(
                "Unable to parse the XML dataset "
                "inside the PSIX response"
            ) from error

    def _extract_records(
        self,
        root: ET.Element,
    ) -> list[dict[str, str | None]]:
        records: list[dict[str, str | None]] = []

        for element in root.iter():
            children = list(element)

            if not children:
                continue

            record: dict[str, str | None] = {}

            for child in children:
                # Skip elements that themselves contain nested rows.
                if list(child):
                    continue

                field_name = self._local_name(child.tag)

                # PSIX inconsistently returns VesselId rather than VesselID.
                if field_name.casefold() == "vesselid":
                    field_name = "VesselID"

                record[field_name] = self._clean_text(
                    child.text
                )

            if record and (
                "VesselID" in record
                or "VesselName" in record
                or "ServiceType" in record
                or "VIN" in record
            ):
                records.append(record)

        # Remove exact duplicate dictionaries.
        unique_records: list[dict[str, str | None]] = []

        for record in records:
            if record not in unique_records:
                unique_records.append(record)

        return unique_records

    def _find_summary(
    self,
    imo: int,
) -> dict[str, str | None] | None:
        """
        Search PSIX using the IMO number in the VIN field.

        Service must remain blank. Setting Service to ALL causes
        the current PSIX service to return an empty dataset.
        """

        body = f"""
    <getVesselSummaryXMLString xmlns="{USCG_NAMESPACE}">
        <VesselID></VesselID>
        <VesselName></VesselName>
        <CallSign></CallSign>
        <VIN>{imo}</VIN>
        <HIN></HIN>
        <Flag></Flag>
        <Service></Service>
        <BuildYear></BuildYear>
    </getVesselSummaryXMLString>
    """

        soap_xml = self._post_soap(
            operation="getVesselSummaryXMLString",
            operation_body=body,
        )

        inner_root = self._extract_inner_xml(
            soap_xml,
            "getVesselSummaryXMLStringResult",
        )

        records = self._extract_records(inner_root)

        if not records:
            return None

        for record in records:
            identification = record.get("Identification")

            if identification:
                digits = re.sub(
                    r"\D",
                    "",
                    identification,
                )

                if digits == str(imo):
                    return record

        return records[0]

    def _get_particulars(
        self,
        vessel_id: int,
    ) -> dict[str, str | None] | None:
        body = f"""
<getVesselParticularsXMLString
    xmlns="{USCG_NAMESPACE}">
    <VesselID>{vessel_id}</VesselID>
</getVesselParticularsXMLString>
"""

        soap_xml = self._post_soap(
            operation="getVesselParticularsXMLString",
            operation_body=body,
        )

        inner_root = self._extract_inner_xml(
            soap_xml,
            "getVesselParticularsXMLStringResult",
        )

        records = self._extract_records(inner_root)

        return records[0] if records else None

    def lookup(
        self,
        imo: int,
    ) -> PsixResult | None:
        summary = self._find_summary(imo)

        if summary is None:
            return None

        vessel_id = self._digits_to_integer(
            summary.get("VesselID")
            or summary.get("VesselId")
        )

        if vessel_id is None:
            raise PsixError(
                f"No VesselID returned for IMO {imo}"
            )

        particulars = self._get_particulars(vessel_id)

        if particulars is None:
            raise PsixError(
                f"No particulars returned for "
                f"PSIX VesselID {vessel_id}"
            )

        return PsixResult(
            requested_imo=imo,
            vessel_id=vessel_id,
            vessel_name=(
                particulars.get("VesselName")
                or summary.get("VesselName")
            ),
            vin=(
                particulars.get("VIN")
                or summary.get("Identification")
            ),
            service_type=particulars.get("ServiceType"),
            service_sub_type=particulars.get(
                "ServiceSubType"
            ),
            cargo_description=particulars.get(
                "CargoAuthorizationDescription"
            ),
            flag=particulars.get("CountryLookupName"),
            status=particulars.get("StatusLookupName"),
            raw_summary=summary,
            raw_particulars=particulars,
        )
