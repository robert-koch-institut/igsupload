import logging
import os
import time
from pathlib import Path

import typer

from igsupload.api.client import ApiClient
from igsupload.builders.document_reference import build_document_reference
from igsupload.builders.fhir_constants import NOTIFICATION_BUNDLE_PROFILE
from igsupload.builders.fhir_response import parse_fhir_response, report_fhir_error
from igsupload.builders.igs_notification import send_notification
from igsupload.log.upload_report import UploadReport
from igsupload.utils.demis_response import extract_param
from igsupload.utils.extract_csv import read_csv
from igsupload.utils.sha256_hash import create_hash

logger = logging.getLogger(__name__)

def start(
    csv_path: Path,
    fhir_base_url: str,
    api: ApiClient,
    report: UploadReport,
) -> bool:
    """
    Haupt-Workflow: CSV einlesen, jede Datei verarbeiten, validieren,
    anschließend eine Sequenzmeldung senden und loggen.
    """

    rows = read_csv(csv_path)
    report_rows = []

    # init igsupload report
    for row_number, row in enumerate(rows, start=1):
        filenames = []
        if row.FILE_1_NAME:
            filenames.append(row.FILE_1_NAME)
        if row.FILE_2_NAME:
            filenames.append(row.FILE_2_NAME)

        report_rows.append((row_number, filenames))

    report.initialize_rows(report_rows)

    if not rows:
        logger.error("The metadata CSV contains no data rows")
        return False

    run_successful = True

    # start of actual workflow
    for row_number, row in enumerate(rows, start=1):
        requested_filenames = []
        if row.FILE_1_NAME:
            requested_filenames.append(row.FILE_1_NAME)
        if row.FILE_2_NAME:
            requested_filenames.append(row.FILE_2_NAME)

        sha256_values = []
        document_reference_ids = []
        upload_ids = []
        validation_statuses = []
        current_stage = "METADATA"

        report.start_row(row_number)

        try:
            if not row.FILE_1_NAME:
                raise ValueError("Missing required sequence file: FILE_1_NAME")

            for file_num in (1, 2):
                file_name = getattr(row, f"FILE_{file_num}_NAME", "")

                if not file_name:
                    continue

                current_stage = "FILE_CHECK"
                report.update_row(
                    row_number=row_number,
                    stage=current_stage,
                    message=f"Checking sequence file {file_name}",
                )

                reads_directory = (
                    csv_path.parent.parent / "reads" 
                ).resolve()

                file_path = ( 
                    reads_directory / file_name 
                ).resolve()

                logger.info(f"Processing file: {file_name}")

                if not file_path.is_relative_to(reads_directory):
                    raise ValueError(
                        f"Sequence file is outside the reads directory: {file_name}"
                    )

                if not file_path.is_file():
                    raise FileNotFoundError(f"Sequence file not found: {file_path}")

                
                current_stage = "HASHING"
                report.update_row(
                    row_number=row_number,
                    stage=current_stage,
                    message=f"Calculating SHA-256 for {file_name}",
                )

                hash_value = create_hash(file_path)
                sha256_values.append(hash_value)
                report.update_row(
                    row_number=row_number,
                    sha256_values=sha256_values,
                    message=f"SHA-256 created for {file_name}",
                )

                current_stage = "DOCUMENT_REFERENCE"
                report.update_row(
                    row_number=row_number,
                    stage=current_stage,
                    message=f"Creating DocumentReference for {file_name}",
                )

                doc_ref = build_document_reference(file_name, hash_value)
                doc_id = api.post_doc_ref(doc_ref)

                if not doc_id:
                    raise RuntimeError(
                        f"DEMIS returned no DocumentReference ID for {file_name}"
                    )

                document_reference_ids.append(doc_id)
                report.update_row(
                    row_number=row_number,
                    document_reference_ids=document_reference_ids,
                    message=f"DocumentReference created for {file_name}",
                )

                current_stage = "UPLOAD"
                report.update_row(
                    row_number=row_number,
                    stage=current_stage,
                    message=f"Fetching upload information for {file_name}",
                )

                size = os.path.getsize(file_path)
                upload_info = api.get_presigned_url(doc_id, size)

                if not isinstance(upload_info, dict):
                    raise TypeError(
                        f"Invalid upload information for {file_name}"
                    )

                upload_id = upload_info.get("uploadId")
                urls = upload_info.get("presignedUrls")
                part_size = upload_info.get("partSizeBytes")

                if not upload_id or not urls or not part_size:
                    raise RuntimeError(
                        f"Incomplete upload information for {file_name}"
                    )

                upload_ids.append(upload_id)
                report.update_row(
                    row_number=row_number,
                    upload_ids=upload_ids,
                    message=f"Uploading {file_name}",
                )

                complete_body = api.put_file_chunks(
                    file_path,
                    part_size,
                    urls,
                    upload_id,
                )
                completed_chunks = (
                    complete_body.get("completedChunks", [])
                    if complete_body
                    else []
                )
                chunks_complete = (
                    len(completed_chunks) == len(urls)
                    and all(chunk.get("eTag") for chunk in completed_chunks)
                )

                if not chunks_complete:
                    raise RuntimeError(f"Chunk upload incomplete for {file_name}")

                upload_finished = api.post_finish_upload(doc_id, complete_body)
                if upload_finished.status_code != 204:
                    raise RuntimeError(f"Failed to finish upload for {file_name}")

                current_stage = "VALIDATION"
                report.update_row(
                    row_number=row_number,
                    stage=current_stage,
                    message=f"Starting validation for {file_name}",
                )
                logger.info(f"Starting validation for {file_name}")

                validation_started = api.post_start_validation(doc_id)
                if not validation_started:
                    raise RuntimeError(
                        f"Failed to start validation for {file_name}"
                    )

                validation_result = wait_for_validation(api, doc_id)
                validation_status = validation_result.get("status", "UNKNOWN")
                validation_statuses.append(validation_status)

                report.update_row(
                    row_number=row_number,
                    validation_statuses=validation_statuses,
                    message=(
                        f"Validation status for {file_name}: "
                        f"{validation_status}"
                    ),
                )

                if validation_status != "VALID":
                    raise ValueError(
                        f"Validation failed for {file_name}: "
                        f"{validation_status}"
                    )

                logger.info(
                    "Validation was successful",
                    extra={"color": "green"},
                )

            if not 1 <= len(document_reference_ids) <= 2:
                raise ValueError(
                    "One or two sequence files must complete validation"
                )

            current_stage = "NOTIFICATION"
            report.update_row(
                row_number=row_number,
                stage=current_stage,
                message="Sending final IGS notification",
            )

            result = send_notification(
                api,
                fhir_base_url,
                row,
                document_reference_ids,
            )

            if result.status_code != 200:
                report_fhir_error(
                    parse_fhir_response(result),
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                    outcome_directory=report.report_path,
                )
                raise RuntimeError(
                    f"Notification failed with HTTP status {result.status_code}"
                )

            try:
                response_body = result.json()
            except ValueError:
                run_successful = False
                report.finish_row(
                    row_number=row_number,
                    status="NEEDS_REVIEW",
                    stage="DONE",
                    message=(
                        "Notification was accepted, but the response was not JSON"
                    ),
                    error_type="InvalidResponse",
                    filenames=requested_filenames,
                    sha256_values=sha256_values,
                    document_reference_ids=document_reference_ids,
                    upload_ids=upload_ids,
                    validation_statuses=validation_statuses,
                )
                continue

            parameters = []
            if isinstance(response_body, dict):
                parameters = response_body.get("parameter", [])

            notification_id = extract_param(
                parameters,
                "submitterGeneratedNotificationID",
            )
            transaction_id = extract_param(parameters, "transactionID")
            lab_sequence_id = extract_param(parameters, "labSequenceID")

            response_ids = {
                "notification_id": notification_id,
                "transaction_id": transaction_id,
                "lab_sequence_id": lab_sequence_id,
            }
            missing_ids = [
                name
                for name, value in response_ids.items()
                if not value
            ]

            if missing_ids:
                run_successful = False
                final_status = "NEEDS_REVIEW"
                final_message = (
                    "Notification was accepted, but response fields are missing: "
                    + ", ".join(missing_ids)
                )
                error_type = "MissingResponseData"
            else:
                final_status = "SUCCESS"
                final_message = "Upload and notification completed successfully"
                error_type = ""

            report.finish_row(
                row_number=row_number,
                status=final_status,
                stage="DONE",
                message=final_message,
                error_type=error_type,
                filenames=requested_filenames,
                sha256_values=sha256_values,
                document_reference_ids=document_reference_ids,
                upload_ids=upload_ids,
                validation_statuses=validation_statuses,
                notification_id=notification_id or "",
                transaction_id=transaction_id or "",
                lab_sequence_id=lab_sequence_id or "",
            )

            if final_status == "SUCCESS":
                logger.info(
                    f"Notification for {' and '.join(requested_filenames)} "
                    "sent successfully.",
                    extra={"color": "green"},
                )

        except Exception as exc: # noqa: BLE001
            run_successful = False
            response = getattr(exc, "response", None)

            if current_stage == "NOTIFICATION" and response is not None:
                report_fhir_error(
                    parse_fhir_response(response),
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                    outcome_directory=report.report_path,
                )

            logger.error(
                "Metadata row %s failed during %s: %s",
                row_number,
                current_stage,
                exc,
            )
            report.finish_row(
                row_number=row_number,
                status="FAILED",
                stage=current_stage,
                message=str(exc),
                error_type=type(exc).__name__,
                filenames=requested_filenames,
                sha256_values=sha256_values,
                document_reference_ids=document_reference_ids,
                upload_ids=upload_ids,
                validation_statuses=validation_statuses,
            )

    return run_successful



def wait_for_validation(api: ApiClient, doc_id: str, max_wait_seconds: int = 300) -> dict:
    deadline = time.monotonic() + max_wait_seconds
    start_time = time.time()

    while time.monotonic() < deadline:
        result = api.get_validation_status(doc_id)
        current_time = time.time()
        logger.info(
            "Validation Status: %s, %.2f seconds passed",
            result.get("status"),
            current_time - start_time,
        )

        if result.get("done") is True:
            return result

        time.sleep(2)

    raise TimeoutError(
        f"Validation timed out for document {doc_id}"
    )
