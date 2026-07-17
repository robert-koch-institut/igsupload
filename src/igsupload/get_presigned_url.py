import requests
import typer

import igsupload.config as config
from igsupload.fhir_response import parse_fhir_response, report_fhir_error


def get_presigned_url(token, doc_id, file_in_bytes):
    try:
        params = {"fileSize": file_in_bytes}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/fhir+json",
        }
        response = requests.get(
            f"{config.BASE_URL}/S3Controller/upload/{doc_id}/s3-upload-info",
            headers=headers,
            params=params,
            cert=(config.CERT, config.KEY),
        )

        if response.status_code == 200:
            result = response.json()
            print(
                f"GET request "
                f"{typer.style('successful', fg=typer.colors.GREEN)}"
            )
            return (
                result.get("uploadId"),
                result.get("presignedUrls"),
                result.get("partSizeBytes"),
            )

        print(
            f"{typer.style('Error', fg=typer.colors.RED)} during upload: "
            f"{response.status_code}"
        )
        report_fhir_error(
            parse_fhir_response(response),
            resource="DocumentReference upload information",
        )
        return None

    except requests.exceptions.SSLError as ssl_err:
        msg = (
            f"{typer.style('SSL-Error', fg=typer.colors.RED)} "
            "(wrong certificate?):"
        )
        print(msg)
        print(ssl_err)

    except requests.exceptions.RequestException as error:
        msg = (
            f"{typer.style('Network-/Connectionerror', fg=typer.colors.RED)}:"
        )
        print(msg)
        print(error)

    return None
