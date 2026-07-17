import os
from types import SimpleNamespace
from unittest import mock

import pytest

from igsupload.workflow import start


def _row(file_1="file1.fq", file_2="file2.fq"):
    return SimpleNamespace(FILE_1_NAME=file_1, FILE_2_NAME=file_2)


def _secho_texts(mock_secho):
    return [str(call.args[0]) for call in mock_secho.call_args_list if call.args]


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def workflow_pipeline(monkeypatch):
    monkeypatch.setattr(
        "igsupload.workflow.threading.Thread",
        lambda *args, **kwargs: mock.Mock(start=lambda: None),
    )
    monkeypatch.setattr("igsupload.workflow.time.sleep", lambda seconds: None)
    monkeypatch.setattr("igsupload.workflow.os.path.abspath", lambda path: "/abs/" + path)
    monkeypatch.setattr("igsupload.workflow.os.path.dirname", lambda path: "dir")
    monkeypatch.setattr("igsupload.workflow.os.path.join", os.path.join)
    monkeypatch.setattr("igsupload.workflow.os.path.exists", lambda path: True)
    monkeypatch.setattr("igsupload.workflow.os.path.getsize", lambda path: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda path: "hash")
    monkeypatch.setattr(
        "igsupload.workflow.build_document_reference",
        lambda file_name, hash_value: {"file": file_name, "hash": hash_value},
    )
    monkeypatch.setattr(
        "igsupload.workflow.get_presigned_url",
        lambda token, doc_id, size: ("upload-id", ["url"], 100),
    )
    monkeypatch.setattr(
        "igsupload.workflow.put_chunks",
        lambda path, size, urls, upload_id: {
            "uploadId": upload_id,
            "completedChunks": [{"partNumber": 1, "eTag": "etag-1"}],
        },
    )
    monkeypatch.setattr(
        "igsupload.workflow.post_upload_body",
        lambda doc_id, body, token: True,
    )
    monkeypatch.setattr(
        "igsupload.workflow.start_validation",
        lambda doc_id, token: True,
    )


def test_notification_is_sent_once_after_both_files_are_valid(
    monkeypatch,
    workflow_pipeline,
):
    row = _row("Sample12346_R1.fastq", "Sample12346_R2.fastq")
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])

    post_document_reference = mock.Mock(side_effect=["doc-r1", "doc-r2"])
    poll_validation_status = mock.Mock(side_effect=["VALID", "VALID"])
    send_notification = mock.Mock(return_value=_Response())
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        post_document_reference,
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        poll_validation_status,
    )
    monkeypatch.setattr("igsupload.workflow.send_notification", send_notification)

    with mock.patch("igsupload.workflow.typer.secho") as secho:
        start("dummy.csv")

    send_notification.assert_called_once_with(row, ["doc-r1", "doc-r2"])
    assert any(
        "Notification for Sample12346_R1.fastq and Sample12346_R2.fastq "
        "sent successfully." in text
        for text in _secho_texts(secho)
    )


@pytest.mark.parametrize(
    "statuses",
    [
        ["INVALID", "VALID"],
        ["VALID", "INVALID"],
        ["TIMEOUT", "VALID"],
    ],
)
def test_notification_is_not_sent_if_any_file_is_not_valid(
    monkeypatch,
    workflow_pipeline,
    statuses,
):
    row = _row()
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(side_effect=["doc-r1", "doc-r2"]),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(side_effect=statuses),
    )
    send_notification = mock.Mock()
    monkeypatch.setattr("igsupload.workflow.send_notification", send_notification)

    with mock.patch("igsupload.workflow.typer.secho") as secho:
        start("dummy.csv")

    send_notification.assert_not_called()
    assert any("Notification not sent" in text for text in _secho_texts(secho))


def test_notification_is_not_sent_if_a_required_file_is_missing(
    monkeypatch,
    workflow_pipeline,
):
    row = _row(file_2="")
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(return_value="doc-r1"),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(return_value="VALID"),
    )
    send_notification = mock.Mock()
    monkeypatch.setattr("igsupload.workflow.send_notification", send_notification)

    with mock.patch("igsupload.workflow.typer.secho") as secho:
        start("dummy.csv")

    send_notification.assert_not_called()
    texts = _secho_texts(secho)
    assert any("Missing required sequence file: FILE_2_NAME" in text for text in texts)
    assert any("Notification not sent" in text for text in texts)


def test_notification_is_not_sent_if_document_reference_creation_fails(
    monkeypatch,
    workflow_pipeline,
):
    row = _row()
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(side_effect=["doc-r1", None]),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(return_value="VALID"),
    )
    send_notification = mock.Mock()
    monkeypatch.setattr("igsupload.workflow.send_notification", send_notification)

    with mock.patch("igsupload.workflow.typer.secho") as secho:
        start("dummy.csv")

    send_notification.assert_not_called()
    assert any(
        "Failed to create DocumentReference for file2.fq" in text
        for text in _secho_texts(secho)
    )


