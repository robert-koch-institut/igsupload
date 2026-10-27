from dataclasses import fields

import pytest
import requests

from igsupload.config import REQUIRED_KEYS, Settings
from igsupload.utils.extract_csv import CsvRow

TEST_BASE_URL = (
    "https://test.demis.rki.de/qs/surveillance/notification-sequence"
)
TEST_TOKEN_URL = "https://token.test.invalid/oauth/token"


@pytest.fixture(autouse=True)
def fixed_test_environment(monkeypatch):
    """Keep unit tests independent from a developer's local .env file."""
    values = {
        "CERT_URL": "/tmp/test-cert.pem",
        "KEY_URL": "/tmp/test-key.pem",
        "CLIENT_ID": "test-client",
        "CLIENT_SECRET": "test-secret",
        "USERNAME": "test-user",
        "BASE_URL": TEST_BASE_URL,
        "TOKEN_URL": TEST_TOKEN_URL,
    }
    for key in REQUIRED_KEYS:
        monkeypatch.setenv(key, values[key])

    def reject_network_request(*args, **kwargs):
        raise AssertionError("Unit tests must not perform real network requests")

    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        reject_network_request,
    )


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        cert="/tmp/test-cert.pem",
        key="/tmp/test-key.pem",
        client_id="test-client",
        client_secret="test-secret",
        username="test-user",
        base_url=TEST_BASE_URL,
        token_url=TEST_TOKEN_URL,
    )


@pytest.fixture
def csv_row_factory():
    def create_row(**overrides) -> CsvRow:
        values = {field.name: "" for field in fields(CsvRow)}
        values.update(
            {
                "MELDETATBESTAND": "SPNP",
                "SPECIES_CODE": "3092008",
                "SPECIES": "Staphylococcus aureus",
                "LAB_SEQUENCE_ID": "sample-1",
                "DEMIS_NOTIFICATION_ID": (
                    "6cb7099d-8d53-4ee4-96ca-c55761b347d4"
                ),
                "STATUS": "final",
                "DATE_OF_SAMPLING": "2025-01-01",
                "DATE_OF_RECEIVING": "2025-01-02",
                "DATE_OF_SEQUENCING": "2025-01-03",
                "SEQUENCING_INSTRUMENT": "NextSeq 550",
                "SEQUENCING_PLATFORM": "ILLUMINA",
                "ADAPTER": "adapter-1+adapter-2",
                "PRIMER_SCHEME": "ARTICv4.1",
                "SEQUENCING_STRATEGY": "WGS",
                "ISOLATION_SOURCE_CODE": "258604001",
                "ISOLATION_SOURCE": "Skin specimen",
                "HOST_SEX": "male",
                "HOST_BIRTH_MONTH": "12",
                "HOST_BIRTH_YEAR": "2000",
                "SEQUENCING_REASON": "random",
                "GEOGRAPHIC_LOCATION": "104",
                "SEQUENCING_LAB_DEMIS_LAB_ID": "test-lab",
                "SEQUENCING_LAB_NAME": "Test laboratory",
                "SEQUENCING_LAB_ADDRESS": "Test street 1",
                "SEQUENCING_LAB_POSTAL_CODE": "10115",
                "SEQUENCING_LAB_CITY": "Berlin",
                "SEQUENCING_LAB_FEDERAL_STATE": "DE-BE",
                "SEQUENCING_LAB_EMAIL": "test@example.org",
            }
        )
        values.update(overrides)
        return CsvRow(**values)

    return create_row
