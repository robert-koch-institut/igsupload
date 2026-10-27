import json

from igsupload.builders.fhir_response import (
    parse_fhir_response,
    report_fhir_error,
)


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        if self.payload is None:
            raise ValueError("not JSON")
        return self.payload


def test_operation_outcome_is_parsed_and_saved(tmp_path):
    payload = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "processing",
                "details": {"text": "Invalid postal code"},
                "diagnostics": "threeDigitPostalCode failed",
                "expression": ["Bundle.entry[1].resource.address[0].postalCode"],
            }
        ],
    }
    parsed = parse_fhir_response(FakeResponse(422, payload))
    output = []

    saved_path = report_fhir_error(
        parsed,
        resource="Notification Bundle",
        expected_profile="test-profile",
        output=output.append,
        outcome_directory=tmp_path,
    )

    assert parsed.is_operation_outcome is True
    assert parsed.issues[0].diagnostics == "threeDigitPostalCode failed"
    assert parsed.issues[0].paths == (
        "Bundle.entry[1].resource.address[0].postalCode",
    )
    assert saved_path is not None
    assert json.loads(saved_path.read_text(encoding="utf-8")) == payload
    assert saved_path.stat().st_mode & 0o777 == 0o600
    assert any("Diagnostics: threeDigitPostalCode failed" in line for line in output)


def test_non_json_error_response_remains_available_as_text():
    parsed = parse_fhir_response(FakeResponse(502, text="Bad Gateway"))

    assert parsed.is_operation_outcome is False
    assert parsed.payload is None
    assert parsed.text == "Bad Gateway"
    assert parsed.issues == ()
