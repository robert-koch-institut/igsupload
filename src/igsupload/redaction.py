from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit


REDACTED = "[REDACTED]"
PRESIGNED_QUERY_REDACTED = "[PRESIGNED-QUERY-REDACTED]"

_SENSITIVE_KEYS = {
    "accesstoken",
    "authorization",
    "bearertoken",
    "clientsecret",
    "idtoken",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
}

_SIGNED_QUERY_KEYS = {
    "awsaccesskeyid",
    "googleaccessid",
    "signature",
    "sig",
    "token",
    "x-amz-credential",
    "x-amz-security-token",
    "x-amz-signature",
    "x-goog-credential",
    "x-goog-signature",
}

_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?"
    r"-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    flags=re.IGNORECASE | re.DOTALL,
)
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)\bAuthorization\s*:\s*(?:Bearer|Basic)\s+[^\s,;]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b("
    r"client[_-]?secret|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|password|private[_-]?key"
    r")(\s*[:=]\s*)([^\s,;&]+)"
)
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", flags=re.IGNORECASE)


def redact_sensitive_data(value: Any) -> Any:
    """Return a recursively redacted copy of JSON-like data."""
    if isinstance(value, Mapping):
        return {
            key: (
                REDACTED
                if _is_sensitive_key(key)
                else redact_sensitive_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    """Redact credentials, private keys and signed URLs from free text."""
    text = str(value)
    text = _PRIVATE_KEY_PATTERN.sub("[PRIVATE-KEY-REDACTED]", text)
    text = _AUTHORIZATION_PATTERN.sub("Authorization: [REDACTED]", text)
    text = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    text = _SENSITIVE_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        text,
    )
    return _URL_PATTERN.sub(_redact_url_match, text)


def _is_sensitive_key(value: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(value).lower())
    return normalized in _SENSITIVE_KEYS


def _redact_url_match(match: re.Match[str]) -> str:
    candidate = match.group(0)
    url, trailing_punctuation = _split_trailing_punctuation(candidate)
    parsed = urlsplit(url)
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query)}
    if not query_keys.intersection(_SIGNED_QUERY_KEYS):
        return candidate

    redacted_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        redacted_url += f"?{PRESIGNED_QUERY_REDACTED}"
    return redacted_url + trailing_punctuation


def _split_trailing_punctuation(value: str) -> tuple[str, str]:
    trailing = ""
    while value and value[-1] in ".,;:)":
        trailing = value[-1] + trailing
        value = value[:-1]
    return value, trailing
