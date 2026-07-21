import tempfile
import pytest
from unittest import mock
import requests

from src.igsupload import upload_chunks

@pytest.fixture
def mock_requests_put():
    with mock.patch("src.igsupload.upload_chunks.requests.put") as mock_put:
        yield mock_put

def test_put_chunks_success(mock_requests_put):
    # Arrange: Erstelle eine Datei mit ein paar Bytes
    content = b"abcdefghij"
    chunk_size = 4  # => 3 Chunks: abcd, efgh, ij

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    # Presigned URLs für 3 Chunks
    urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

    # Mock für requests.put: immer status_code 200 und ETag-Header
    def mock_put_side_effect(url, data):
        part_number = urls.index(url) + 1
        response = mock.Mock()
        response.status_code = 200
        response.headers = {"ETag": f'"etag{part_number}"'}
        return response

    mock_requests_put.side_effect = mock_put_side_effect

    with mock.patch("builtins.print") as mock_print:
        result = upload_chunks.put_chunks(tmp_path, chunk_size, urls, "uploadid")
        print_calls = [" ".join(str(a) for a in args) for args, _ in mock_print.call_args_list]

    assert result["uploadId"] == "uploadid"
    assert len(result["completedChunks"]) == 3
    assert result["completedChunks"][0]["partNumber"] == 1
    assert result["completedChunks"][0]["eTag"] == "etag1"
    assert any("uploaded" in call for call in print_calls)

def test_put_chunks_error(mock_requests_put):
    content = b"abcdefghij"
    chunk_size = 4

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

    # der zweite Chunk schlägt fehl
    def mock_put_side_effect(url, data):
        part_number = urls.index(url) + 1
        response = mock.Mock()
        if part_number == 2:
            response.status_code = 500
            response.headers = {}
        else:
            response.status_code = 200
            response.headers = {"ETag": f'"etag{part_number}"'}
        return response

    mock_requests_put.side_effect = mock_put_side_effect

    with mock.patch("builtins.print") as mock_print:
        result = upload_chunks.put_chunks(tmp_path, chunk_size, urls, "uploadid")
        print_calls = [" ".join(str(a) for a in args) for args, _ in mock_print.call_args_list]

    # Der Upload bricht nach dem zweiten Chunk ab
    assert len(result["completedChunks"]) == 1  # Nur der erste Chunk erfolgreich
    assert any("Error" in call for call in print_calls)
    assert any("while uploading chunk 2" in call for call in print_calls)


def test_put_chunks_redacts_presigned_url_from_network_error(mock_requests_put):
    presigned_url = (
        "https://uploads.example.org/sample.fastq"
        "?X-Amz-Credential=credential-value"
        "&X-Amz-Signature=signature-value"
    )
    mock_requests_put.side_effect = requests.RequestException(
        f"Connection failed for {presigned_url} with Bearer bearer-value"
    )

    with tempfile.NamedTemporaryFile() as file:
        file.write(b"sequence-data")
        file.flush()
        with mock.patch("builtins.print") as output:
            result = upload_chunks.put_chunks(
                file.name,
                1024,
                [presigned_url],
                "uploadid",
            )

    rendered = "\n".join(
        " ".join(str(value) for value in call.args)
        for call in output.call_args_list
    )
    assert result["completedChunks"] == []
    assert "credential-value" not in rendered
    assert "signature-value" not in rendered
    assert "bearer-value" not in rendered
    assert "[PRESIGNED-QUERY-REDACTED]" in rendered
    assert "Bearer [REDACTED]" in rendered
