import csv
import json

from igsupload.log.upload_report import UploadReport


def read_rows(report):
    with report.file_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_report_keeps_one_row_and_persists_intermediate_state(tmp_path):
    source_csv = tmp_path / "metadata.csv"
    source_csv.write_text("FILE_1_NAME\n", encoding="utf-8")
    report = UploadReport(tmp_path / "logs", source_csv)
    report.initialize_rows([(1, ["sample.fq.gz"])])
    report.start_row(1)
    report.update_row(
        1,
        stage="VALIDATION",
        document_reference_ids=["doc-1"],
        validation_statuses=["VALIDATING"],
    )

    rows = read_rows(report)

    assert len(rows) == 1
    assert rows[0]["status"] == "IN_PROGRESS"
    assert rows[0]["stage"] == "VALIDATION"
    assert json.loads(rows[0]["filenames"]) == ["sample.fq.gz"]
    assert json.loads(rows[0]["document_reference_ids"]) == ["doc-1"]
    assert json.loads(rows[0]["validation_statuses"]) == ["VALIDATING"]


def test_finish_row_records_final_result_and_duration(tmp_path, monkeypatch):
    source_csv = tmp_path / "metadata.csv"
    source_csv.write_text("FILE_1_NAME\n", encoding="utf-8")
    report = UploadReport(tmp_path / "logs", source_csv)
    report.initialize_rows([(1, ["sample.fastq"])])

    times = iter([10.0, 12.345])
    monkeypatch.setattr("igsupload.log.upload_report.time.monotonic", lambda: next(times))
    report.start_row(1)
    report.finish_row(1, status="SUCCESS", message="done")

    row = read_rows(report)[0]

    assert row["status"] == "SUCCESS"
    assert row["stage"] == "DONE"
    assert row["duration_seconds"] == "2.35"
    assert row["message"] == "done"
