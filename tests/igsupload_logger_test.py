import os
import csv
import tempfile
from igsupload import igsupload_logger

def test_log_to_csv_creates_and_writes_file():
    # Verwendet ein temporäres Verzeichnis, so wird kein echter Logger-Ordner angelegt
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test_log.csv")
        igsupload_logger.log_to_csv(
            filename="test.fq",
            notification_id="n1",
            transaction_id="t1",
            lab_sequence_id="l1",
            document_reference_id="d1",
            status="OK",
            csv_path=csv_path
        )
        assert os.path.exists(csv_path)
        with open(csv_path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["filename"] == "test.fq"
        assert rows[0]["notification_id"] == "n1"
        assert rows[0]["transaction_id"] == "t1"
        assert rows[0]["lab_sequence_id"] == "l1"
        assert rows[0]["document_reference_id"] == "d1"
        assert rows[0]["status"] == "OK"
        assert "timestamp" in rows[0]

def test_log_to_csv_appends_multiple_rows():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test_log.csv")
        # Erster Eintrag
        igsupload_logger.log_to_csv(
            filename="one.fq",
            notification_id="id1",
            transaction_id="tr1",
            lab_sequence_id="lab1",
            document_reference_id="doc1",
            status="OK",
            csv_path=csv_path
        )
        # Zweiter Eintrag
        igsupload_logger.log_to_csv(
            filename="two.fq",
            notification_id="id2",
            transaction_id="tr2",
            lab_sequence_id="lab2",
            document_reference_id="doc2",
            status="FAILED",
            csv_path=csv_path
        )
        with open(csv_path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["filename"] == "one.fq"
        assert rows[1]["filename"] == "two.fq"
        assert rows[1]["status"] == "FAILED"

def test_log_to_csv_with_extra_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test_log.csv")
        igsupload_logger.log_to_csv(
            filename="extra.fq",
            notification_id="nid",
            transaction_id="tid",
            lab_sequence_id="lid",
            document_reference_id="did",
            status="OK",
            extra_fields={"custom_field": "myvalue", "another": "ok"},
            csv_path=csv_path
        )
        with open(csv_path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["custom_field"] == "myvalue"
        assert rows[0]["another"] == "ok"

def test_extract_param_value_found():
    params = [
        {"name": "foo", "valueIdentifier": {"value": "bar"}},
        {"name": "id", "valueIdentifier": {"value": "abc123"}}
    ]
    result = igsupload_logger.extract_param(params, "id")
    assert result == "abc123"

def test_extract_param_not_found():
    params = [{"name": "notid", "valueIdentifier": {"value": "nope"}}]
    assert igsupload_logger.extract_param(params, "doesnotexist") is None

def test_extract_param_value_identifier_missing():
    params = [{"name": "id"}]
    assert igsupload_logger.extract_param(params, "id") is None
    params = [{"name": "id", "valueIdentifier": {}}]
    assert igsupload_logger.extract_param(params, "id") is None

def test_extract_param_value_identifier_wrong_type():
    params = [{"name": "id", "valueIdentifier": {"something": "not_value"}}]
    assert igsupload_logger.extract_param(params, "id") is None

def test_log_to_csv_default_path(tmp_path):
    # Modul-Global auf tmp_path setzen, weil es beim Import gecached wurde
    igsupload_logger.logging_path = str(tmp_path)

    igsupload_logger.log_to_csv(
        filename="no_path.fq",
        notification_id="nid",
        transaction_id="tid",
        lab_sequence_id="lid",
        document_reference_id="did",
        status="OK",
        csv_path=None
    )
    default_path = os.path.join(str(tmp_path), "logging", "igsupload_log.csv")
    assert os.path.exists(default_path)
    with open(default_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["filename"] == "no_path.fq"
    assert rows[0]["status"] == "OK"

