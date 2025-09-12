import os
import json
import typer
import igsupload.config as config
import requests

def put_chunks(file_path, chunk_size, presigned_urls, upload_id):
    json_object = {
        "uploadId": upload_id,
        "completedChunks": []
    }

    for part_number, chunk in enumerate(split_file_in_chunks(file_path, chunk_size), start=1):
        url = presigned_urls[part_number - 1]
        response = requests.put(url, data=chunk)

        if response.status_code != 200:
            print(f"{typer.style('Error', fg=typer.colors.RED)} while uploading chunk {part_number}: {response.status_code}")
            break

        etag = response.headers.get("ETag", "").strip('"')
        json_object["completedChunks"].append({
            "partNumber": part_number,
            "eTag": etag
        })

        print(f"Chunk {part_number} {typer.style('uploaded', fg=typer.colors.GREEN)}, eTag: {etag}")

    return json_object

def split_file_in_chunks(file_path, chunk_size):
  with open(file_path, "rb") as file:
    while True:
      chunk = file.read(chunk_size)
      if not chunk:
        break
      yield chunk