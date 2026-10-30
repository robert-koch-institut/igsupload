from unittest import mock

import pytest
import requests

from igsupload.api import client as client_module
from igsupload.api.client import ApiClient
from igsupload.auth.bearer_auth import BearerAuth


def create_client(test_settings):
    token_provider = mock.Mock()
    return ApiClient(
        base_url=test_settings.base_url,
        token_provider=token_provider,
        cert_path=test_settings.cert,
        key_path=test_settings.key,
    )


def test_client_configures_session_for_demis(test_settings):
    client = create_client(test_settings)

    assert isinstance(client._session.auth, BearerAuth)
    assert client._session.cert == (test_settings.cert, test_settings.key)
    assert client._session.headers["Content-Type"] == "application/fhir+json"
    assert client._session.headers["Accept"] == "application/fhir+json"
    client.close()


def test_request_uses_base_url_and_raises_for_http_errors(test_settings):
    client = create_client(test_settings)
    response = mock.Mock()
    session = mock.Mock()
    session.request.return_value = response
    client._session = session

    result = client._request(
        "POST",
        "/v5/fhir/DocumentReference",
        payload={"resourceType": "DocumentReference"},
    )

    assert result is response
    session.request.assert_called_once_with(
        method="POST",
        url=f"{test_settings.base_url}/v5/fhir/DocumentReference",
        json={"resourceType": "DocumentReference"},
        params=None,
        headers=None,
        timeout=15,
    )
    response.raise_for_status.assert_called_once_with()


def test_document_reference_and_upload_endpoints(test_settings):
    client = create_client(test_settings)
    response = mock.Mock()
    response.json.side_effect = [
        {"id": "document-1"},
        {
            "uploadId": "upload-1",
            "presignedUrls": ["https://upload.test.invalid/part-1"],
            "partSizeBytes": 1024,
        },
    ]
    request = mock.Mock(return_value=response)
    client._request = request

    document_id = client.post_doc_ref({"resourceType": "DocumentReference"})
    upload_info = client.get_presigned_url(document_id, 2048)

    assert document_id == "document-1"
    assert upload_info["uploadId"] == "upload-1"
    assert request.call_args_list == [
        mock.call(
            method="POST",
            endpoint="/v5/fhir/DocumentReference",
            payload={"resourceType": "DocumentReference"},
        ),
        mock.call(
            method="GET",
            endpoint=(
                "/S3Controller/upload/document-1/s3-upload-info"
            ),
            params={"fileSize": 2048},
        ),
    ]
    client.close()


def test_upload_lifecycle_and_notification_endpoints(test_settings):
    client = create_client(test_settings)
    response = mock.Mock()
    response.json.return_value = {"done": True, "status": "VALID"}
    request = mock.Mock(return_value=response)
    client._request = request
    complete_body = {
        "uploadId": "upload-1",
        "completedChunks": [{"partNumber": 1, "eTag": "etag-1"}],
    }
    bundle = {"resourceType": "Bundle"}

    client.post_finish_upload("document-1", complete_body)
    client.post_start_validation("document-1")
    validation = client.get_validation_status("document-1")
    client.post_igs_bundle(bundle)

    assert validation == {"done": True, "status": "VALID"}
    assert request.call_args_list == [
        mock.call(
            method="POST",
            endpoint="/S3Controller/upload/document-1/$finish-upload",
            payload=complete_body,
            headers={"Content-Type": "application/json"},
        ),
        mock.call(
            method="POST",
            endpoint="/S3Controller/upload/document-1/$validate",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        ),
        mock.call(
            method="GET",
            endpoint="/S3Controller/upload/document-1/$validation-status",
            timeout=300,
        ),
        mock.call(
            method="POST",
            endpoint="/v5/fhir/$process-notification-sequence",
            payload=bundle,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        ),
    ]
    client.close()


def test_chunk_upload_streams_parts_and_collects_etags(
    tmp_path,
    monkeypatch,
    test_settings,
):
    file_path = tmp_path / "sample.fastq"
    file_path.write_bytes(b"abcdefghij")
    responses = []
    for number in range(1, 4):
        response = mock.Mock(status_code=200)
        response.headers = {"ETag": f'"etag-{number}"'}
        responses.append(response)
    put = mock.Mock(side_effect=responses)
    monkeypatch.setattr(client_module.requests, "put", put)
    client = create_client(test_settings)

    result = client.put_file_chunks(
        file_path,
        chunk_size=4,
        presigned_urls=["url-1", "url-2", "url-3"],
        upload_id="upload-1",
    )

    assert [call.kwargs["data"] for call in put.call_args_list] == [
        b"abcd",
        b"efgh",
        b"ij",
    ]
    assert result == {
        "uploadId": "upload-1",
        "completedChunks": [
            {"partNumber": 1, "eTag": "etag-1"},
            {"partNumber": 2, "eTag": "etag-2"},
            {"partNumber": 3, "eTag": "etag-3"},
        ],
    }
    client.close()


def test_failed_chunk_upload_raises_http_error(
    tmp_path,
    monkeypatch,
    test_settings,
):
    file_path = tmp_path / "sample.fastq"
    file_path.write_bytes(b"abcd")
    response = mock.Mock(status_code=500)
    response.raise_for_status.side_effect = requests.HTTPError("upload failed")
    monkeypatch.setattr(
        client_module.requests,
        "put",
        mock.Mock(return_value=response),
    )
    client = create_client(test_settings)

    with pytest.raises(requests.HTTPError, match="upload failed"):
        client.put_file_chunks(file_path, 4, ["url-1"], "upload-1")

    client.close()
