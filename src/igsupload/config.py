import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


REQUIRED_KEYS = [
    "CERT_URL",
    "KEY_URL",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "USERNAME",
    "BASE_URL",
    "TOKEN_URL",
]


@dataclass(frozen=True)
class Settings:
    cert: str
    key: str
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
            raise FileNotFoundError(
                f"Configuration file not found: {path}"
            )

        load_dotenv(path, override=True)
    else:
        load_dotenv()

    
    # Check if all required environment variables exist
    missing_keys = [
        key for key in REQUIRED_KEYS
        if not os.getenv(key)
    ]
    if missing_keys:
        raise ValueError(
            f"Missing configuration values: {', '.join(missing_keys)}"
        )


    return Settings(
        cert=os.environ["CERT_URL"],
        key=os.environ["KEY_URL"],
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        username=os.environ["USERNAME"],
        base_url=os.environ["BASE_URL"],
        token_url=os.environ["TOKEN_URL"],
    )
