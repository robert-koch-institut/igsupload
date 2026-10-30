import pytest

from igsupload.config import REQUIRED_KEYS, load_env
from tests.conftest import TEST_BASE_URL, TEST_TOKEN_URL


def test_default_configuration_uses_fixed_test_environment():
    settings = load_env()

    assert settings.base_url == TEST_BASE_URL
    assert settings.token_url == TEST_TOKEN_URL
    assert settings.client_id == "test-client"


def test_explicit_test_config_is_loaded(tmp_path):
    config_path = tmp_path / ".env.test"
    config_path.write_text(
        "CERT_URL=/test/cert.pem\n"
        "KEY_URL=/test/key.pem\n"
        "CLIENT_ID=file-client\n"
        "CLIENT_SECRET=file-secret\n"
        "USERNAME=file-user\n"
        f"BASE_URL={TEST_BASE_URL}\n"
        f"TOKEN_URL={TEST_TOKEN_URL}\n",
        encoding="utf-8",
    )

    settings = load_env(config_path)

    assert settings.base_url == TEST_BASE_URL
    assert settings.cert == "/test/cert.pem"
    assert settings.client_secret == "file-secret"


def test_missing_configuration_values_are_rejected(tmp_path, monkeypatch):
    for key in REQUIRED_KEYS:
        monkeypatch.delenv(key, raising=False)
    config_path = tmp_path / ".env.test"
    config_path.write_text(f"BASE_URL={TEST_BASE_URL}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Missing configuration values"):
        load_env(config_path)
