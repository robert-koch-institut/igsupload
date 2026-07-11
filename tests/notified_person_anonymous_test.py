from dataclasses import fields

from igsupload.extract_csv import CsvRow
from igsupload.igs_notification import (
    ADDRESS_USE_EXTENSION,
    ADDRESS_USE_SYSTEM,
    NOTIFIED_PERSON_ANONYMOUS_PROFILE,
    build_notification_bundle,
)


def _row(**overrides) -> CsvRow:
    values = {field.name: "" for field in fields(CsvRow)}
    values.update(
        {
            "DEMIS_NOTIFICATION_ID": "6cb7099d-8d53-4ee4-96ca-c55761b347d4",
            "STATUS": "final",
            "ADAPTER": "adapter-1+adapter-2",
        }
    )
    values.update(overrides)
    return CsvRow(**values)


def _patient(bundle: dict) -> dict:
    return next(
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Patient"
    )


def test_patient_uses_anonymous_profile_and_primary_address_slice():
    bundle = build_notification_bundle(
        _row(
            HOST_SEX="male",
            HOST_BIRTH_YEAR="2025",
            HOST_BIRTH_MONTH="12",
            GEOGRAPHIC_LOCATION="104",
        ),
        ["document-1", "document-2"],
    )

    patient = _patient(bundle)

    assert patient["meta"]["profile"] == [NOTIFIED_PERSON_ANONYMOUS_PROFILE]
    assert patient["gender"] == "male"
    assert patient["birthDate"] == "2025-12"
    assert patient["address"] == [
        {
            "extension": [
                {
                    "url": ADDRESS_USE_EXTENSION,
                    "valueCoding": {
                        "system": ADDRESS_USE_SYSTEM,
                        "code": "primary",
                    },
                }
            ],
            "postalCode": "104",
        }
    ]


def test_patient_omits_address_without_geographic_location():
    patient = _patient(
        build_notification_bundle(_row(), ["document-1", "document-2"])
    )

    assert "address" not in patient
