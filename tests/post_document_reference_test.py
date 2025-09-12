import pytest
from unittest import mock
import requests

from src.igsupload import post_document_reference as post_dc
from src.igsupload import document_reference as dc

@pytest.fixture
def mock_post_document_reference():
    """Fixture, um die Funktion `post_document_reference` zu mocken."""
    with mock.patch('src.igsupload.post_document_reference.requests.post') as mock_post:
        yield mock_post

@pytest.fixture
def mock_typer_style():
    with mock.patch('src.igsupload.post_document_reference.typer.style', side_effect=lambda t, fg=None: t):
        yield

def test_post_document_reference_success(mock_post_document_reference, mock_typer_style):
    mock_response = mock.Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "test_id"}
    mock_post_document_reference.return_value = mock_response

    token = "mocked_token"
    test_file = "test.fastq"
    hash = "test_hash"

    with mock.patch("builtins.print") as mock_print:
        document_id = post_dc.post_document_reference(dc.build_document_reference(test_file, hash), token)
        assert document_id == "test_id"
        mock_post_document_reference.assert_called_once()
        # Optional: check the print call for success output
        assert any("Upload successful" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])

def test_post_document_reference_error_json_response(mock_post_document_reference, mock_typer_style):
    # Fehlerstatus + JSON-Antwort
    mock_response = mock.Mock()
    
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "Invalid input", "code": 42}
    mock_post_document_reference.return_value = mock_response

    token = "mocked_token"
    test_file = "test.fastq"
    hash = "test_hash"

    with mock.patch("builtins.print") as mock_print:
        document_id = post_dc.post_document_reference(dc.build_document_reference(test_file, hash), token)
        assert document_id is None
        # Check output
        assert any("Error during Upload: 400" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
        assert any("Error (JSON):" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
        assert any("error: Invalid input" in str(call) or "code: 42" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])

def test_post_document_reference_error_no_json_response(mock_post_document_reference, mock_typer_style):
    # Fehlerstatus + keine gültige JSON-Antwort
    mock_response = mock.Mock()
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("No JSON")
    mock_response.text = "Internal Server Error"
    mock_post_document_reference.return_value = mock_response

    token = "mocked_token"
    test_file = "test.fastq"
    hash = "test_hash"

    with mock.patch("builtins.print") as mock_print:
        document_id = post_dc.post_document_reference(dc.build_document_reference(test_file, hash), token)
        assert document_id is None
        # Output prüfen
        assert any("Error during Upload: 500" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
        assert any("No JSON response" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
        assert any("Internal Server Error" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])

def test_post_document_reference_ssl_error(mock_post_document_reference, mock_typer_style):
    mock_post_document_reference.side_effect = requests.exceptions.SSLError("SSL fail")
    test_file = "test.fastq"
    hash = "test_hash"
    with mock.patch("builtins.print") as mock_print:
        result = post_dc.post_document_reference(dc.build_document_reference(test_file, hash), token="abc")
        assert result is None
        # Output prüfen
        assert any("SSL-Error" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
        assert any("SSL fail" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])

def test_post_document_reference_request_exception(mock_post_document_reference, mock_typer_style):
    mock_post_document_reference.side_effect = requests.exceptions.RequestException("Netzwerk-/Verbindungsfehler")
    test_file = "test.fastq"
    hash = "test_hash"
    with mock.patch("builtins.print") as mock_print:
        result = post_dc.post_document_reference(dc.build_document_reference(test_file, hash), token="abc")
        assert result is None
        assert any("Network-/Connectionerror" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
        assert any("Netzwerk-/Verbindungsfehler" in str(call) for call in [args[0] for args, _ in mock_print.call_args_list])
