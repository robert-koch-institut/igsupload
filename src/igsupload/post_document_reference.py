import typer
import igsupload.config as config
import requests
from igsupload.fhir_response import parse_fhir_response, report_fhir_error
from igsupload.redaction import redact_text

def post_document_reference(document_reference, token):
    try:
        headers = {
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/fhir+json"
        }
    
        response = requests.post(
            f"{config.BASE_URL}/v5/fhir/DocumentReference",
            headers=headers,
            json=document_reference,
            cert=(config.CERT, config.KEY)
        )

        if response.status_code == 201:
            result = response.json()
            print(f"Upload {typer.style('successful', fg=typer.colors.GREEN)}: DocumentReference ID = {result.get('id')}")
            return result.get("id")

        print(f"{typer.style('Error', fg=typer.colors.RED)} during Upload: {response.status_code}")
        report_fhir_error(
            parse_fhir_response(response),
            resource="DocumentReference",
        )

        return None

    except requests.exceptions.SSLError as ssl_err:
        msg = f"{typer.style('SSL-Error', fg=typer.colors.RED)} (wrong certificate?):"
        print(msg)
        print(redact_text(str(ssl_err)))

    except requests.exceptions.RequestException as e:
        msg = f"{typer.style('Network-/Connectionerror', fg=typer.colors.RED)}:"
        print(msg)
        print(redact_text(str(e)))
