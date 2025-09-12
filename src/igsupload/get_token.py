import typer
import requests
import igsupload.config as config
import time
import threading
from urllib.parse import urlparse

current_token = None
refresh_token = None


def base_url(url: str) -> str:
    """Return the base URL (scheme + netloc) of a given URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_token(refresh_token=None):
    data = {
        "grant_type": "refresh_token" if refresh_token else "password",
        "client_id": config.CLIENT_ID,
        "client_secret": config.CLIENT_SECRET
    }

    if refresh_token:
        data["refresh_token"] = refresh_token
    else:
        data["username"] = config.USERNAME

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(
            base_url(config.BASE_URL)+"/auth/realms/LAB/protocol/openid-connect/token",
            data=data,
            headers=headers,
            cert=(config.CERT, config.KEY)
        )

        if response.status_code == 200:
            result = response.json()
            print(f"Token request was {typer.style('successfull', fg=typer.colors.GREEN)} and the token {typer.style('created', fg=typer.colors.GREEN)}")
            return result.get("access_token"), result.get("refresh_token")

        print(f"{typer.style('Error', fg=typer.colors.RED)} during token request: {response.status_code}")
        try:
            error_json = response.json()
            print(f"{typer.style('Error', fg=typer.colors.RED)} (JSON):")
            for key, val in error_json.items():
                print(f"   {key}: {val}")
        except ValueError:
            print(f"{typer.style('No', fg=typer.colors.RED)} JSON response")
            print(response.text)


    except requests.exceptions.SSLError as ssl_err:
        msg = f"{typer.style('SSL-Error', fg=typer.colors.RED)} (wrong certificate?):"
        print(msg)
        print(ssl_err)

    except requests.exceptions.RequestException as e:
        msg = f"{typer.style('Network-/Connectionerror', fg=typer.colors.RED)}:"
        print(msg)
        print(e)

    return None, None


def update_token():
    global current_token, refresh_token
    while True:
        print(f"New Token is {typer.style('created', fg=typer.colors.GREEN)}...")
        current_token, refresh_token = get_token(refresh_token)
        time.sleep(580)