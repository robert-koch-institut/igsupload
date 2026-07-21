import os
import time
import threading
import uuid
import typer
import json
import requests

import igsupload.get_token as token_module
from igsupload.extract_csv import read_csv
from igsupload.document_reference import build_document_reference
from igsupload.sha256_hash import create_hash
from igsupload.post_document_reference import post_document_reference
from igsupload.get_presigned_url import get_presigned_url
from igsupload.upload_chunks import put_chunks
from igsupload.finish_upload import post_upload_body
from igsupload.start_validation import start_validation
from igsupload.long_polling_val import poll_validation_status
from igsupload.igs_notification import send_notification
from igsupload.igsupload_logger import log_to_csv, extract_param
from igsupload.fhir_response import parse_fhir_response, report_fhir_error
from igsupload.redaction import redact_text
from igsupload.fhir_constants import NOTIFICATION_BUNDLE_PROFILE


def start(csv_path: str):
    """
    Haupt-Workflow: CSV einlesen, jede Datei verarbeiten, validieren
    und anschließend eine Sequenzmeldung senden und loggen.
    """
    # Token im Hintergrund regelmäßig aktualisieren
    token_thread = threading.Thread(target=token_module.update_token, daemon=True)
    token_thread.start()
    time.sleep(2)

    rows = read_csv(csv_path)
    for row in rows:
        doc_ids = []
        file_names = []
        all_files_valid = True

        for file_num in (1,2):
            file_name = getattr(row, f"FILE_{file_num}_NAME")

            if not file_name:
                typer.secho(
                    f"Missing required sequence file: FILE_{file_num}_NAME",
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

            # SHA-256 Hash
            hash_value = create_hash(file_path)

            # create and post DocumentReference
            doc_ref = build_document_reference(file_name, hash_value)
            doc_id = post_document_reference(doc_ref, token_module.current_token)
            if not doc_id:
                typer.secho(f"Failed to create DocumentReference for {file_name}", fg=typer.colors.RED)
                all_files_valid = False
                continue

            # upload chunks
            size = os.path.getsize(file_path)
            upload_info = get_presigned_url(
                token_module.current_token, doc_id, size
            )
            if not upload_info:
                typer.secho(
                    f"Failed to get upload information for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            upload_id, urls, part_size = upload_info
            if not upload_id or not urls or not part_size:
                typer.secho(
                    f"Incomplete upload information for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            complete_body = put_chunks(file_path, part_size, urls, upload_id)
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

            upload_finished = post_upload_body(
                doc_id,
                complete_body,
                token_module.current_token,
            )
            if not upload_finished:
                typer.secho(
                    f"Failed to finish upload for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            # validation of files
            validation_started = start_validation(
                doc_id,
                token_module.current_token,
            )
            if not validation_started:
                typer.secho(
                    f"Failed to start validation for {file_name}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            status = poll_validation_status(doc_id, token_module.current_token)
            if status != "VALID":
                typer.secho(
                    f"Validation failed for {file_name}: {status}",
                    fg=typer.colors.RED,
                )
                all_files_valid = False
                continue

            doc_ids.append(doc_id)

        if not all_files_valid or len(doc_ids) != 2:
            typer.secho(
                "Notification not sent: both sequence files must complete "
                "validation with status VALID.",
                fg=typer.colors.RED,
            )
            continue

        notification_label = " and ".join(file_names)

        try:
            result = send_notification(row, doc_ids)
            parsed_response = parse_fhir_response(result)
            if result.status_code != 200:
                report_fhir_error(
                    parsed_response,
                    resource="Notification Bundle",
                    expected_profile=NOTIFICATION_BUNDLE_PROFILE,
                    output=typer.echo,
                )
                continue

            typer.secho(
                f"Notification for {notification_label} sent successfully.",
                fg=typer.colors.GREEN,
            )

            response_body = parsed_response.payload
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
                    f"{redact_text(str(e))}",
                    fg=typer.colors.RED,
                )
