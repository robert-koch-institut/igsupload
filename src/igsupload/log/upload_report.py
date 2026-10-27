import csv
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPORT_FIELDS = [
    "timestamp_utc",
    "run_id",
    "source_csv",
    "metadata_row",
    "stage",
    "status",
    "filenames",
    "sha256_values",
    "document_reference_ids",
    "upload_ids",
    "validation_statuses",
    "notification_id",
    "transaction_id",
    "lab_sequence_id",
    "duration_seconds",
    "error_type",
    "message",
]

LIST_FIELDS = {
    "filenames",
    "sha256_values",
    "document_reference_ids",
    "upload_ids",
    "validation_statuses",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class UploadReport:
    def __init__(self, report_path: Path, source_csv: Path):
        self.report_path = report_path
        self.report_path.mkdir(parents=True, exist_ok=True)
        self.file_path = report_path / "igsupload_report.csv"
        self.run_id = str(uuid.uuid4())
        self.source_csv = str(source_csv.resolve())

        self.rows: dict[int, dict] = {}
        self.started_at: dict[int, float] = {}

    def initialize_rows(
        self,
        metadata_rows: list[tuple[int, list[str]]],
    ) -> None:
        for row_number, filenames in metadata_rows:
            row = {field: "" for field in REPORT_FIELDS}

            for field in LIST_FIELDS:
                row[field] = []

            row["timestamp_utc"] = utc_now()
            row["run_id"] = self.run_id
            row["source_csv"] = self.source_csv
            row["metadata_row"] = row_number
            row["stage"] = "METADATA"
            row["status"] = "PENDING"
            row["filenames"] = list(filenames)
            row["message"] = "Waiting for processing"

            self.rows[row_number] = row

        self._write()

    def start_row(self, row_number: int) -> None:
        self.started_at[row_number] = time.monotonic()
        self.update_row(
            row_number=row_number,
            stage="METADATA",
            status="IN_PROGRESS",
            message="Processing started",
        )

    def update_row(
        self,
        row_number: int,
        stage: str | None = None,
        status: str | None = None,
        filenames: list[str] | None = None,
        sha256_values: list[str] | None = None,
        document_reference_ids: list[str] | None = None,
        upload_ids: list[str] | None = None,
        validation_statuses: list[str] | None = None,
        notification_id: str | None = None,
        transaction_id: str | None = None,
        lab_sequence_id: str | None = None,
        duration_seconds: float | str | None = None,
        error_type: str | None = None,
        message: str | None = None,
    ) -> None:
        if row_number not in self.rows:
            raise KeyError(f"Unknown metadata row: {row_number}")

        row = self.rows[row_number]

        values_to_update = {
            "stage": stage,
            "status": status,
            "filenames": filenames,
            "sha256_values": sha256_values,
            "document_reference_ids": document_reference_ids,
            "upload_ids": upload_ids,
            "validation_statuses": validation_statuses,
            "notification_id": notification_id,
            "transaction_id": transaction_id,
            "lab_sequence_id": lab_sequence_id,
            "duration_seconds": duration_seconds,
            "error_type": error_type,
            "message": message,
        }

        for field_name, value in values_to_update.items():
            if value is None:
                continue

            if field_name in LIST_FIELDS:
                row[field_name] = list(value)
            else:
                row[field_name] = value

        row["timestamp_utc"] = utc_now()
        self._write()

    def finish_row(
        self,
        row_number: int,
        status: str,
        message: str,
        error_type: str = "",
        stage: str | None = None,
        filenames: list[str] | None = None,
        sha256_values: list[str] | None = None,
        document_reference_ids: list[str] | None = None,
        upload_ids: list[str] | None = None,
        validation_statuses: list[str] | None = None,
        notification_id: str | None = None,
        transaction_id: str | None = None,
        lab_sequence_id: str | None = None,
    ) -> None:
        started = self.started_at.get(row_number)
        duration_seconds: float | str = ""

        if started is not None:
            duration_seconds = round(time.monotonic() - started, 2)

        final_stage = stage
        if status == "SUCCESS":
            final_stage = "DONE"

        self.update_row(
            row_number=row_number,
            stage=final_stage,
            status=status,
            filenames=filenames,
            sha256_values=sha256_values,
            document_reference_ids=document_reference_ids,
            upload_ids=upload_ids,
            validation_statuses=validation_statuses,
            notification_id=notification_id,
            transaction_id=transaction_id,
            lab_sequence_id=lab_sequence_id,
            duration_seconds=duration_seconds,
            error_type=error_type,
            message=message,
        )

    def _write(self) -> None:
        temporary_path = self.file_path.with_suffix(".tmp")

        with temporary_path.open(
            mode="w",
            newline="",
            encoding="utf-8",
        ) as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=REPORT_FIELDS)
            writer.writeheader()

            for row_number in sorted(self.rows):
                row = self.rows[row_number].copy()

                for field in LIST_FIELDS:
                    row[field] = json.dumps(row[field], ensure_ascii=False)

                writer.writerow(row)

        temporary_path.replace(self.file_path)
