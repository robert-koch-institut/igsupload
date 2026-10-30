import csv
import json
from unittest import mock

import pytest
import requests

from igsupload import workflow
from igsupload.log.upload_report import UploadReport
from tests.conftest import TEST_BASE_URL


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self.payload


class FakeApi:
    def __init__(self, validation_status="VALID"):
        self.document_number = 0
        self.validation_status = validation_status

    def post_doc_ref(self, doc_ref):
        self.document_number += 1
        return f"doc-{self.document_number}"

    def get_presigned_url(self, doc_id, file_size):
        return {
            "uploadId": f"upload-{doc_id}",
            "presignedUrls": ["https://upload.test.invalid/part-1"],
            "partSizeBytes": file_size,
        }

    def put_file_chunks(self, file_path, part_size, urls, upload_id):
        return {
            "uploadId": upload_id,
            "completedChunks": [{"partNumber": 1, "eTag": "etag-1"}],
        }

    def post_finish_upload(self, doc_id, complete_body):
        return FakeResponse(status_code=204)

    def post_start_validation(self, doc_id):
        return FakeResponse(status_code=202)

    def get_validation_status(self, doc_id):
        return {"done": True, "status": self.validation_status}


def response_payload(suffix="1"):
    return {
        "resourceType": "Parameters",
        "parameter": [
            {
                "name": "submitterGeneratedNotificationID",
                "valueIdentifier": {"value": f"notification-{suffix}"},
            },
            {
                "name": "transactionID",
                "valueIdentifier": {"value": f"transaction-{suffix}"},
            },
            {
                "name": "labSequenceID",
                "valueIdentifier": {"value": f"sequence-{suffix}"},
            },
        ],
    }


def create_dataset(tmp_path, rows):
    metadata_dir = tmp_path / "metadata"
    reads_dir = tmp_path / "reads"
    logs_dir = tmp_path / "logs"
    metadata_dir.mkdir()
    reads_dir.mkdir()
    logs_dir.mkdir()

    csv_path = metadata_dir / "metadata.csv"
    csv_path.write_text(
        "FILE_1_NAME;FILE_2_NAME\n"
        + "".join(f"{first};{second}\n" for first, second in rows),
        encoding="utf-8",
    )
    return csv_path, reads_dir, logs_dir


def read_report(report):
    with report.file_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_successful_row_uploads_files_and_writes_response_ids(
    tmp_path,
    monkeypatch,
):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("sample_R1.fq.gz", "sample_R2.fq.gz")],
    )
    (reads_dir / "sample_R1.fq.gz").write_bytes(b"read-1")
    (reads_dir / "sample_R2.fq.gz").write_bytes(b"read-2")
    send_notification = mock.Mock(
        return_value=FakeResponse(payload=response_payload())
    )
    monkeypatch.setattr(workflow, "send_notification", send_notification)
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(
        csv_path,
        TEST_BASE_URL,
        FakeApi(),
        report,
    )

    row = read_report(report)[0]
    assert successful is True
    assert row["status"] == "SUCCESS"
    assert json.loads(row["document_reference_ids"]) == ["doc-1", "doc-2"]
    assert json.loads(row["validation_statuses"]) == ["VALID", "VALID"]
    assert row["notification_id"] == "notification-1"
    assert row["transaction_id"] == "transaction-1"
    assert row["lab_sequence_id"] == "sequence-1"
    assert send_notification.call_args.args[1] == TEST_BASE_URL
    assert send_notification.call_args.args[3] == ["doc-1", "doc-2"]


def test_failed_row_does_not_stop_following_rows(tmp_path, monkeypatch):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("missing.fastq", ""), ("available.fastq", "")],
    )
    (reads_dir / "available.fastq").write_bytes(b"read")
    monkeypatch.setattr(
        workflow,
        "send_notification",
        mock.Mock(return_value=FakeResponse(payload=response_payload("2"))),
    )
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(csv_path, TEST_BASE_URL, FakeApi(), report)

    rows = read_report(report)
    assert successful is False
    assert rows[0]["status"] == "FAILED"
    assert rows[0]["stage"] == "FILE_CHECK"
    assert rows[0]["error_type"] == "FileNotFoundError"
    assert rows[1]["status"] == "SUCCESS"
    assert rows[1]["notification_id"] == "notification-2"


def test_invalid_file_validation_prevents_notification(tmp_path, monkeypatch):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("invalid.fastq", "")],
    )
    (reads_dir / "invalid.fastq").write_bytes(b"not-fastq")
    send_notification = mock.Mock()
    monkeypatch.setattr(workflow, "send_notification", send_notification)
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(
        csv_path,
        TEST_BASE_URL,
        FakeApi(validation_status="INVALID"),
        report,
    )

    row = read_report(report)[0]
    assert successful is False
    assert row["status"] == "FAILED"
    assert row["stage"] == "VALIDATION"
    assert json.loads(row["validation_statuses"]) == ["INVALID"]
    send_notification.assert_not_called()


