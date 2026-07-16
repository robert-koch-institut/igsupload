import requests
import typer

import igsupload.config as config


def start_validation(doc_id, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{config.BASE_URL}/S3Controller/upload/{doc_id}/$validate",
            headers=headers,
            cert=(config.CERT, config.KEY),
        )

        if response.status_code == 204:
            print(
                "Validation was started "
                f"{typer.style('successfully', fg=typer.colors.GREEN)}."
            )
            return True

        print(
            f"{typer.style('Error', fg=typer.colors.RED)} "
            f"at validation start: {response.status_code}"
        )
        print("Response:", response.text)
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
