from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv, find_dotenv

EXPECTED_KEYS = [
    "CERT_URL",
    "KEY_URL",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "USERNAME",
    "BASE_URL",
]

CERT = None
KEY = None

CLIENT_ID = None
CLIENT_SECRET = None
USERNAME = None

BASE_URL = None

def load_env(config_path: Optional[Path] = None) -> dict:
    """
    Lädt .env:
    - Wenn --config gesetzt: genau diese Datei laden.
    - Sonst: automatische Suche im Projekt.
    - Fehlende Keys -> Info-Print.
    - Wenn gar kein erwarteter Key gesetzt -> Fehler.
    Setzt zusätzlich Modul-Attribute (CERT, KEY, CLIENT_ID, CLIENT_SECRET, USERNAME, BASE_URL).
    """
    origin = None

    if config_path is not None:
        cp = Path(config_path).expanduser().resolve()
        if not cp.exists():
            raise FileNotFoundError(f".env file not found at: {cp}")
        load_dotenv(dotenv_path=str(cp), override=False)
        origin = str(cp)
    else:
        auto = find_dotenv(usecwd=True)
        if not auto:
            raise FileNotFoundError(
                "No .env found. Provide one via --config or place a .env in the project."
            )
        load_dotenv(dotenv_path=auto, override=False)
        origin = auto

    # Werte lesen
    values = {key: os.getenv(key) for key in EXPECTED_KEYS}

    # Mindestens ein Key muss gesetzt sein
    non_empty = sum(1 for v in values.values() if v not in (None, ""))
    if non_empty == 0:
        raise RuntimeError(
            f"No expected keys found in loaded environment ({origin}). "
            f"Expected at least one of: {', '.join(EXPECTED_KEYS)}"
        )

    # Infos für fehlende Keys
    for k, v in values.items():
        if v in (None, ""):
            print(f"[info] {k} not set (will be None)")

    print(f"[INFO] Loaded configuration from: {origin}")

    # --- Mapping auf Attribut-Namen ---
    g = globals()
    g["CERT"] = values.get("CERT_URL")
    g["KEY"] = values.get("KEY_URL")

    g["CLIENT_ID"] = values.get("CLIENT_ID")
    g["CLIENT_SECRET"] = values.get("CLIENT_SECRET")
    g["USERNAME"] = values.get("USERNAME")

    g["BASE_URL"] = values.get("BASE_URL")

    return values
