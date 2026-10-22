import datetime
import csv
import os

from pathlib import Path

class UploadReport:
    def __init__(self, report_path: Path):
        self.report_path = report_path


    def create_report(
        self,
        filename: str,
        notification_id: str,
        transaction_id: str,
        lab_sequence_id: str,
        document_reference_id: str,
        status: str,
        extra_fields: dict = None,
    ):
        fieldnames = [
            'timestamp',
            'filename',
            'notification_id',
            'transaction_id',
            'lab_sequence_id',
            'document_reference_id',
            'status',
        ]
        if extra_fields:
            fieldnames += list(extra_fields.keys())

        file_path = Path(self.report_path / "igsupload_log.csv")
        file_exists = os.path.isfile(file_path)

        with open(file_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            row = {
                'timestamp': datetime.datetime.now().isoformat(),
                'filename': filename,
                'notification_id': notification_id,
                'transaction_id': transaction_id,
                'lab_sequence_id': lab_sequence_id,
                'document_reference_id': document_reference_id,
                'status': status,
            }
            if extra_fields:
                row.update(extra_fields)
            writer.writerow(row)
