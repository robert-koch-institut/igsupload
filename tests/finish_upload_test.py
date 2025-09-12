import pytest
from unittest import mock
import requests

from src.igsupload import finish_upload

@pytest.fixture
def mock_finished_upload():
    """Fixture, um requests.post zu mocken."""
    with mock.patch('src.igsupload.finish_upload.requests.post') as mock_post:
        yield mock_post

def get_print_calls(mock_print):
    return [" ".join(str(a) for a in args) for args, _ in mock_print.call_args_list]

def test_post_upload_body_success(mock_finished_upload):
    mock_response = mock.Mock()
    mock_response.status_code = 204
    mock_finished_upload.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        result = finish_upload.post_upload_body("docid", {"file": "abc"}, "token")
        print_calls = get_print_calls(mock_print)

    assert any("successful" in call for call in print_calls)
    assert result is None
    mock_finished_upload.assert_called_once()

def test_post_upload_body_error_json(mock_finished_upload):
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "Fehlertext", "code": 123}
    mock_finished_upload.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        result = finish_upload.post_upload_body("docid", {"file": "abc"}, "token")
        print_calls = get_print_calls(mock_print)

    assert any("Fehler" in call for call in print_calls)
    assert any("error: Fehlertext" in call for call in print_calls)
    assert any("code: 123" in call for call in print_calls)
    assert result is None

def test_post_upload_body_error_no_json(mock_finished_upload):
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_response.json.side_effect = ValueError("no json")
    mock_finished_upload.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        result = finish_upload.post_upload_body("docid", {"file": "abc"}, "token")
        print_calls = get_print_calls(mock_print)

    assert any(f"beim Upload: {mock_response.status_code}" in call for call in print_calls)
    assert any("JSON response" in call for call in print_calls)
    assert result is None

def test_post_upload_body_ssl_error(mock_finished_upload):
    mock_finished_upload.side_effect = requests.exceptions.SSLError("SSL fail")

    with mock.patch("builtins.print") as mock_print:
        result = finish_upload.post_upload_body("docid", {"file": "abc"}, "token")
        print_calls = get_print_calls(mock_print)

    assert any("SSL-Error" in call for call in print_calls)
    assert any("SSL fail" in call for call in print_calls)
    assert result is None

def test_post_upload_body_request_exception(mock_finished_upload):
    mock_finished_upload.side_effect = requests.exceptions.RequestException("Netzwerkfehler")

    with mock.patch("builtins.print") as mock_print:
        result = finish_upload.post_upload_body("docid", {"file": "abc"}, "token")
        print_calls = get_print_calls(mock_print)

    assert any("Network-/Connectionerror" in call for call in print_calls)
    assert any("Netzwerkfehler" in call for call in print_calls)
    assert result is None
