import pytest
from unittest import mock
import requests

from src.igsupload import get_presigned_url

@pytest.fixture
def mock_requests_get():
    with mock.patch('src.igsupload.get_presigned_url.requests.get') as mock_get:
        yield mock_get

def get_print_calls(mock_print):
    return [" ".join(str(a) for a in args) for args, _ in mock_print.call_args_list]

def test_get_presigned_url_success(mock_requests_get):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "uploadId": "12345",
        "presignedUrls": ["https://upload1", "https://upload2"],
        "partSizeBytes": 1234
    }
    mock_requests_get.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        result = get_presigned_url.get_presigned_url("token", "docid", 123456)
        print_calls = get_print_calls(mock_print)

    assert any("successful" in call for call in print_calls)
    assert result == ("12345", ["https://upload1", "https://upload2"], 1234)
    mock_requests_get.assert_called_once()

def test_get_presigned_url_error_json(mock_requests_get):
    mock_response = mock.Mock()
    mock_response.json.return_value = {
        "error": "irgendwas schiefgelaufen",
        "info": "mehr infos"
    }
    mock_requests_get.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        result = get_presigned_url.get_presigned_url("token", "docid", 123456)
        print_calls = get_print_calls(mock_print)

    assert result is None

def test_get_presigned_url_error_no_json(mock_requests_get):
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_response.json.side_effect = ValueError("no json")
    mock_requests_get.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        result = get_presigned_url.get_presigned_url("token", "docid", 123456)
        print_calls = get_print_calls(mock_print)

    assert any("Error during upload: 400" in call or "Error" in call for call in print_calls)
    assert any("JSON response" in call for call in print_calls)
    assert result is None

def test_get_presigned_url_ssl_error(mock_requests_get):
    mock_requests_get.side_effect = requests.exceptions.SSLError("SSL kaputt")

    with mock.patch("builtins.print") as mock_print:
        result = get_presigned_url.get_presigned_url("token", "docid", 123456)
        print_calls = get_print_calls(mock_print)

    assert any("SSL-Error" in call for call in print_calls)
    assert any("SSL kaputt" in call for call in print_calls)
    assert result is None

def test_get_presigned_url_request_exception(mock_requests_get):
    mock_requests_get.side_effect = requests.exceptions.RequestException("Netzwerkfehler")

    with mock.patch("builtins.print") as mock_print:
        result = get_presigned_url.get_presigned_url("token", "docid", 123456)
        print_calls = get_print_calls(mock_print)

    assert any("Network-/Connectionerror" in call for call in print_calls)
    assert any("Netzwerkfehler" in call for call in print_calls)
    assert result is None
