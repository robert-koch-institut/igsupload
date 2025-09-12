import pytest
import os
from unittest import mock

from igsupload.workflow import start

@pytest.fixture(autouse=True)
def mock_open(monkeypatch):
    # Verhindert IO-Fehler überall (z.B. open("file1.fq"))
    monkeypatch.setattr("builtins.open", mock.mock_open(read_data=b"irrelevant"))  # b"irrelevant" für binary reads

@pytest.fixture
def workflow_base(monkeypatch):
    # Patch Thread/Token
    monkeypatch.setattr("threading.Thread", lambda *a, **kw: mock.Mock(start=lambda: None))
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda csv_path: [
        {"FILE_1_NAME": "file1.fq", "FILE_2_NAME": "file2.fq", "SEQUENCING_LAB.DEMIS_LAB_ID": "labid"}
    ])
    monkeypatch.setattr("os.path.abspath", lambda p: "/abs/" + p)
    monkeypatch.setattr("os.path.dirname", lambda p: "dir")
    monkeypatch.setattr("os.path.join", os.path.join)

def get_secho_texts(mock_secho):
    texts = []
    for call in mock_secho.call_args_list:
        args, kwargs = call
        if args:
            texts.append(str(args[0]))
    return texts

def get_echo_texts(mock_echo):
    texts = []
    for call in mock_echo.call_args_list:
        args, kwargs = call
        if args:
            texts.append(str(args[0]))
    return texts

def test_workflow_success(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: "docid")
    monkeypatch.setattr("igsupload.workflow.get_presigned_url", lambda token, docid, size: ("up_id", ["url1"], 42))
    monkeypatch.setattr("igsupload.workflow.put_chunks", lambda path, size, urls, uid: {"uploadId": "up_id", "completedChunks": []})
    monkeypatch.setattr("igsupload.workflow.post_upload_body", lambda docid, body, token: None)
    monkeypatch.setattr("igsupload.workflow.start_validation", lambda docid, token: None)
    monkeypatch.setattr("igsupload.workflow.poll_validation_status", lambda docid, token: "VALID")
    monkeypatch.setattr("igsupload.workflow.send_notification", lambda fn, docid, labid: {
        "parameter": [
            {"name": "submitterGeneratedNotificationID", "valueString": "notifid"},
            {"name": "transactionID", "valueString": "transid"},
            {"name": "labSequenceID", "valueString": "seqid"}
        ]
    })
    monkeypatch.setattr("igsupload.workflow.extract_param", lambda params, key: next((p["valueString"] for p in params if p["name"] == key), None))
    monkeypatch.setattr("igsupload.workflow.log_to_csv", lambda **kw: None)

    with mock.patch("igsupload.workflow.typer.secho"), mock.patch("igsupload.workflow.typer.echo"):
        start("dummy.csv")

def test_workflow_file_not_found(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: False)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    with mock.patch("igsupload.workflow.typer.secho") as mock_secho:
        start("dummy.csv")
        texts = get_secho_texts(mock_secho)
        assert any("File not found" in t for t in texts)

def test_workflow_document_reference_failed(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: None)
    with mock.patch("igsupload.workflow.typer.secho") as mock_secho:
        start("dummy.csv")
        texts = get_secho_texts(mock_secho)
        assert any("Failed to create DocumentReference" in t for t in texts)

def test_workflow_validation_failed(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: "docid")
    monkeypatch.setattr("igsupload.workflow.get_presigned_url", lambda token, docid, size: ("up_id", ["url1"], 42))
    monkeypatch.setattr("igsupload.workflow.put_chunks", lambda path, size, urls, uid: {"uploadId": "up_id", "completedChunks": []})
    monkeypatch.setattr("igsupload.workflow.post_upload_body", lambda docid, body, token: None)
    monkeypatch.setattr("igsupload.workflow.start_validation", lambda docid, token: None)
    monkeypatch.setattr("igsupload.workflow.poll_validation_status", lambda docid, token: "INVALID")
    with mock.patch("igsupload.workflow.typer.secho") as mock_secho:
        start("dummy.csv")
        texts = get_secho_texts(mock_secho)
        assert any("Validation failed" in t for t in texts)

def test_workflow_notification_exception_with_json(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: "docid")
    monkeypatch.setattr("igsupload.workflow.get_presigned_url", lambda token, docid, size: ("up_id", ["url1"], 42))
    monkeypatch.setattr("igsupload.workflow.put_chunks", lambda path, size, urls, uid: {"uploadId": "up_id", "completedChunks": []})
    monkeypatch.setattr("igsupload.workflow.post_upload_body", lambda docid, body, token: None)
    monkeypatch.setattr("igsupload.workflow.start_validation", lambda docid, token: None)
    monkeypatch.setattr("igsupload.workflow.poll_validation_status", lambda docid, token: "VALID")
    class FakeResponse:
        status_code = 400
        def json(self): return {"error": "fail"}
        text = "failtext"
    class FakeException(Exception):
        def __init__(self): self.response = FakeResponse()
    def fail_notify(*a, **kw): raise FakeException()
    monkeypatch.setattr("igsupload.workflow.send_notification", fail_notify)
    with mock.patch("igsupload.workflow.typer.secho") as mock_secho, mock.patch("igsupload.workflow.typer.echo") as mock_echo:
        start("dummy.csv")
        secho_texts = get_secho_texts(mock_secho)
        echo_texts = get_echo_texts(mock_echo)
        assert any("Error 400 sending notification" in t for t in secho_texts)
        assert any("error" in t for t in echo_texts)

