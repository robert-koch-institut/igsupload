import requests
import typer

from igsupload.redaction import redact_text


def put_chunks(file_path, chunk_size, presigned_urls, upload_id):
    result = {
        "uploadId": upload_id,
        "completedChunks": [],
    }

    chunks = split_file_in_chunks(file_path, chunk_size)
    for part_number, chunk in enumerate(chunks, start=1):
        url = presigned_urls[part_number - 1]
        try:
            response = requests.put(url, data=chunk)
        except requests.RequestException as error:
            print(
                f"{typer.style('Networkerror', fg=typer.colors.RED)} while "
                f"uploading chunk {part_number}: {redact_text(str(error))}"
            )
            break

        if response.status_code != 200:
            print(
                f"{typer.style('Error', fg=typer.colors.RED)} while uploading "
                f"chunk {part_number}: {response.status_code}"
            )
            break

        etag = response.headers.get("ETag", "").strip('"')
        result["completedChunks"].append(
            {
                "partNumber": part_number,
                "eTag": etag,
            }
        )
        print(
            f"Chunk {part_number} "
            f"{typer.style('uploaded', fg=typer.colors.GREEN)}, "
            f"eTag: {redact_text(etag)}"
        )

    return result


def split_file_in_chunks(file_path, chunk_size):
    with open(file_path, "rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk
