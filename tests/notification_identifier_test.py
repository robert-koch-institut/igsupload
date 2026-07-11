from dataclasses import fields
from unittest import mock

import pytest

from igsupload.extract_csv import CsvRow
from igsupload.igs_notification import (
    NOTIFICATION_BUNDLE_ID_SYSTEM,
    NOTIFICATION_ID_SYSTEM,
    build_notification_bundle,
)


REFERENCED_NOTIFICATION_ID = "6cb7099d-8d53-4ee4-96ca-c55761b347d4"
NEW_NOTIFICATION_ID = "10000000-0000-4000-8000-000000000001"
NEW_BUNDLE_ID = "20000000-0000-4000-8000-000000000002"


def _row(**overrides) -> CsvRow:
    values = {field.name: "" for field in fields(CsvRow)}
    values.update(
        {
            "DEMIS_NOTIFICATION_ID": REFERENCED_NOTIFICATION_ID,
            "STATUS": "final",
            "ADAPTER": "adapter-1+adapter-2",
        }
    )
    values.update(overrides)
    return CsvRow(**values)


def _uuid_sequence():
    yield NEW_NOTIFICATION_ID
    yield NEW_BUNDLE_ID
    counter = 3
    while True:
        yield f"00000000-0000-4000-8000-{counter:012d}"
        counter += 1


def test_notification_reference_and_bundle_identifiers_are_distinct():
    generated_uuids = _uuid_sequence()
    with mock.patch(
        "igsupload.igs_notification.uuid.uuid4",
        side_effect=lambda: next(generated_uuids),
    ):
        bundle = build_notification_bundle(_row(), ["document-1", "document-2"])

    composition = bundle["entry"][0]["resource"]

    assert composition["id"] == NEW_NOTIFICATION_ID
    assert composition["identifier"] == {
        "system": NOTIFICATION_ID_SYSTEM,
        "value": NEW_NOTIFICATION_ID,
    }
    assert composition["relatesTo"][0]["targetReference"]["identifier"] == {
        "system": NOTIFICATION_ID_SYSTEM,
        "value": REFERENCED_NOTIFICATION_ID,
    }
    assert bundle["identifier"] == {
        "system": NOTIFICATION_BUNDLE_ID_SYSTEM,
        "value": NEW_BUNDLE_ID,
    }
    assert len(
        {
            composition["identifier"]["value"],
            composition["relatesTo"][0]["targetReference"]["identifier"]["value"],
            bundle["identifier"]["value"],
        }
    ) == 3


@pytest.mark.parametrize("value", ["", "not-a-uuid"])
def test_referenced_notification_id_must_be_a_uuid(value):
    with pytest.raises(ValueError, match="DEMIS_NOTIFICATION_ID must contain"):
        build_notification_bundle(
            _row(DEMIS_NOTIFICATION_ID=value),
            ["document-1", "document-2"],
        )


def test_generated_notification_id_cannot_repeat_referenced_id():
    generated_uuids = iter(
        [
            REFERENCED_NOTIFICATION_ID,
            NEW_NOTIFICATION_ID,
            NEW_BUNDLE_ID,
            *[
                f"00000000-0000-4000-8000-{counter:012d}"
                for counter in range(3, 20)
            ],
        ]
    )
    with mock.patch(
        "igsupload.igs_notification.uuid.uuid4",
        side_effect=lambda: next(generated_uuids),
    ):
        bundle = build_notification_bundle(_row(), ["document-1", "document-2"])

    composition = bundle["entry"][0]["resource"]
    assert composition["identifier"]["value"] == NEW_NOTIFICATION_ID
    assert bundle["identifier"]["value"] == NEW_BUNDLE_ID
