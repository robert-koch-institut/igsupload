import logging
from pathlib import Path
from typing import Any

import requests

from igsupload.auth.bearer_auth import BearerAuth
from igsupload.auth.token_provider import TokenProvider
from igsupload.utils.split_file import split_file_in_chunks

logger = logging.getLogger(__name__)

class ApiClient:
    # client to communicate with demis api
    def __init__(self, base_url:str, token_provider:TokenProvider, cert_path:str, key_path:str):
        self.base_url = base_url
        self.token_provider = token_provider

        self._session = requests.Session()
        self._session.auth = BearerAuth(token_provider)
        self._session.cert = (cert_path, key_path)
        self._session.headers.update({
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json",
        })

    def _request(
            self, 
            method:str, 
            endpoint:str, 
            payload: dict[str, Any] | None = None,
            params: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
            timeout: int | None = 15
    ) -> requests.Response:
        response = self._session.request(
            method=method,
            url=f"{self.base_url}{endpoint}",
            json=payload,
            params=params,
            headers=headers,
            timeout=timeout,
        )

        response.raise_for_status()
        return response

    def post_doc_ref(self, doc_ref):
        response = self._request(
            method='POST',
            endpoint="/v5/fhir/DocumentReference",
            payload=doc_ref,
        )

        return response.json()["id"]


    def get_presigned_url(self, doc_id:str, file_in_bytes:int) -> dict[str, str]:
        params = {"fileSize": file_in_bytes}
        response = self._request(
            method='GET',
            endpoint=f"/S3Controller/upload/{doc_id}/s3-upload-info",
            params=params,
        )

        return response.json()


    def put_file_chunks(
            self, 
            file_path:str, 
            chunk_size:int, 
            presigned_urls:list[str], 
            upload_id:str,
    ):
        result = {
            "uploadId": upload_id,
            "completedChunks": [],
        }

        file_size = Path(file_path).stat().st_size
        total_chunks_num = (file_size + chunk_size - 1) // chunk_size

        chunks = split_file_in_chunks(file_path, chunk_size)
        
        for part_number, chunk in enumerate(chunks, start=1):
            url = presigned_urls[part_number - 1]
            response = requests.put(
                url, 
                data=chunk,
                timeout=60,
            )

            if response.status_code != 200:
                logger.error("Error while uploading file chunks")
                logger.debug(f"chunk {part_number}: {response.status_code}")
                response.raise_for_status()
            
            etag = response.headers.get("ETag", "").strip('"')
            result["completedChunks"].append(
                {
                    "partNumber": part_number,
                    "eTag": etag,
                }
            )
            logger.info(f"Uploaded chunk {part_number} of {total_chunks_num}")

        return result


    def post_finish_upload(self, doc_id:str, upload_body:dict[str, str]):
        '''Endpoint: $finish_upload'''

        response = self._request(
            method='POST',
            endpoint=f"/S3Controller/upload/{doc_id}/$finish-upload",
            payload=upload_body,
            headers={"Content-Type": "application/json"},
        )

        return response


    def post_start_validation(self, doc_id:str):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
                
        response = self._request(
            method='POST',
            endpoint=f"/S3Controller/upload/{doc_id}/$validate",
            headers=headers,
        )

        return response


    def get_validation_status(self, doc_id:str) -> dict[str, str]:
        response = self._request(
            method='GET',
            endpoint=f"/S3Controller/upload/{doc_id}/$validation-status",
            timeout=300,
        )
        
        return response.json()

    def post_igs_bundle(self, bundle:dict[str, str]) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
            
        response = self._request(
            method='POST',
            endpoint="/v5/fhir/$process-notification-sequence",
            payload=bundle,
            headers=headers,
        )

        return response



    def close(self) -> None:
        self._session.close()