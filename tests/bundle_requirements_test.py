from dataclasses import fields

import pytest

import igsupload.igs_notification as igs_notification
from igsupload.extract_csv import CsvRow
from igsupload.fhir_constants import (
    ADAPTER_SUBSTANCE_PROFILE,
    DIAGNOSTIC_REPORT_PROFILE,
    LOINC_VERSION,
    MOLECULAR_SEQUENCE_PROFILE,
    NOTIFICATION_BUNDLE_ID_SYSTEM,
    NOTIFICATION_ID_SYSTEM,
    NOTIFIED_PERSON_ANONYMOUS_PROFILE,
    OBSERVATION_PROFILE,
    SEQUENCE_DOCUMENT_REFERENCE_EXTENSION,
    SEQUENCING_SUBSTANCES_SYSTEM,
    SNOMED_CT_VERSION,
    SPECIMEN_PROFILE,
)


REFERENCED_NOTIFICATION_ID = "6cb7099d-8d53-4ee4-96ca-c55761b347d4"


def _row(**overrides) -> CsvRow:
    values = {field.name: "" for field in fields(CsvRow)}
    values.update(
        {
            "DEMIS_NOTIFICATION_ID": REFERENCED_NOTIFICATION_ID,
            "STATUS": "final",
            "GEOGRAPHIC_LOCATION": "104",
            "ISOLATION_SOURCE_CODE": "258604001",
            "ISOLATION_SOURCE": "Skin specimen",
            "SPECIES_CODE": "3092008",
            "SPECIES": "Staphylococcus aureus",
            "ADAPTER": "adapter-1+adapter-2",
            "PRIMER_SCHEME": "ARTICv4.1",
        }
    )
    values.update(overrides)
    return CsvRow(**values)


def _bundle(*, doc_ids=None, **overrides) -> dict:
    return igs_notification.build_notification_bundle(
        _row(**overrides),
        ["document-1", "document-2"] if doc_ids is None else doc_ids,
    )


def _resources(bundle: dict, resource_type: str) -> list[dict]:
    return [
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == resource_type
    ]


def _resource(bundle: dict, resource_type: str) -> dict:
    resources = _resources(bundle, resource_type)
    assert len(resources) == 1
    return resources[0]


def _collect_references(value) -> list[str]:
    if isinstance(value, dict):
        references = []
        for key, item in value.items():
            if key == "reference" and isinstance(item, str):
                references.append(item)
            else:
                references.extend(_collect_references(item))
        return references
    if isinstance(value, list):
        references = []
        for item in value:
            references.extend(_collect_references(item))
        return references
    return []


def test_a1_patient_uses_notified_person_anonymous_profile():
    patient = _resource(_bundle(), "Patient")

    assert patient["meta"]["profile"] == [NOTIFIED_PERSON_ANONYMOUS_PROFILE]
    assert patient["address"][0]["postalCode"] == "104"


def test_a2_diagnostic_report_uses_expected_profile_and_observation():
    bundle = _bundle()
    report = _resource(bundle, "DiagnosticReport")
    observation = _resource(bundle, "Observation")

    assert report["meta"]["profile"] == [DIAGNOSTIC_REPORT_PROFILE]
    assert report["result"] == [
        {"reference": f"Observation/{observation['id']}"}
    ]


def test_a3_specimen_uses_expected_profile_without_broken_additive_slices():
    bundle = _bundle()
    specimen = _resource(bundle, "Specimen")

    assert igs_notification.INCLUDE_SEQUENCING_ADDITIVES is False
    assert specimen["meta"]["profile"] == [SPECIMEN_PROFILE]
    assert all(
        "additive" not in processing
        for processing in specimen.get("processing", [])
    )
    assert _resources(bundle, "Substance") == []


def test_a4_observation_uses_expected_profile_and_core_references():
    bundle = _bundle()
    observation = _resource(bundle, "Observation")
    specimen = _resource(bundle, "Specimen")
    sequence = _resource(bundle, "MolecularSequence")

    assert observation["meta"]["profile"] == [OBSERVATION_PROFILE]
    assert observation["specimen"] == {
        "reference": f"Specimen/{specimen['id']}"
    }
    assert observation["derivedFrom"] == [
        {"reference": f"MolecularSequence/{sequence['id']}"}
    ]


