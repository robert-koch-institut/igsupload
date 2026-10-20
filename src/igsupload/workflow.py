import os
import time
import threading
import uuid
import typer
import json
import requests

from igsupload.api.client import ApiClient
from igsupload.utils.extract_csv import read_csv
from igsupload.builders.document_reference import build_document_reference
from igsupload.utils.sha256_hash import create_hash
from igsupload.builders.igs_notification import send_notification
from igsupload.log.igsupload_logger import log_to_csv, extract_param
from igsupload.builders.fhir_response import parse_fhir_response, report_fhir_error
from igsupload.builders.fhir_constants import NOTIFICATION_BUNDLE_PROFILE


def start(csv_path: str, fhir_base_url:str, api: ApiClient):
    """
    Haupt-Workflow: CSV einlesen, jede Datei verarbeiten, validieren
    und anschließend eine Sequenzmeldung senden und loggen.
    """

    rows = read_csv(csv_path)
    for row in rows:
        doc_ids = []
        file_names = []
        all_files_valid = True

        for file_num in (1,2):
            file_name = getattr(row, f"FILE_{file_num}_NAME")

            if not file_name:
                if file_num == 1:
                    typer.secho(
                        "Missing required sequence file: FILE_1_NAME",
                        fg=typer.colors.RED,
                    )
                    all_files_valid = False
                continue

            file_names.append(file_name)

            file_path = os.path.abspath(
                os.path.join(os.path.dirname(csv_path), "..", "reads", file_name)
            )
            typer.echo(f"Processing file: {file_name}")

            if not os.path.exists(file_path):
                typer.secho(f"File not found: {file_path}", fg=typer.colors.RED)
                all_files_valid = False
                continue

            hash_value = create_hash(file_path) # SHA-256 Hash

            # ------- create and post doc ref
            doc_ref = build_document_reference(file_name, hash_value)
            doc_id = api.post_doc_ref(doc_ref)
            if not doc_id:
                typer.secho(f"Failed to create DocumentReference for {file_name}", fg=typer.colors.RED)
                all_files_valid = False
                continue

            # ------- presigned urls from S3
            size = os.path.getsize(file_path)
            upload_info = api.get_presigned_url(doc_id, size)
            if not upload_info:
                typer.secho(
                    f"Failed to get upload information for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            # ToDo: wie ist der normale Umgang mit solchen variablen? oben oder hier definieren oder sogar die Datei unterteilen usw.
            upload_id: str = upload_info["uploadId"]
            urls: list[str] = upload_info["presignedUrls"]
            part_size: int = upload_info["partSizeBytes"]

            if not upload_id or not urls or not part_size:
                typer.secho(
                    f"Incomplete upload information for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            # ------- file chunks upload
            complete_body = api.put_file_chunks(file_path, part_size, urls, upload_id)
            completed_chunks = (
                complete_body.get("completedChunks", []) if complete_body else []
            )
            chunks_complete = (
                len(completed_chunks) == len(urls)
                and all(chunk.get("eTag") for chunk in completed_chunks)
            )
            if not chunks_complete:
                typer.secho(
                    f"Chunk upload incomplete for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            # ------- final upload to S3
            upload_finished = api.post_finish_upload(doc_id, complete_body)
            if upload_finished.status_code != 204:
                typer.secho(
                    f"Failed to finish upload for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            # ------- start validation of files
            validation_started = api.post_start_validation(doc_id)
            if not validation_started:
                typer.secho(
                    f"Failed to start validation for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            val_status = wait_for_validation(api, doc_id)

            if val_status["status"] != "VALID":
                typer.secho(
                    f"Validation failed for {file_name}: {val_status}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            doc_ids.append(doc_id)

        if not all_files_valid or not 1 <= len(doc_ids) <= 2:
            typer.secho(
                "Notification not sent: one or two sequence files must "
                "complete validation with status VALID.",
                fg=typer.colors.RED,
            )
            continue

        notification_label = " and ".join(file_names)

         # ------- post final notification
        try:
            result = send_notification(api, fhir_base_url, row, doc_ids)

            if result.status_code != 200:
                report_fhir_error(
                    result.json(),
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                )
                continue

            typer.secho(
                f"Notification for {notification_label} sent successfully.",
                fg=typer.colors.GREEN,
            )

            response_body = result.json()
            if isinstance(response_body, dict) and "parameter" in response_body:
                typer.secho("Logging the Results...", fg=typer.colors.GREEN)
                parameters = response_body["parameter"]
                notification_id = extract_param(parameters, "submitterGeneratedNotificationID")
                transaction_id = extract_param(parameters, "transactionID")
                lab_sequence_id = extract_param(parameters, "labSequenceID")

                log_to_csv(
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
                typer.secho(f"Error {resp.status_code} sending notification for {notification_label}", fg=typer.colors.RED)
                report_fhir_error(
                    parse_fhir_response(resp),
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                )
            else:
                typer.secho(
                    f"Unexpected error for {notification_label}: "
                    f"{(str(e))}",
                    fg=typer.colors.RED,
                )



def wait_for_validation(api: ApiClient, doc_id: str, max_wait_seconds: int = 300) -> dict:

    deadline = time.monotonic() + max_wait_seconds

    while time.monotonic() < deadline:
        result = api.get_validation_status(doc_id)

        if result["done"] is True:
            return result

    raise TimeoutError(
        f"Validation timed out for document {doc_id}"
    )