import requests
import typer

import igsupload.config as config
from igsupload.fhir_response import parse_fhir_response, report_fhir_error


def post_upload_body(doc_id, complete_upload_body, token):
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{config.BASE_URL}/S3Controller/upload/{doc_id}/$finish-upload",
            headers=headers,
            json=complete_upload_body,
            cert=(config.CERT, config.KEY),
        )

        if response.status_code == 204:
            msg = f"Upload was {typer.style('successful', fg=typer.colors.GREEN)}."
            print(msg)
            return True

        msg = (
            f"{typer.style('Fehler', fg=typer.colors.RED)} beim Upload: "
            f"{response.status_code}"
        )
        print(msg)

        report_fhir_error(
            parse_fhir_response(response),
            resource="DocumentReference upload",
        )

        return False

    except requests.exceptions.SSLError as ssl_err:
        msg = (
            f"{typer.style('SSL-Error', fg=typer.colors.RED)} "
            "(wrong certificate?):"
        )
        print(msg)
        print(ssl_err)
        return False

    except requests.exceptions.RequestException as error:
        msg = (
            f"{typer.style('Network-/Connectionerror', fg=typer.colors.RED)}:"
        )
        print(msg)
        print(error)
        return False