def test_a5_molecular_sequence_uses_expected_profile_and_specimen():
    bundle = _bundle()
    sequence = _resource(bundle, "MolecularSequence")
    specimen = _resource(bundle, "Specimen")

    assert sequence["meta"]["profile"] == [MOLECULAR_SEQUENCE_PROFILE]
    assert sequence["specimen"] == {
        "reference": f"Specimen/{specimen['id']}"
    }


def test_a6_profile_relevant_codings_contain_central_versions():
    bundle = _bundle()
    specimen = _resource(bundle, "Specimen")
    observation = _resource(bundle, "Observation")

    assert specimen["type"]["coding"][0]["version"] == SNOMED_CT_VERSION
    assert observation["code"]["coding"][0]["version"] == LOINC_VERSION
    assert (
        observation["valueCodeableConcept"]["coding"][0]["version"]
        == SNOMED_CT_VERSION
    )
    assert observation["method"]["coding"][0]["version"] == SNOMED_CT_VERSION


def test_a7_adapter_substances_use_profile_conformant_fields(monkeypatch):
    monkeypatch.setattr(
        igs_notification,
        "INCLUDE_SEQUENCING_ADDITIVES",
        True,
    )
    adapters = [
        resource
        for resource in _resources(_bundle(), "Substance")
        if resource["meta"]["profile"] == [ADAPTER_SUBSTANCE_PROFILE]
    ]

    assert len(adapters) == 2
    for adapter in adapters:
        assert adapter["category"] == [
            {
                "coding": [
                    {
                        "system": SEQUENCING_SUBSTANCES_SYSTEM,
                        "code": "adapter",
                    }
                ]
            }
        ]
        assert adapter["code"]["text"]
        assert "coding" not in adapter["code"]
        assert "description" not in adapter


def test_a8_notification_and_referenced_identifiers_are_distinct():
    bundle = _bundle()
    composition = _resource(bundle, "Composition")
    own_identifier = composition["identifier"]
    referenced_identifier = composition["relatesTo"][0]["targetReference"][
        "identifier"
    ]

    assert own_identifier["system"] == NOTIFICATION_ID_SYSTEM
    assert referenced_identifier == {
        "system": NOTIFICATION_ID_SYSTEM,
        "value": REFERENCED_NOTIFICATION_ID,
    }
    assert bundle["identifier"]["system"] == NOTIFICATION_BUNDLE_ID_SYSTEM
    assert len(
        {
            own_identifier["value"],
            referenced_identifier["value"],
            bundle["identifier"]["value"],
        }
    ) == 3


def test_a9_all_relative_references_resolve_inside_bundle():
    bundle = _bundle()
    available_resources = {
        f"{entry['resource']['resourceType']}/{entry['resource']['id']}"
        for entry in bundle["entry"]
    }
    relative_references = {
        reference
        for reference in _collect_references(bundle)
        if "://" not in reference
    }

    assert relative_references
    assert relative_references <= available_resources

    external_references = {
        reference
        for reference in _collect_references(bundle)
        if "://" in reference
    }
    assert external_references == {
        "http://test/v5/fhir/DocumentReference/document-1",
        "http://test/v5/fhir/DocumentReference/document-2",
    }


def test_a10_single_sequence_document_reference_is_supported():
    sequence = _resource(
        _bundle(doc_ids=["document-1"]),
        "MolecularSequence",
    )
    document_references = [
        extension["valueReference"]["reference"]
        for extension in sequence["extension"]
        if extension["url"] == SEQUENCE_DOCUMENT_REFERENCE_EXTENSION
    ]

    assert document_references == [
        "http://test/v5/fhir/DocumentReference/document-1"
    ]


@pytest.mark.parametrize("doc_ids", [[], ["one", "two", "three"]])
def test_a11_invalid_sequence_document_reference_count_is_rejected(doc_ids):
    with pytest.raises(ValueError, match="one or two sequence documents"):
        _bundle(doc_ids=doc_ids)
