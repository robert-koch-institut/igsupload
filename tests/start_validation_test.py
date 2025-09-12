import pytest
from unittest import mock
import requests

from src.igsupload.start_validation import start_validation

@pytest.fixture
def mock_requests_post():
    """Fixture, um requests.post in start_validation zu mocken."""
    with mock.patch('src.igsupload.start_validation.requests.post') as mock_post:
        yield mock_post

@pytest.fixture
def mock_typer_style():
    """Fixture, um typer.style zu mocken."""
    with mock.patch('src.igsupload.start_validation.typer.style') as mock_style:
        mock_style.side_effect = lambda text, fg: text  # Nur Text, keine Farbe
        yield mock_style

def test_start_validation_success(mock_requests_post, mock_typer_style):
    mock_response = mock.Mock()
    mock_response.status_code = 204
    mock_requests_post.return_value = mock_response

    token = "test_token"
    doc_id = "test_doc_id"

    with mock.patch("builtins.print") as mock_print:
        start_validation(doc_id, token)
        # Prüfen ob der Success-Print aufgerufen wurde
        mock_print.assert_any_call("Validation was started successfully.")

    mock_requests_post.assert_called_once()
    _, kwargs = mock_requests_post.call_args
    assert kwargs["headers"]["Authorization"] == f"Bearer {token}"

def test_start_validation_error_status(mock_requests_post, mock_typer_style):
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    mock_requests_post.return_value = mock_response

    with mock.patch("builtins.print") as mock_print:
        start_validation("id", "token")
        mock_print.assert_any_call("Error at validation start: 400")
        mock_print.assert_any_call("Response:", "Bad request")

def test_start_validation_ssl_error(mock_requests_post, mock_typer_style):
    mock_requests_post.side_effect = requests.exceptions.SSLError("SSL error")
    with mock.patch("builtins.print") as mock_print:
        start_validation("id", "token")
        mock_print.assert_any_call("SSL-Error (wrong certificate?):")
        assert any("SSL error" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])

def test_start_validation_request_exception(mock_requests_post, mock_typer_style):
    mock_requests_post.side_effect = requests.exceptions.RequestException("Connection error")
    with mock.patch("builtins.print") as mock_print:
        start_validation("id", "token")
        mock_print.assert_any_call("Network-/Connectionerror:")
        assert any("Connection error" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
