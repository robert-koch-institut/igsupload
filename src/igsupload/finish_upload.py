import typer
import requests
import igsupload.config as config


def post_upload_body(doc_id, complete_upload_body, token):
  try:
    headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json"
    }

    response = requests.post(
        f"{config.BASE_URL}/S3Controller/upload/{doc_id}/$finish-upload",
        headers=headers,
        json=complete_upload_body,
        cert=(config.CERT, config.KEY)
    )

    if response.status_code == 204:
      msg = f"Upload was {typer.style('successful', fg=typer.colors.GREEN)}."
      print(msg)
      return

    msg = f"{typer.style('Fehler', fg=typer.colors.RED)} beim Upload: {response.status_code}"
    print(msg)

    try:
      error_json = response.json()
      print(f"{typer.style('Error', fg=typer.colors.RED)} (JSON):")
      for key, val in error_json.items():
        print(f"   {key}: {val}")
    except ValueError:
      print(f"{typer.style('No', fg=typer.colors.RED)} JSON response")
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
