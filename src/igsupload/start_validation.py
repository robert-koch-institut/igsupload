import typer
import requests
import igsupload.config as config

def start_validation(doc_id, token):

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{config.BASE_URL}/S3Controller/upload/{doc_id}/$validate",
            headers=headers,
            cert=(config.CERT, config.KEY)
        )

        if response.status_code == 204:
            print(f"Validation was started {typer.style('successfully', fg=typer.colors.GREEN)}.")

            
        else:
            print(f"{typer.style('Error', fg=typer.colors.RED)} at validation start: {response.status_code}")
            print("Response:", response.text)

    except requests.exceptions.SSLError as ssl_err:
        msg = f"{typer.style('SSL-Error', fg=typer.colors.RED)} (wrong certificate?):"
        print(msg)
        print(ssl_err)

    except requests.exceptions.RequestException as e:
        msg = f"{typer.style('Network-/Connectionerror', fg=typer.colors.RED)}:"
        print(msg)
        print(e)