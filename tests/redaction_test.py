from igsupload.redaction import (
    PRESIGNED_QUERY_REDACTED,
    REDACTED,
    redact_sensitive_data,
    redact_text,
)


PRESIGNED_URL = (
    "https://uploads.example.org/reads/sample.fastq"
    "?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=AKIAEXAMPLE%2F20260717%2Feu-central-1%2Fs3%2Faws4_request"
    "&X-Amz-Signature=very-secret-signature"
)


def test_nested_sensitive_fields_are_redacted_without_mutating_input():
    payload = {
        "access_token": "access-value",
        "nested": {
            "clientSecret": "client-value",
            "Authorization": "Bearer header-value",
            "safe": "visible",
        },
        "items": [{"refresh-token": "refresh-value"}],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted == {
        "access_token": REDACTED,
        "nested": {
            "clientSecret": REDACTED,
            "Authorization": REDACTED,
            "safe": "visible",
        },
        "items": [{"refresh-token": REDACTED}],
    }
    assert payload["access_token"] == "access-value"
    assert payload["nested"]["clientSecret"] == "client-value"


def test_free_text_redacts_bearer_token_private_key_and_assignments():
    private_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        "super-secret-key-material\n"
        "-----END PRIVATE KEY-----"
    )
    text = (
        "Authorization: Bearer abc.def.ghi; "
        "client_secret=client-value; "
        f"key={private_key}"
    )

    redacted = redact_text(text)

    assert "abc.def.ghi" not in redacted
    assert "client-value" not in redacted
    assert "super-secret-key-material" not in redacted
    assert "Authorization: [REDACTED]" in redacted
    assert "client_secret=[REDACTED]" in redacted
    assert "[PRIVATE-KEY-REDACTED]" in redacted


def test_presigned_url_keeps_location_but_removes_complete_query():
    text = f"Upload failed for {PRESIGNED_URL}. Please retry."

    redacted = redact_text(text)

    assert PRESIGNED_URL not in redacted
    assert "AKIAEXAMPLE" not in redacted
    assert "very-secret-signature" not in redacted
    assert (
        "https://uploads.example.org/reads/sample.fastq"
        f"?{PRESIGNED_QUERY_REDACTED}"
    ) in redacted
    assert redacted.endswith(". Please retry.")


def test_normal_url_is_not_modified():
    url = "https://demis.rki.de/fhir/StructureDefinition/Patient"
    assert redact_text(url) == url
