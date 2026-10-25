import csv
import json

from igsupload.log.upload_report import UploadReport


def read_report(report: UploadReport) -> list[dict[str, str]]:
    with report.file_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_report_updates_existing_row(tmp_path):
    source_csv = tmp_path / "metadata.csv"
    source_csv.write_text("FILE_1_NAME\nsample.fastq\n", encoding="utf-8")

    report = UploadReport(
        report_path=tmp_path,
        source_csv=source_csv,
    )
    report.initialize_rows([
        (1, ["sample_R1.fastq", "sample_R2.fastq"]),
        (2, ["sample_2.fastq"]),
    ])

    report.start_row(1)
    report.update_row(
        row_number=1,
        stage="DOCUMENT_REFERENCE",
        document_reference_ids=["doc-1", "doc-2"],
        message="DocumentReferences created",
    )
    report.finish_row(
        row_number=1,
        status="SUCCESS",
        message="Completed",
    )

    rows = read_report(report)

    assert len(rows) == 2
    assert rows[0]["status"] == "SUCCESS"
    assert rows[0]["stage"] == "DONE"
    assert rows[0]["duration_seconds"] != ""
    assert rows[1]["status"] == "PENDING"
    assert json.loads(rows[0]["document_reference_ids"]) == [
        "doc-1",
        "doc-2",
    ]


def test_report_is_saved_after_an_intermediate_update(tmp_path):
    source_csv = tmp_path / "metadata.csv"
    source_csv.write_text("FILE_1_NAME\nsample.fastq\n", encoding="utf-8")

    report = UploadReport(
        report_path=tmp_path,
        source_csv=source_csv,
    )
    report.initialize_rows([(1, ["sample.fastq"])])
    report.start_row(1)
    report.update_row(
        row_number=1,
        stage="UPLOAD",
        sha256_values=["abc123"],
        document_reference_ids=["doc-1"],
        upload_ids=["upload-1"],
        message="Uploading sample.fastq",
    )

    rows = read_report(report)

    assert rows[0]["status"] == "IN_PROGRESS"
    assert rows[0]["stage"] == "UPLOAD"
    assert json.loads(rows[0]["sha256_values"]) == ["abc123"]
    assert json.loads(rows[0]["upload_ids"]) == ["upload-1"]
    assert not report.file_path.with_suffix(".tmp").exists()
