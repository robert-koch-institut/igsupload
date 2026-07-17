import json
from unittest import mock

from igsupload.fhir_response import (
    parse_fhir_response,
    report_fhir_error,
    save_operation_outcome,
)


def _response(status_code, payload=None, text=""):
    response = mock.Mock(status_code=status_code, text=text)
    if payload is None:
        response.json.side_effect = ValueError("No JSON")
    else:
        response.json.return_value = payload
    return response


def test_operation_outcome_is_parsed_without_losing_payload():
    payload = {
        "resourceType": "OperationOutcome",
        "id": "outcome-1",
        "issue": [
            {
                "severity": "error",
                "code": "invalid",
                "details": {"text": "Profile validation failed"},
                "diagnostics": "Required element is missing",
                "expression": ["Bundle.entry[1].resource.code"],
                "extension": [{"url": "https://example.org/context"}],
            },
            {
                "severity": "warning",
                "code": "business-rule",
                "location": ["Bundle.entry[2]"],
            },
        ],
    }

    parsed = parse_fhir_response(_response(422, payload))

    assert parsed.payload == payload
    assert parsed.is_operation_outcome is True
    assert len(parsed.issues) == 2
    assert parsed.issues[0].details == "Profile validation failed"
    assert parsed.issues[0].diagnostics == "Required element is missing"
    assert parsed.issues[0].paths == ("Bundle.entry[1].resource.code",)
    assert parsed.issues[1].paths == ("Bundle.entry[2]",)


def test_operation_outcome_report_contains_context_and_every_issue(tmp_path):
    payload = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "invalid",
                "details": {"text": "Wrong profile"},
                "diagnostics": "Expected Patient profile",
                "expression": ["Bundle.entry[1].resource.meta.profile"],
            },
            {
                "severity": "warning",
                "code": "informational",
                "diagnostics": "Code display differs",
            },
        ],
    }
    parsed = parse_fhir_response(_response(422, payload))
    output = mock.Mock()

    with mock.patch(
        "igsupload.fhir_response.typer.style",
        side_effect=lambda text, **kwargs: text,
    ) as style:
        outcome_path = report_fhir_error(
            parsed,
            resource="Patient",
            expected_profile="https://example.org/StructureDefinition/Patient",
            output=output,
            outcome_directory=tmp_path,
        )

    rendered = "\n".join(call.args[0] for call in output.call_args_list)
    assert "Resource: Patient" in rendered
    assert "Expected profile: https://example.org/StructureDefinition/Patient" in rendered
    assert "Issue 1:" in rendered
    assert "Severity: error" in rendered
    assert "Code: invalid" in rendered
    assert "Path: Bundle.entry[1].resource.meta.profile" in rendered
    assert "Details: Wrong profile" in rendered
    assert "Diagnostics: Expected Patient profile" in rendered
    assert "Issue 2:" in rendered
    assert "Severity: warning" in rendered
    assert "=== Complete OperationOutcome available ===" in rendered
    assert "saved for detailed analysis" in rendered
    assert "Open this JSON file" in rendered
    assert json.dumps(payload, ensure_ascii=False, indent=2) not in rendered
    assert outcome_path is not None
    assert outcome_path.parent == tmp_path
    assert outcome_path.name.startswith(
        "operation-outcome_patient_"
    )
    assert json.loads(outcome_path.read_text(encoding="utf-8")) == payload
    assert outcome_path.stat().st_mode & 0o777 == 0o600
    assert mock.call(
        "FHIR request failed with HTTP status 422.",
        fg="red",
    ) in style.call_args_list
    assert mock.call("  Severity: error", fg="red") in style.call_args_list
    assert mock.call("  Severity: warning", fg="yellow") in style.call_args_list
    assert mock.call(
        "=== Complete OperationOutcome available ===",
        fg="yellow",
        bold=True,
    ) in style.call_args_list


def test_non_json_response_is_reported_without_parse_error():
    parsed = parse_fhir_response(_response(503, text="Service unavailable"))
    output = mock.Mock()

    report_fhir_error(parsed, resource="Notification Bundle", output=output)

    rendered = "\n".join(call.args[0] for call in output.call_args_list)
    assert "HTTP status 503" in rendered
    assert "Service unavailable" in rendered


def test_operation_outcome_filename_uses_readable_collision_suffix(tmp_path):
    payload = {"resourceType": "OperationOutcome", "issue": []}
    fixed_timestamp = mock.Mock()
    fixed_timestamp.strftime.return_value = "2026-07-17_134522"

    mocked_datetime = mock.Mock()
    mocked_datetime.now.return_value = fixed_timestamp

    with mock.patch("igsupload.fhir_response.datetime", mocked_datetime):
        first = save_operation_outcome(
            payload,
            directory=tmp_path,
            resource="Notification Bundle",
        )
        second = save_operation_outcome(
            payload,
            directory=tmp_path,
            resource="Notification Bundle",
        )

    assert first.name == (
        "operation-outcome_notification-bundle_2026-07-17_134522.json"
    )
    assert second.name == (
        "operation-outcome_notification-bundle_2026-07-17_134522_2.json"
    )
