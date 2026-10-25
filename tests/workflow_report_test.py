import csv
import json

import igsupload.workflow as workflow
from igsupload.log.upload_report import UploadReport


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeApi:
    def __init__(self):
        self.document_number = 0

    def post_doc_ref(self, doc_ref):
        self.document_number += 1
        return f"doc-{self.document_number}"

    def get_presigned_url(self, doc_id, file_size):
        return {
            "uploadId": f"upload-{doc_id}",
            "presignedUrls": ["https://upload.invalid/part-1"],
            "partSizeBytes": file_size,
        }

    def put_file_chunks(self, file_path, part_size, urls, upload_id):
        return {
            "uploadId": upload_id,
            "completedChunks": [
                {"partNumber": 1, "eTag": "etag-1"},
            ],
        }

    def post_finish_upload(self, doc_id, complete_body):
        return FakeResponse(status_code=204)

    def post_start_validation(self, doc_id):
        return FakeResponse(status_code=202)

    def get_validation_status(self, doc_id):
        return {"done": True, "status": "VALID"}


def read_report(report: UploadReport) -> list[dict[str, str]]:
    with report.file_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_workflow_writes_successful_final_report(tmp_path, monkeypatch):
    metadata_dir = tmp_path / "metadata"
    reads_dir = tmp_path / "reads"
    report_dir = tmp_path / "logs"
    metadata_dir.mkdir()
    reads_dir.mkdir()
    report_dir.mkdir()

    csv_path = metadata_dir / "metadata.csv"
    csv_path.write_text(
        "FILE_1_NAME;FILE_2_NAME\n"
        "sample_R1.fastq;sample_R2.fastq\n",
        encoding="utf-8",
    )
    (reads_dir / "sample_R1.fastq").write_text("read 1", encoding="utf-8")
    (reads_dir / "sample_R2.fastq").write_text("read 2", encoding="utf-8")

    response_payload = {
        "parameter": [
            {
                "name": "submitterGeneratedNotificationID",
                "valueIdentifier": {"value": "notification-1"},
            },
            {
                "name": "transactionID",
                "valueIdentifier": {"value": "transaction-1"},
            },
            {
                "name": "labSequenceID",
                "valueIdentifier": {"value": "sequence-1"},
            },
        ]
    }
    monkeypatch.setattr(
        workflow,
        "send_notification",
        lambda api, base_url, row, doc_ids: FakeResponse(
            status_code=200,
            payload=response_payload,
        ),
    )

    report = UploadReport(report_path=report_dir, source_csv=csv_path)
    successful = workflow.start(
        csv_path=csv_path,
        fhir_base_url="https://demis.invalid",
        api=FakeApi(),
        report=report,
    )

    rows = read_report(report)

    assert successful is True
    assert len(rows) == 1
    assert rows[0]["status"] == "SUCCESS"
    assert rows[0]["stage"] == "DONE"
    assert json.loads(rows[0]["filenames"]) == [
        "sample_R1.fastq",
        "sample_R2.fastq",
    ]
    assert json.loads(rows[0]["document_reference_ids"]) == [
        "doc-1",
        "doc-2",
    ]
    assert json.loads(rows[0]["validation_statuses"]) == [
        "VALID",
        "VALID",
    ]
    assert rows[0]["notification_id"] == "notification-1"
    assert rows[0]["transaction_id"] == "transaction-1"
    assert rows[0]["lab_sequence_id"] == "sequence-1"


def test_workflow_writes_failed_row_and_continues(tmp_path, monkeypatch):
    metadata_dir = tmp_path / "metadata"
    reads_dir = tmp_path / "reads"
    report_dir = tmp_path / "logs"
    metadata_dir.mkdir()
    reads_dir.mkdir()
    report_dir.mkdir()

    csv_path = metadata_dir / "metadata.csv"
    csv_path.write_text(
        "FILE_1_NAME;FILE_2_NAME\n"
        "missing.fastq;\n"
        "available.fastq;\n",
        encoding="utf-8",
    )
    (reads_dir / "available.fastq").write_text("read", encoding="utf-8")

    response_payload = {
        "parameter": [
            {
                "name": "submitterGeneratedNotificationID",
                "valueIdentifier": {"value": "notification-2"},
            },
            {
                "name": "transactionID",
                "valueIdentifier": {"value": "transaction-2"},
            },
            {
                "name": "labSequenceID",
                "valueIdentifier": {"value": "sequence-2"},
            },
        ]
    }
    monkeypatch.setattr(
        workflow,
        "send_notification",
        lambda api, base_url, row, doc_ids: FakeResponse(
            status_code=200,
            payload=response_payload,
        ),
    )

    report = UploadReport(report_path=report_dir, source_csv=csv_path)
    successful = workflow.start(
        csv_path=csv_path,
        fhir_base_url="https://demis.invalid",
        api=FakeApi(),
        report=report,
    )

    rows = read_report(report)

    assert successful is False
    assert len(rows) == 2
    assert rows[0]["status"] == "FAILED"
    assert rows[0]["stage"] == "FILE_CHECK"
    assert rows[0]["error_type"] == "FileNotFoundError"
    assert "Sequence file not found" in rows[0]["message"]
    assert rows[1]["status"] == "SUCCESS"
    assert rows[1]["notification_id"] == "notification-2"