def test_accepted_notification_with_missing_ids_needs_review(
    tmp_path,
    monkeypatch,
):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("sample.fastq", "")],
    )
    (reads_dir / "sample.fastq").write_bytes(b"read")
    monkeypatch.setattr(
        workflow,
        "send_notification",
        mock.Mock(return_value=FakeResponse(payload={"parameter": []})),
    )
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(csv_path, TEST_BASE_URL, FakeApi(), report)

    row = read_report(report)[0]
    assert successful is False
    assert row["status"] == "NEEDS_REVIEW"
    assert row["error_type"] == "MissingResponseData"
    assert "notification_id" in row["message"]
    assert "transaction_id" in row["message"]
    assert "lab_sequence_id" in row["message"]


def test_accepted_non_json_response_needs_review(tmp_path, monkeypatch):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("sample.fastq", "")],
    )
    (reads_dir / "sample.fastq").write_bytes(b"read")
    response = FakeResponse(payload={})
    response.json = mock.Mock(side_effect=ValueError("not JSON"))
    monkeypatch.setattr(
        workflow,
        "send_notification",
        mock.Mock(return_value=response),
    )
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(csv_path, TEST_BASE_URL, FakeApi(), report)

    row = read_report(report)[0]
    assert successful is False
    assert row["status"] == "NEEDS_REVIEW"
    assert row["error_type"] == "InvalidResponse"


def test_fhir_rejection_is_saved_and_row_is_failed(tmp_path, monkeypatch):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("sample.fastq", "")],
    )
    (reads_dir / "sample.fastq").write_bytes(b"read")
    outcome = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "processing",
                "diagnostics": "threeDigitPostalCode failed",
                "location": ["Bundle.entry[1].resource.address[0].postalCode"],
            }
        ],
    }
    response = FakeResponse(status_code=422, payload=outcome)
    http_error = requests.HTTPError("422 Unprocessable Entity", response=response)
    monkeypatch.setattr(
        workflow,
        "send_notification",
        mock.Mock(side_effect=http_error),
    )
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(csv_path, TEST_BASE_URL, FakeApi(), report)

    row = read_report(report)[0]
    saved_outcomes = list(logs_dir.glob("operation-outcome_*.json"))
    assert successful is False
    assert row["status"] == "FAILED"
    assert row["stage"] == "NOTIFICATION"
    assert row["error_type"] == "HTTPError"
    assert len(saved_outcomes) == 1
    assert json.loads(saved_outcomes[0].read_text(encoding="utf-8")) == outcome


def test_filename_cannot_escape_reads_directory(tmp_path, monkeypatch):
    csv_path, _, logs_dir = create_dataset(
        tmp_path,
        [("../outside.fastq", "")],
    )
    (tmp_path / "outside.fastq").write_bytes(b"read")
    send_notification = mock.Mock()
    monkeypatch.setattr(workflow, "send_notification", send_notification)
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(csv_path, TEST_BASE_URL, FakeApi(), report)

    row = read_report(report)[0]
    assert successful is False
    assert row["status"] == "FAILED"
    assert row["error_type"] == "ValueError"
    assert "outside the reads directory" in row["message"]
    send_notification.assert_not_called()


def test_first_sequence_file_is_required(tmp_path, monkeypatch):
    csv_path, reads_dir, logs_dir = create_dataset(
        tmp_path,
        [("", "optional.fastq")],
    )
    (reads_dir / "optional.fastq").write_bytes(b"read")
    send_notification = mock.Mock()
    monkeypatch.setattr(workflow, "send_notification", send_notification)
    report = UploadReport(logs_dir, csv_path)

    successful = workflow.start(csv_path, TEST_BASE_URL, FakeApi(), report)

    row = read_report(report)[0]
    assert successful is False
    assert row["status"] == "FAILED"
    assert row["stage"] == "METADATA"
    assert row["error_type"] == "ValueError"
    assert "FILE_1_NAME" in row["message"]
    send_notification.assert_not_called()


def test_validation_polling_times_out(monkeypatch):
    api = mock.Mock()
    api.get_validation_status.return_value = {
        "done": False,
        "status": "VALIDATING",
    }
    monotonic_values = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr(
        workflow.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(workflow.time, "time", lambda: 100.0)
    monkeypatch.setattr(workflow.time, "sleep", mock.Mock())

    with pytest.raises(TimeoutError, match="Validation timed out"):
        workflow.wait_for_validation(api, "document-1", max_wait_seconds=1)