def test_workflow_notification_exception_without_json(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: "docid")
    monkeypatch.setattr("igsupload.workflow.get_presigned_url", lambda token, docid, size: ("up_id", ["url1"], 42))
    monkeypatch.setattr("igsupload.workflow.put_chunks", lambda path, size, urls, uid: {"uploadId": "up_id", "completedChunks": []})
    monkeypatch.setattr("igsupload.workflow.post_upload_body", lambda docid, body, token: None)
    monkeypatch.setattr("igsupload.workflow.start_validation", lambda docid, token: None)
    monkeypatch.setattr("igsupload.workflow.poll_validation_status", lambda docid, token: "VALID")
    class FakeResponse:
        status_code = 400
        def json(self): raise ValueError("no json")
        text = "failtext"
    class FakeException(Exception):
        def __init__(self): self.response = FakeResponse()
    def fail_notify(*a, **kw): raise FakeException()
    monkeypatch.setattr("igsupload.workflow.send_notification", fail_notify)
    with mock.patch("igsupload.workflow.typer.secho") as mock_secho, mock.patch("igsupload.workflow.typer.echo") as mock_echo:
        start("dummy.csv")
        secho_texts = get_secho_texts(mock_secho)
        echo_texts = get_echo_texts(mock_echo)
        assert any("Error 400 sending notification" in t for t in secho_texts)
        assert any("failtext" in t for t in echo_texts)

def test_workflow_notification_exception_other(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: "docid")
    monkeypatch.setattr("igsupload.workflow.get_presigned_url", lambda token, docid, size: ("up_id", ["url1"], 42))
    monkeypatch.setattr("igsupload.workflow.put_chunks", lambda path, size, urls, uid: {"uploadId": "up_id", "completedChunks": []})
    monkeypatch.setattr("igsupload.workflow.post_upload_body", lambda docid, body, token: None)
    monkeypatch.setattr("igsupload.workflow.start_validation", lambda docid, token: None)
    monkeypatch.setattr("igsupload.workflow.poll_validation_status", lambda docid, token: "VALID")
    def fail_notify(*a, **kw): raise Exception("something unexpected")
    monkeypatch.setattr("igsupload.workflow.send_notification", fail_notify)
    with mock.patch("igsupload.workflow.typer.secho") as mock_secho:
        start("dummy.csv")
        texts = get_secho_texts(mock_secho)
        assert any("Unexpected error" in t for t in texts)

def test_workflow_notification_no_parameter(monkeypatch, workflow_base):
    monkeypatch.setattr("os.path.exists", lambda p: True)
    monkeypatch.setattr("os.path.getsize", lambda p: 100)
    monkeypatch.setattr("igsupload.workflow.create_hash", lambda p: "hash")
    monkeypatch.setattr("igsupload.workflow.build_document_reference", lambda f, h: {"doc": f, "hash": h})
    monkeypatch.setattr("igsupload.workflow.post_document_reference", lambda doc, token: "docid")
    monkeypatch.setattr("igsupload.workflow.get_presigned_url", lambda token, docid, size: ("up_id", ["url1"], 42))
    monkeypatch.setattr("igsupload.workflow.put_chunks", lambda path, size, urls, uid: {"uploadId": "up_id", "completedChunks": []})
    monkeypatch.setattr("igsupload.workflow.post_upload_body", lambda docid, body, token: None)
    monkeypatch.setattr("igsupload.workflow.start_validation", lambda docid, token: None)
    monkeypatch.setattr("igsupload.workflow.poll_validation_status", lambda docid, token: "VALID")
    monkeypatch.setattr("igsupload.workflow.send_notification", lambda fn, docid, labid: {})
    with mock.patch("igsupload.workflow.typer.secho"), mock.patch("igsupload.workflow.typer.echo"):
        start("dummy.csv")

def test_workflow_continue_branch(monkeypatch, workflow_base):
    monkeypatch.setattr("igsupload.workflow.read_csv", lambda csv_path: [
        {"FILE_1_NAME": "", "FILE_2_NAME": "", "SEQUENCING_LAB.DEMIS_LAB_ID": "labid"},
        {"SEQUENCING_LAB.DEMIS_LAB_ID": "labid"}, 
    ])
    monkeypatch.setattr("os.path.abspath", lambda p: "/abs/" + p)
    monkeypatch.setattr("os.path.dirname", lambda p: "dir")
    monkeypatch.setattr("os.path.join", os.path.join)
    with mock.patch("igsupload.workflow.typer.secho"), mock.patch("igsupload.workflow.typer.echo"):
        start("dummy.csv")

