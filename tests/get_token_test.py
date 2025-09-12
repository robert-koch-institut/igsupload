import pytest
from unittest import mock
import requests

from src.igsupload import get_token as token_manager

@pytest.fixture
def mock_requests_post():
    with mock.patch('src.igsupload.get_token.requests.post') as mock_post:
        yield mock_post

def test_get_token_success(mock_requests_post):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "test_token", "refresh_token": "test_refresh_token"}
    mock_requests_post.return_value = mock_response

    token, refresh_token = token_manager.get_token()

    assert token == "test_token"
    assert refresh_token == "test_refresh_token"
    mock_requests_post.assert_called_once()

def test_update_token_one_loop(monkeypatch, mock_requests_post):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "loop_token", "refresh_token": "loop_refresh"}
    mock_requests_post.return_value = mock_response

    call_counter = {"count": 0}
    def fake_sleep(_):
        call_counter["count"] += 1
        if call_counter["count"] > 1:
            raise StopIteration()

    with mock.patch("src.igsupload.get_token.typer.style", side_effect=lambda text, fg=None: f"[{fg}]{text}"):
        with mock.patch("src.igsupload.get_token.typer.colors.GREEN", "green"):
            with mock.patch("src.igsupload.get_token.time.sleep", side_effect=fake_sleep):
                try:
                    token_manager.update_token()
                except StopIteration:
                    pass

    assert mock_requests_post.call_count == 2

def test_get_token_ssl_error(mock_requests_post):
    mock_requests_post.side_effect = requests.exceptions.SSLError("SSL fail")
    result = token_manager.get_token()
    assert result == (None, None)
    mock_requests_post.assert_called_once()

def test_get_token_request_exception(mock_requests_post):
    mock_requests_post.side_effect = requests.exceptions.RequestException("Netzwerk-/Verbindungsfehler")
    result = token_manager.get_token()
    assert result == (None, None)
    mock_requests_post.assert_called_once()

def test_get_token_value_error(mock_requests_post):
    mock_response = mock.Mock()
    mock_response.json.side_effect = ValueError("No JSON!")
    mock_requests_post.return_value = mock_response
    result = token_manager.get_token()
    assert result == (None, None)
    mock_requests_post.assert_called_once()

def test_get_token_error_response(mock_requests_post):
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"status_code": "400", "message": "Error 400"}
    mock_requests_post.return_value = mock_response
    response = token_manager.get_token()
    assert response == (None, None)
    mock_requests_post.assert_called_once()

def test_get_token_with_refresh_token(mock_requests_post):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "abc", "refresh_token": "def"}
    mock_requests_post.return_value = mock_response
    token, refresh = token_manager.get_token(refresh_token="foobar")
    assert token == "abc"
    assert refresh == "def"
    mock_requests_post.assert_called_once()
