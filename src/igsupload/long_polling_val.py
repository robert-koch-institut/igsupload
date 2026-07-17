import time

import requests
import typer

import igsupload.config as config
from igsupload.fhir_response import parse_fhir_response, report_fhir_error


def poll_validation_status(doc_id, token, timeout=300):
    """Poll validation status until completion or timeout."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    start_time = time.time()

    while True:
        try:
            response = requests.get(
                f"{config.BASE_URL}/S3Controller/upload/{doc_id}/$validation-status",
                headers=headers,
                cert=(config.CERT, config.KEY),
            )

            if response.status_code == 200:
                result = response.json()
                status = result.get("status")
                done = result.get("done")
                message = result.get("message")

                status_color = (
                    typer.colors.GREEN if status == "VALID" else typer.colors.RED
                )
                done_color = typer.colors.GREEN if done else typer.colors.RED
                styled_status = typer.style(status, fg=status_color)
                styled_done = typer.style(done, fg=done_color)

                if message is None:
                    print(f"Current status: {styled_status} (done={styled_done})")
                else:
                    print(
                        f"Current status: {styled_status} (done={styled_done}) "
                        f"mit message: {message}"
                    )

                if done:
                    print(
                        f"{typer.style('Validation', fg=typer.colors.GREEN)} "
                        "finished."
                    )
                    return status
            else:
                print(
                    f"{typer.style('Error', fg=typer.colors.RED)}: "
                    f"{response.status_code}"
                )
                report_fhir_error(
                    parse_fhir_response(response),
                    resource="DocumentReference validation status",
                )

        except requests.RequestException as error:
            print(
                f"{typer.style('Networkerror', fg=typer.colors.RED)} "
                "during polling:",
                error,
            )

        if time.time() - start_time > timeout:
            print(
                "Validation took to long "
                f"({typer.style('Timeout', fg=typer.colors.RED)})."
            )
            return "TIMEOUT"

        time.sleep(5)
