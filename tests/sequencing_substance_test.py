from dataclasses import fields

import igsupload.igs_notification as igs_notification
from igsupload.extract_csv import CsvRow
from igsupload.igs_notification import (
    ADAPTER_SUBSTANCE_PROFILE,
    PRIMER_SUBSTANCE_PROFILE,
    SEQUENCING_SUBSTANCES_SYSTEM,
    build_notification_bundle,
)


def _row(**overrides) -> CsvRow:
    values = {field.name: "" for field in fields(CsvRow)}
    values.update(
        {
            "DEMIS_NOTIFICATION_ID": "6cb7099d-8d53-4ee4-96ca-c55761b347d4",
            "STATUS": "final",
        }
    )
    values.update(overrides)
    return CsvRow(**values)


def _resources(bundle: dict, resource_type: str) -> list[dict]:
    return [
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == resource_type
    ]


def _substances_with_profile(bundle: dict, profile: str) -> list[dict]:
    return [
        substance
        for substance in _resources(bundle, "Substance")
        if substance["meta"]["profile"] == [profile]
    ]


def test_adapters_and_primer_use_current_substance_fields(monkeypatch):
    monkeypatch.setattr(
        igs_notification,
        "INCLUDE_SEQUENCING_ADDITIVES",
        True,
    )
    bundle = build_notification_bundle(
        _row(
            ADAPTER="adapter-1+adapter-2",
            PRIMER_SCHEME="ARTICv4.1",
        ),
        ["document-1", "document-2"],
    )

    adapters = _substances_with_profile(bundle, ADAPTER_SUBSTANCE_PROFILE)
    primers = _substances_with_profile(bundle, PRIMER_SUBSTANCE_PROFILE)

    assert len(adapters) == 2
    assert {adapter["code"]["text"] for adapter in adapters} == {
        "adapter-1",
        "adapter-2",
    }
    for adapter in adapters:
        assert adapter["category"] == [{
            "coding": [{
                "system": SEQUENCING_SUBSTANCES_SYSTEM,
                "code": "adapter",
            }]
        }]
        assert "coding" not in adapter["code"]
        assert "description" not in adapter

    assert len(primers) == 1
    assert primers[0]["category"] == [{
        "coding": [{
            "system": SEQUENCING_SUBSTANCES_SYSTEM,
            "code": "primer",
        }]
    }]
    assert primers[0]["code"] == {"text": "ARTICv4.1"}
    assert "coding" not in primers[0]["code"]
    assert "description" not in primers[0]
    assert adapters[0]["category"] != primers[0]["category"]

    specimen = _resources(bundle, "Specimen")[0]
    additive_references = {
        additive["reference"]
        for additive in specimen["processing"][0]["additive"]
    }
    substance_references = {
        f"Substance/{substance['id']}"
        for substance in adapters + primers
    }
    assert additive_references == substance_references


def test_single_adapter_does_not_create_empty_second_substance(monkeypatch):
    monkeypatch.setattr(
        igs_notification,
        "INCLUDE_SEQUENCING_ADDITIVES",
        True,
    )
    bundle = build_notification_bundle(
        _row(ADAPTER="adapter-1"),
        ["document-1", "document-2"],
    )

    adapters = _substances_with_profile(bundle, ADAPTER_SUBSTANCE_PROFILE)
    primers = _substances_with_profile(bundle, PRIMER_SUBSTANCE_PROFILE)
    specimen = _resources(bundle, "Specimen")[0]

    assert len(adapters) == 1
    assert adapters[0]["code"] == {"text": "adapter-1"}
    assert primers == []
    assert specimen["processing"][0]["additive"] == [
        {"reference": f"Substance/{adapters[0]['id']}"}
    ]


def test_additives_are_enabled_by_default():
    bundle = build_notification_bundle(
        _row(
            ADAPTER="adapter-1+adapter-2",
            PRIMER_SCHEME="ARTICv4.1",
            NAME_AMP_PROTOCOL="Amplicon protocol",
            SEQUENCING_STRATEGY="amplicon",
            DATE_OF_SEQUENCING="2026-07-13",
        ),
        ["document-1", "document-2"],
    )

    specimen = _resources(bundle, "Specimen")[0]
    processing = specimen["processing"][0]

    assert igs_notification.INCLUDE_SEQUENCING_ADDITIVES is True
    assert len(processing["additive"]) == 3
    assert len(_substances_with_profile(bundle, ADAPTER_SUBSTANCE_PROFILE)) == 2
    assert len(_substances_with_profile(bundle, PRIMER_SUBSTANCE_PROFILE)) == 1
    assert processing["description"] == "Amplicon protocol"
    assert processing["procedure"]["coding"][0]["code"] == "amplicon"
    assert processing["timeDateTime"] == "2026-07-13"
