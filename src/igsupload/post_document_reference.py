import typer
import igsupload.config as config
import requests

def post_document_reference(document_reference, token):
    try:
        headers = {
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/fhir+json"
        }
    
        response = requests.post(
            f"{config.BASE_URL}/fhir/DocumentReference",
            headers=headers,
            json=document_reference,
            cert=(config.CERT, config.KEY)
        )

        if response.status_code == 201:
            result = response.json()
            print(f"Upload {typer.style('successful', fg=typer.colors.GREEN)}: DocumentReference ID = {result.get('id')}")
            return result.get("id")

        print(f"{typer.style('Error', fg=typer.colors.RED)} during Upload: {response.status_code}")

        try:
            error_json = response.json()
            print(f"{typer.style('Error', fg=typer.colors.GREEN)} (JSON):")
            for key, val in error_json.items():
                print(f"   {key}: {val}")
        except ValueError:
            print(f"{typer.style('No', fg=typer.colors.GREEN)} JSON response")
            print(response.text)

        return None

    except requests.exceptions.SSLError as ssl_err:
        msg = f"{typer.style('SSL-Error', fg=typer.colors.RED)} (wrong certificate?):"
        print(msg)
        print(ssl_err)

    except requests.exceptions.RequestException as e:
        msg = f"{typer.style('Network-/Connectionerror', fg=typer.colors.RED)}:"
        print(msg)
        print(e)

