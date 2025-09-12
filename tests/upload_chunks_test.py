import tempfile
import pytest
from unittest import mock

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
