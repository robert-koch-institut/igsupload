import time
import threading
import requests

from igsupload.config import Settings


class TokenProvider:
    def __init__(self, settings: Settings):
        self._settings = settings

        self._access_token: str | None = None
        self._refresh_token: str | None = None

        self._refresh_at: float = 0.0
        self._refresh_expires_at: float = 0.0
        self._lock = threading.Lock()


    def _fetch_token(self) -> None:
        can_refresh = (
            self._refresh_token is not None
            and time.monotonic() < self._refresh_expires_at - 30
        )

        data = {
            "grant_type": "refresh_token" if can_refresh else "password",
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
        }

        if can_refresh:
            data["refresh_token"] = self._refresh_token
        else:
            data["username"] = self._settings.username

        requested_at = time.monotonic()

        response = requests.post(
            url=self._settings.token_url,
            data=data,
            cert=(self._settings.cert, self._settings.key),
            timeout=15,
        )

        response.raise_for_status()
        result = response.json()

        access_token = result["access_token"]
        refresh_token = result["refresh_token"]

        expires_in = int(result["expires_in"])
        refresh_expires_in = int(result["refresh_expires_in"])

        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Invalid access token")

        if not isinstance(refresh_token, str) or not refresh_token:
            raise ValueError("Invalid refresh token")

        if expires_in <= 0 or refresh_expires_in <= 0:
            raise ValueError("Invalid token lifetime")

        self._access_token = access_token
        self._refresh_token = refresh_token

        # Refresh access token 60 seconds before expiration
        self._refresh_at = requested_at + max(
            0, expires_in - 60
        )

        # Refresh token expiration with 30s safety margin
        self._refresh_expires_at = (
            requested_at + refresh_expires_in
        )

    def get_token(self) -> str:
        with self._lock:
            if (
                self._access_token is None
                or time.monotonic() >= self._refresh_at
            ):
                self._fetch_token()

            if self._access_token is None:
                raise RuntimeError("No access token available")

            return self._access_token