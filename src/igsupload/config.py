import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REQUIRED_KEYS = [
    "PKCS12_PATH",
    "PASSWORD",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "USERNAME",
    "BASE_URL",
    "TOKEN_URL",
]


@dataclass(frozen=True)
class Settings:
    pkcs12_path: str
    password: str = field(repr=False)
    client_id: str
    client_secret: str = field(repr=False)
    username: str
    base_url: str
    token_url: str


def load_env(path: Path | None = None) -> Settings:
    """Load and validate the application configuration."""

    # Load custom .env or search automatically
    if path is not None:
        path = path.expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        load_dotenv(path, override=True)
    else:
        load_dotenv()

    # Check if all required environment variables exist
    missing_keys = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    if missing_keys:
        raise ValueError(f"Missing configuration values: {', '.join(missing_keys)}")

    return Settings(
        pkcs12_path=os.environ.get("PKCS12_PATH"),
        password=os.environ.get("PASSWORD"),
        client_id=os.environ.get("CLIENT_ID"),
        client_secret=os.environ.get("CLIENT_SECRET"),
        username=os.environ.get("USERNAME"),
        base_url=os.environ.get("BASE_URL"),
        token_url=os.environ.get("TOKEN_URL"),
    )
