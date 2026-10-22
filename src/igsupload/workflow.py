import os
import time
import logging
import typer

from pathlib import Path

from igsupload.api.client import ApiClient
from igsupload.utils.extract_csv import read_csv
from igsupload.builders.document_reference import build_document_reference
from igsupload.utils.sha256_hash import create_hash
from igsupload.utils.demis_response import extract_param
from igsupload.builders.igs_notification import send_notification
from igsupload.log.upload_report import UploadReport
from igsupload.builders.fhir_response import parse_fhir_response, report_fhir_error
from igsupload.builders.fhir_constants import NOTIFICATION_BUNDLE_PROFILE


logger = logging.getLogger(__name__)

def start(csv_path: Path, fhir_base_url:str, api: ApiClient, report: UploadReport):
    """
    Haupt-Workflow: CSV einlesen, jede Datei verarbeiten, validieren,
    anschließend eine Sequenzmeldung senden und loggen.
    """

    rows = read_csv(csv_path)
    for row in rows:
        doc_ids = []
        file_names = []
        all_files_valid = True

        for file_num in (1,2):
            file_name = getattr(row, f"FILE_{file_num}_NAME", None)

            if not file_name:
                if file_num == 1:
                    logger.error("Missing required sequence file")
                    all_files_valid = False
                continue

            file_names.append(file_name)

            file_path = os.path.abspath(
                os.path.join(os.path.dirname(csv_path), "..", "reads", file_name)
            )
            logger.info(f"Processing file: {file_name}")

            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                all_files_valid = False
                continue
            logger.debug(f"file found in Path: {file_path}")

            hash_value = create_hash(file_path) # SHA-256 Hash

            # ------- create and post doc ref
            doc_ref = build_document_reference(file_name, hash_value)
            if not doc_ref:
                logger.error(f"Failed to create DocumentReference for {file_name}")
                all_files_valid = False
                continue
            logger.info(f"DocumentReference created for {file_name}")
            
            doc_id = api.post_doc_ref(doc_ref)
            if not doc_id:
                logger.error(f"Failed to post DocumentReference for {file_name}")
                all_files_valid = False
                continue
            logger.info("DocumentReference was sent successfully", extra={"color": "green"})
            logger.debug(f"DocumentReferenceID: {doc_id}")

            # ------- presigned urls from S3
            size = os.path.getsize(file_path)
            logger.info(f"Fetching upload information for {file_name}")
            upload_info = api.get_presigned_url(doc_id, size)
            if not upload_info:
                logger.error(f"Failed to get upload information for {file_name}")
                all_files_valid = False
                continue

            upload_id: str = upload_info["uploadId"]
            urls: list[str] = upload_info["presignedUrls"]
            part_size: int = upload_info["partSizeBytes"]

            if not upload_id or not urls or not part_size:
                logger.error(f"Incomplete upload information for {file_name}")
                all_files_valid = False
                continue

            # ------- file chunks upload
            logger.info(f"Starting to upload {file_name} in chunks to fetched Presigned URLs")
            complete_body = api.put_file_chunks(file_path, part_size, urls, upload_id)
            completed_chunks = (
                complete_body.get("completedChunks", []) if complete_body else []
            )
            chunks_complete = (
                len(completed_chunks) == len(urls)
                and all(chunk.get("eTag") for chunk in completed_chunks)
            )
            if not chunks_complete:
                logger.error(f"Chunk upload incomplete for {file_name}")
                all_files_valid = False
                continue

            # ------- final upload to S3
            upload_finished = api.post_finish_upload(doc_id, complete_body)
            if upload_finished.status_code != 204:
                logger.error(f"Failed to finish upload for {file_name}")
                all_files_valid = False
                continue
            logger.info("Finished upload to S3", extra={"color": "green"})
            logger.debug(f"for DocumentReference ID: {doc_id}")

            # ------- start validation of files
            logger.info("Started Validation of Sequencing Files...")
            validation_started = api.post_start_validation(doc_id)
            if not validation_started:
                logger.error(f"Failed to start validation for {file_name}")
                all_files_valid = False
                continue

            val_status = wait_for_validation(api, doc_id)

            if val_status["status"] != "VALID":
                logger.error(f"Validation failed for {file_name}: {val_status}")
                all_files_valid = False
                continue
            logger.info("Validation was successfull", extra={"color": "green"})

            doc_ids.append(doc_id)

        if not all_files_valid or not 1 <= len(doc_ids) <= 2:
            logger.error("Notification not sent: one or two sequence files must complete validation with status VALID.")
            continue

        notification_label = " and ".join(file_names)

         # ------- post final notification
        try:
            logger.info("Building final IGS-Bundle...")
            result = send_notification(api, fhir_base_url, row, doc_ids)

            if result.status_code != 200:
                report_fhir_error(
                    result.json(),
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                )
                continue

            logger.info(
                f"Notification for {notification_label} sent successfully.", 
                extra={"color": "green"},
            )

            response_body = result.json()
            if isinstance(response_body, dict) and "parameter" in response_body:
                logger.info("Creating final report")
                parameters = response_body["parameter"]
                notification_id = extract_param(parameters, "submitterGeneratedNotificationID")
                transaction_id = extract_param(parameters, "transactionID")
                lab_sequence_id = extract_param(parameters, "labSequenceID")

                report.create_report(
                    filename=notification_label,
                    notification_id=notification_id or "",
                    transaction_id=transaction_id or "",
                    lab_sequence_id=lab_sequence_id or "",
                    document_reference_id=doc_ids,
                    status="OK"
                )

        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                resp = e.response
                logger.error(f"Error {resp.status_code} sending notification for {notification_label}")
                report_fhir_error(
                    parse_fhir_response(resp),
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                )
            else:
                logger.error(f"Unexpected error for {notification_label}: {(str(e))}")



def wait_for_validation(api: ApiClient, doc_id: str, max_wait_seconds: int = 300) -> dict:
    deadline = time.monotonic() + max_wait_seconds
    start_time = time.time()

    while time.monotonic() < deadline:
        result = api.get_validation_status(doc_id)
        current_time = time.time()
        logger.info(f"Validation Status: {result.get("status")}, {current_time-start_time:.2f} seconds passed")

        if result.get("done") is True:
            return result

    raise TimeoutError(
        f"Validation timed out for document {doc_id}"
    )