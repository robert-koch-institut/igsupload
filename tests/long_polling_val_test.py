import pytest
from unittest.mock import patch, MagicMock
import requests

from src.igsupload.long_polling_val import poll_validation_status

@pytest.fixture
def mock_get_requests():
    with patch("requests.get") as mock_get:
        yield mock_get

@pytest.fixture
def mock_time_sleep():
    with patch("time.sleep", return_value=None):
        yield

@pytest.fixture
def mock_time_time():
    # Simuliere eine immer weiterlaufende Zeit, damit Timeout-Tests durchlaufen
    with patch("time.time") as mock_time:
        yield mock_time

def make_response(status_code, json_data=None, text="ERROR"):
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    resp.text = text
    return resp

def get_print_calls(mock_print):
    # Gibt alle print-Aufrufe als Strings (inklusive aller Argumente pro Aufruf)
    return [" ".join(str(a) for a in args) for args, _ in mock_print.call_args_list]


def test_status_valid_done_true(mock_get_requests):
    mock_get_requests.return_value = make_response(
        200, {"status": "VALID", "done": True, "message": None}
    )
    with patch("builtins.print") as mock_print:
        status = poll_validation_status("doc", "token", timeout=5)
        calls = get_print_calls(mock_print)
        assert status == "VALID"
        assert any("Current status" in c for c in calls)
        assert any("finished" in c for c in calls)

def test_status_invalid_done_true(mock_get_requests):
    mock_get_requests.return_value = make_response(
        200, {"status": "INVALID", "done": True, "message": None}
    )
    with patch("builtins.print") as mock_print:
        status = poll_validation_status("doc", "token", timeout=5)
        calls = get_print_calls(mock_print)
        assert status == "INVALID"
        assert any("Current status" in c for c in calls)
        assert any("finished" in c for c in calls)

def test_status_valid_done_false_then_true(mock_get_requests, mock_time_sleep):
    # Zwei Rückgaben: erst done=False, dann done=True
    mock_get_requests.side_effect = [
        make_response(200, {"status": "VALID", "done": False, "message": None}),
        make_response(200, {"status": "VALID", "done": True, "message": None}),
    ]
    with patch("builtins.print") as mock_print:
        status = poll_validation_status("doc", "token", timeout=5)
        calls = get_print_calls(mock_print)
        assert status == "VALID"
        assert any("Current status" in c for c in calls)
        assert any("finished" in c for c in calls)
        assert mock_get_requests.call_count == 2

def test_status_with_message(mock_get_requests):
    mock_get_requests.return_value = make_response(
        200, {"status": "INVALID", "done": True, "message": "Fehler"}
    )
    with patch("builtins.print") as mock_print:
        status = poll_validation_status("doc", "token", timeout=5)
        calls = get_print_calls(mock_print)
        assert status == "INVALID"
        assert any("mit message: Fehler" in c for c in calls)

def test_statuscode_not_200(mock_get_requests, mock_time_sleep):
    # Simuliere mehrere fehlerhafte Responses bis zum Timeout
    mock_get_requests.return_value = make_response(500, None, text="Internal Error")
    fake_times = [0, 10, 20, 400, 1000]
    with patch("builtins.print") as mock_print, \
         patch("time.time", side_effect=fake_times):
        status = poll_validation_status("doc", "token", timeout=0.01)
        calls = get_print_calls(mock_print)
        assert status == "TIMEOUT"
        assert any("Error" in c for c in calls)
        assert any("Internal Error" in c for c in calls)

def test_poll_validation_status_request_exception(mock_time_sleep):
    # Simuliere Netzwerkfehler, bis zum Timeout
    fake_times = [0, 5, 400, 1000]
    with patch("requests.get", side_effect=requests.exceptions.RequestException("Netzwerk-/Verbindungsfehler")), \
         patch("builtins.print") as mock_print, \
         patch("time.time", side_effect=fake_times):
        status = poll_validation_status("doc", "token", timeout=0.01)
        calls = get_print_calls(mock_print)
        assert status == "TIMEOUT"
        assert any("Networkerror" in c for c in calls)
        assert any("Netzwerk-/Verbindungsfehler" in c for c in calls)

def test_timeout_exit(mock_get_requests, mock_time_sleep):
    # requests.get gibt immer done=False zurück, Zeit läuft bis Timeout
    mock_get_requests.return_value = make_response(
        200, {"status": "VALID", "done": False, "message": None}
    )
    fake_times = [0, 5, 10, 15, 400]
    with patch("builtins.print") as mock_print, \
         patch("time.time", side_effect=fake_times):
        status = poll_validation_status("doc", "token", timeout=0.01)
        calls = get_print_calls(mock_print)
        assert status == "TIMEOUT"
        assert any("took to long" in c for c in calls)
