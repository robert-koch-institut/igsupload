from dataclasses import fields

from igsupload.extract_csv import CsvRow
from igsupload.igs_notification import (
    LOINC_VERSION,
    SNOMED_CT_VERSION,
    build_notification_bundle,
)


def _row(**overrides) -> CsvRow:
    values = {field.name: "" for field in fields(CsvRow)}
    values.update(
        {
            "DEMIS_NOTIFICATION_ID": "6cb7099d-8d53-4ee4-96ca-c55761b347d4",
            "STATUS": "final",
            "ISOLATION_SOURCE_CODE": "258604001",
            "ISOLATION_SOURCE": "Skin specimen",
            "SPECIES_CODE": "3092008",
            "SPECIES": "Staphylococcus aureus",
        }
    )
    values.update(overrides)
    return CsvRow(**values)


def _resource(bundle: dict, resource_type: str) -> dict:
    return next(
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == resource_type
    )


def test_terminology_codings_use_versions_from_demis_package():
    bundle = build_notification_bundle(
        _row(),
        ["document-1", "document-2"],
    )

    specimen = _resource(bundle, "Specimen")
    observation = _resource(bundle, "Observation")

    assert specimen["type"]["coding"][0]["version"] == SNOMED_CT_VERSION
    assert observation["code"]["coding"][0]["version"] == LOINC_VERSION
    assert (
        observation["valueCodeableConcept"]["coding"][0]["version"]
        == SNOMED_CT_VERSION
    )
    assert observation["method"]["coding"][0]["version"] == SNOMED_CT_VERSION
