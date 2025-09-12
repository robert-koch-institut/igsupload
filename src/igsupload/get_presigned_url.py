import typer
import igsupload.config as config
import requests

def get_presigned_url(token, doc_id, file_in_bytes):
  try:
    params = {"fileSize": file_in_bytes}
    headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/fhir+json"
    }
    response = requests.get(
      f"{config.BASE_URL}/S3Controller/upload/{doc_id}/s3-upload-info",
      headers=headers,
      params=params,
      cert=(config.CERT, config.KEY)
    )
    
    if response.status_code == 200:
      result = response.json()
      print(f"GET request {typer.style('successful', fg=typer.colors.GREEN)}")
      return result.get("uploadId"), result.get("presignedUrls"), result.get("partSizeBytes")

    print(f"{typer.style('Error', fg=typer.colors.RED)} during upload: {response.status_code}")

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


  