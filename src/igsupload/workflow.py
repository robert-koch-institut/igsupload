import os
import time
import threading
import uuid
import typer

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
    doc_ids = []
    for row in rows:
        for file_num in (1,2):
            file_name = getattr(row, f"FILE_{file_num}_NAME")

            if not file_name:
                continue

            file_path = os.path.abspath(
                os.path.join(os.path.dirname(csv_path), "..", "reads", file_name)
            )
            typer.echo(f"Processing file: {file_name}")

            if not os.path.exists(file_path):
                typer.secho(f"File not found: {file_path}", fg=typer.colors.RED)
                continue

            # SHA-256 Hash
            hash_value = create_hash(file_path)

            # create and post DocumentReference
            doc_ref = build_document_reference(file_name, hash_value)
            doc_id = post_document_reference(doc_ref, token_module.current_token)
            doc_ids += [doc_id]
            if not doc_id:
                typer.secho(f"Failed to create DocumentReference for {file_name}", fg=typer.colors.RED)
                continue

            # upload chunks
            size = os.path.getsize(file_path)
            upload_id, urls, part_size = get_presigned_url(
                token_module.current_token, doc_id, size
            )
            complete_body = put_chunks(file_path, part_size, urls, upload_id)
            post_upload_body(doc_id, complete_body, token_module.current_token)

            # validation of files
            start_validation(doc_id, token_module.current_token)
            status = poll_validation_status(doc_id, token_module.current_token)
            if status != "VALID":
                typer.secho(f"Validation failed for {file_name}", fg=typer.colors.RED)
                continue

        try:
            result = send_notification(row, doc_ids)
            typer.secho(f"Notification for {file_name} sent successfully.", fg=typer.colors.GREEN)
            typer.echo("Server response:")
            typer.echo(result)

            if isinstance(result, dict) and "parameter" in result:
                typer.secho("Logging the Results...", fg=typer.colors.GREEN)
                notification_id = extract_param(result["parameter"], "submitterGeneratedNotificationID")
                transaction_id = extract_param(result["parameter"], "transactionID")
                lab_sequence_id = extract_param(result["parameter"], "labSequenceID")

                log_to_csv(
                    filename=file_name,
                    notification_id=notification_id or "",
                    transaction_id=transaction_id or "",
                    lab_sequence_id=lab_sequence_id or "",
                    document_reference_id=doc_ids,
                    status="OK"
                )

        except Exception as e:
            if hasattr(e, 'response') and e.response is not None:
                resp = e.response
                typer.secho(f"Error {resp.status_code} sending notification for {file_name}", fg=typer.colors.RED)
                try:
                    typer.echo(resp.json())
                except ValueError:
                    typer.echo(resp.text)
            else:
                typer.secho(f"Unexpected error for {file_name}: {e}", fg=typer.colors.RED)
