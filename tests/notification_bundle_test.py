import pytest

from igsupload.builders.fhir_constants import (
    ADAPTER_SUBSTANCE_PROFILE,
    DIAGNOSTIC_REPORT_PROFILE,
    MOLECULAR_SEQUENCE_PROFILE,
    NOTIFICATION_BUNDLE_ID_SYSTEM,
    NOTIFICATION_BUNDLE_PROFILE,
    NOTIFICATION_ID_SYSTEM,
    NOTIFICATION_PROFILE,
    NOTIFIED_PERSON_ANONYMOUS_PROFILE,
    OBSERVATION_PROFILE,
    PRIMER_SUBSTANCE_PROFILE,
    SEQUENCE_DOCUMENT_REFERENCE_EXTENSION,
    SPECIMEN_PROFILE,
)
from igsupload.builders.igs_notification import build_notification_bundle
from tests.conftest import TEST_BASE_URL

REFERENCED_NOTIFICATION_ID = "6cb7099d-8d53-4ee4-96ca-c55761b347d4"


def resources(bundle, resource_type):
    return [
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == resource_type
    ]


def resource(bundle, resource_type):
    matches = resources(bundle, resource_type)
    assert len(matches) == 1
    return matches[0]


def collect_references(value):
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            if key == "reference" and isinstance(item, str):
                result.append(item)
            else:
                result.extend(collect_references(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(collect_references(item))
        return result
    return []


def build_bundle(csv_row_factory, doc_ids=None, **overrides):
    return build_notification_bundle(
        TEST_BASE_URL,
        csv_row_factory(**overrides),
        ["document-1", "document-2"] if doc_ids is None else doc_ids,
    )


def test_bundle_contains_core_profiles_and_resolvable_references(
    csv_row_factory,
):
    bundle = build_bundle(csv_row_factory)

    assert bundle["meta"]["profile"] == [NOTIFICATION_BUNDLE_PROFILE]
    assert bundle["entry"][0]["resource"]["resourceType"] == "Composition"
    assert resource(bundle, "Composition")["meta"]["profile"] == [
        NOTIFICATION_PROFILE
    ]
    assert resource(bundle, "Patient")["meta"]["profile"] == [
        NOTIFIED_PERSON_ANONYMOUS_PROFILE
    ]
    assert resource(bundle, "Specimen")["meta"]["profile"] == [SPECIMEN_PROFILE]
    assert resource(bundle, "MolecularSequence")["meta"]["profile"] == [
        MOLECULAR_SEQUENCE_PROFILE
    ]
    assert resource(bundle, "Observation")["meta"]["profile"] == [
        OBSERVATION_PROFILE
    ]
    assert resource(bundle, "DiagnosticReport")["meta"]["profile"] == [
        DIAGNOSTIC_REPORT_PROFILE
    ]

    available = {
        f"{entry['resource']['resourceType']}/{entry['resource']['id']}"
        for entry in bundle["entry"]
    }
    relative_references = {
        reference
        for reference in collect_references(bundle)
        if "://" not in reference
    }
    assert relative_references <= available


def test_anonymous_patient_contains_only_supported_demographics(csv_row_factory):
    patient = resource(build_bundle(csv_row_factory), "Patient")

    assert patient["gender"] == "male"
    assert patient["birthDate"] == "2000-12"
    assert patient["address"][0]["postalCode"] == "104"
    assert "name" not in patient
    assert "identifier" not in patient


def test_one_or_two_document_references_are_supported(csv_row_factory):
    bundle = build_bundle(csv_row_factory, doc_ids=["document-1"])
    sequence = resource(bundle, "MolecularSequence")
    references = [
        extension["valueReference"]["reference"]
        for extension in sequence["extension"]
        if extension["url"] == SEQUENCE_DOCUMENT_REFERENCE_EXTENSION
    ]

    assert references == [
        f"{TEST_BASE_URL}/v5/fhir/DocumentReference/document-1"
    ]


@pytest.mark.parametrize("doc_ids", [[], ["one", "two", "three"]])
def test_invalid_document_count_is_rejected(csv_row_factory, doc_ids):
    with pytest.raises(ValueError, match="one or two sequence documents"):
        build_bundle(csv_row_factory, doc_ids=doc_ids)


def test_notification_identifiers_are_distinct(csv_row_factory):
    bundle = build_bundle(csv_row_factory)
    composition = resource(bundle, "Composition")
    notification_id = composition["identifier"]
    referenced_id = composition["relatesTo"][0]["targetReference"]["identifier"]
    bundle_id = bundle["identifier"]

    assert notification_id["system"] == NOTIFICATION_ID_SYSTEM
    assert referenced_id == {
        "system": NOTIFICATION_ID_SYSTEM,
        "value": REFERENCED_NOTIFICATION_ID,
    }
    assert bundle_id["system"] == NOTIFICATION_BUNDLE_ID_SYSTEM
    assert len(
        {notification_id["value"], referenced_id["value"], bundle_id["value"]}
    ) == 3


def test_adapters_and_primer_are_represented_as_substances(csv_row_factory):
    bundle = build_bundle(csv_row_factory)
    substances = resources(bundle, "Substance")
    adapters = [
        item
        for item in substances
        if item["meta"]["profile"] == [ADAPTER_SUBSTANCE_PROFILE]
    ]
    primers = [
        item
        for item in substances
        if item["meta"]["profile"] == [PRIMER_SUBSTANCE_PROFILE]
    ]

    assert [item["code"]["text"] for item in adapters] == [
        "adapter-1",
        "adapter-2",
    ]
    assert [item["code"]["text"] for item in primers] == ["ARTICv4.1"]