@pytest.mark.parametrize(
    ("failing_step", "expected_message"),
    [
        ("upload_info", "Failed to get upload information"),
        ("chunks", "Chunk upload incomplete"),
        ("finish", "Failed to finish upload"),
        ("validation_start", "Failed to start validation"),
    ],
)
def test_notification_is_not_sent_if_an_upload_step_fails(
    monkeypatch,
    workflow_pipeline,
    failing_step,
    expected_message,
):
    row = _row()
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(side_effect=["doc-r1", "doc-r2"]),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(return_value="VALID"),
    )

    if failing_step == "upload_info":
        monkeypatch.setattr(
            "igsupload.workflow.get_presigned_url",
            mock.Mock(side_effect=[None, ("upload-id", ["url"], 100)]),
        )
    elif failing_step == "chunks":
        monkeypatch.setattr(
            "igsupload.workflow.put_chunks",
            mock.Mock(
                side_effect=[
                    {"uploadId": "upload-id", "completedChunks": []},
                    {
                        "uploadId": "upload-id",
                        "completedChunks": [
                            {"partNumber": 1, "eTag": "etag-1"}
                        ],
                    },
                ]
            ),
        )
    elif failing_step == "finish":
        monkeypatch.setattr(
            "igsupload.workflow.post_upload_body",
            mock.Mock(side_effect=[False, True]),
        )
    else:
        monkeypatch.setattr(
            "igsupload.workflow.start_validation",
            mock.Mock(side_effect=[False, True]),
        )

    send_notification = mock.Mock()
    monkeypatch.setattr("igsupload.workflow.send_notification", send_notification)

    with mock.patch("igsupload.workflow.typer.secho") as secho:
        start("dummy.csv")

    send_notification.assert_not_called()
    texts = _secho_texts(secho)
    assert any(expected_message in text for text in texts)
    assert any("Notification not sent" in text for text in texts)


def test_document_reference_ids_are_isolated_per_csv_row(
    monkeypatch,
    workflow_pipeline,
):
    first_row = _row("first_R1.fq", "first_R2.fq")
    second_row = _row("second_R1.fq", "second_R2.fq")
    monkeypatch.setattr(
        "igsupload.workflow.read_csv",
        lambda path: [first_row, second_row],
    )
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(side_effect=["doc-1", "doc-2", "doc-3", "doc-4"]),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(return_value="VALID"),
    )
    send_notification = mock.Mock(return_value=_Response())
    monkeypatch.setattr("igsupload.workflow.send_notification", send_notification)

    with mock.patch("igsupload.workflow.typer.secho"):
        start("dummy.csv")

    assert send_notification.call_args_list == [
        mock.call(first_row, ["doc-1", "doc-2"]),
        mock.call(second_row, ["doc-3", "doc-4"]),
    ]


def test_successful_notification_parameters_are_logged(
    monkeypatch,
    workflow_pipeline,
):
    row = _row("Sample12346_R1.fastq", "Sample12346_R2.fastq")
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(side_effect=["doc-r1", "doc-r2"]),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(return_value="VALID"),
    )
    response_payload = {
        "resourceType": "Parameters",
        "parameter": [
            {
                "name": "submitterGeneratedNotificationID",
                "valueIdentifier": {"value": "notification-id"},
            },
            {
                "name": "transactionID",
                "valueIdentifier": {"value": "transaction-id"},
            },
            {
                "name": "labSequenceID",
                "valueIdentifier": {"value": "lab-sequence-id"},
            },
        ],
    }
    monkeypatch.setattr(
        "igsupload.workflow.send_notification",
        mock.Mock(return_value=_Response(payload=response_payload)),
    )
    log_to_csv = mock.Mock()
    monkeypatch.setattr("igsupload.workflow.log_to_csv", log_to_csv)

    with mock.patch("igsupload.workflow.typer.secho"):
        start("dummy.csv")

    log_to_csv.assert_called_once_with(
        filename="Sample12346_R1.fastq and Sample12346_R2.fastq",
        notification_id="notification-id",
        transaction_id="transaction-id",
        lab_sequence_id="lab-sequence-id",
        document_reference_id=["doc-r1", "doc-r2"],
        status="OK",
    )


def test_failed_notification_reports_operation_outcome(
    monkeypatch,
    workflow_pipeline,
    tmp_path,
):
    monkeypatch.setattr("igsupload.igsupload_logger.logging_path", str(tmp_path))
    row = _row()
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda path: [row])
    monkeypatch.setattr(
        "igsupload.workflow.post_document_reference",
        mock.Mock(side_effect=["doc-r1", "doc-r2"]),
    )
    monkeypatch.setattr(
        "igsupload.workflow.poll_validation_status",
        mock.Mock(return_value="VALID"),
    )
    operation_outcome = {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": "invalid",
                "details": {"text": "Profile mismatch"},
                "diagnostics": "Unexpected patient profile",
                "expression": ["Bundle.entry[1].resource.meta.profile"],
            }
        ],
    }
    monkeypatch.setattr(
        "igsupload.workflow.send_notification",
        mock.Mock(return_value=_Response(status_code=422, payload=operation_outcome)),
    )
    log_to_csv = mock.Mock()
    monkeypatch.setattr("igsupload.workflow.log_to_csv", log_to_csv)

    with mock.patch("igsupload.workflow.typer.echo") as echo:
        start("dummy.csv")

    rendered = "\n".join(str(call.args[0]) for call in echo.call_args_list)
    assert "Resource: Notification Bundle" in rendered
    assert "Expected profile:" in rendered
    assert "Severity: error" in rendered
    assert "Path: Bundle.entry[1].resource.meta.profile" in rendered
    assert "Details: Profile mismatch" in rendered
    assert "Diagnostics: Unexpected patient profile" in rendered
    assert "=== Complete OperationOutcome available ===" in rendered
    saved_outcomes = list(
        (tmp_path / "logging").glob(
            "operation-outcome_notification-bundle_*.json"
        )
    )
    assert len(saved_outcomes) == 1
    assert saved_outcomes[0].read_text(encoding="utf-8").strip()
    log_to_csv.assert_not_called()
