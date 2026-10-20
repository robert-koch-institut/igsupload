import requests
from requests.auth import AuthBase

from igsupload.auth.token_provider import TokenProvider


class BearerAuth(AuthBase):
    def __init__(self, token_provider: TokenProvider):
        self._token_provider = token_provider

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        token = self._token_provider.get_token()

        request.headers["Authorization"] = f"Bearer {token}"
        return request