from unittest import mock

import pytest
import requests

from igsupload.auth import token_provider as token_module
from igsupload.auth.bearer_auth import BearerAuth
from igsupload.auth.token_provider import TokenProvider


def token_response(access_token, refresh_token, expires_in=300):
    response = mock.Mock()
    response.json.return_value = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "refresh_expires_in": 900,
    }
    return response


def test_access_token_is_fetched_once_and_cached(monkeypatch, test_settings):
    response = token_response("access-1", "refresh-1")
    post = mock.Mock(return_value=response)
    monkeypatch.setattr(token_module.requests, "post", post)
    provider = TokenProvider(test_settings)

    assert provider.get_token() == "access-1"
    assert provider.get_token() == "access-1"

    post.assert_called_once_with(
        url=test_settings.token_url,
        data={
            "grant_type": "password",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "username": "test-user",
        },
        cert=(test_settings.cert, test_settings.key),
        timeout=15,
    )
    response.raise_for_status.assert_called_once_with()


def test_expired_access_token_uses_refresh_token(monkeypatch, test_settings):
    first = token_response("access-1", "refresh-1", expires_in=61)
    second = token_response("access-2", "refresh-2")
    post = mock.Mock(side_effect=[first, second])
    monotonic_values = iter([100.0, 102.0, 102.0, 102.0])
    monkeypatch.setattr(token_module.requests, "post", post)
    monkeypatch.setattr(
        token_module.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    provider = TokenProvider(test_settings)

    assert provider.get_token() == "access-1"
    assert provider.get_token() == "access-2"

    assert post.call_args_list[1].kwargs["data"] == {
        "grant_type": "refresh_token",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "refresh_token": "refresh-1",
    }


def test_invalid_token_lifetime_is_rejected(monkeypatch, test_settings):
    response = token_response("access", "refresh", expires_in=0)
    monkeypatch.setattr(token_module.requests, "post", mock.Mock(return_value=response))
    provider = TokenProvider(test_settings)

    with pytest.raises(ValueError, match="Invalid token lifetime"):
        provider.get_token()


def test_bearer_auth_adds_current_access_token():
    token_provider = mock.Mock()
    token_provider.get_token.return_value = "access-token"
    prepared_request = requests.Request(
        "GET",
        "https://test.invalid/resource",
    ).prepare()

    result = BearerAuth(token_provider)(prepared_request)

    assert result.headers["Authorization"] == "Bearer access-token"
    token_provider.get_token.assert_called_once_with()
