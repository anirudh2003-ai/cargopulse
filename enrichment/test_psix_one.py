"""Test one USCG PSIX vessel lookup."""

from pprint import pprint

from enrichment.uscg_psix_provider import (
    UscgPsixProvider,
)


def main() -> None:
    provider = UscgPsixProvider()

    # LNGSHIPS ATHENA from your validated calls.
    imo = 9872949

    print(f"Looking up IMO {imo}...")

    result = provider.lookup(imo)

    if result is None:
        print("No PSIX record was found.")
        return

    print("\nParsed result:")
    pprint(result.to_dict())

    print("\nFields relevant to classification:")
    print(f"Service type:     {result.service_type}")
    print(f"Service subtype:  {result.service_sub_type}")
    print(f"Cargo description:{result.cargo_description}")
    print(f"Combined type:    {result.combined_type}")


if __name__ == "__main__":
    main()
