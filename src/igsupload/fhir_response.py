from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping

import typer

from igsupload.redaction import redact_sensitive_data, redact_text


OutputFunction = Callable[[str], None]


@dataclass(frozen=True)
class OperationOutcomeIssue:
    """Relevant information from a single ``OperationOutcome.issue``."""

    severity: str | None
    code: str | None
    diagnostics: str | None
    details: str | None
    expressions: tuple[str, ...]
    locations: tuple[str, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        """Return expression paths, falling back to legacy location paths."""
        return self.expressions or self.locations


@dataclass(frozen=True)
class FhirResponse:
    """Parsed response data while retaining the complete server payload."""

    status_code: int
    payload: Any | None
    text: str
    issues: tuple[OperationOutcomeIssue, ...]

    @property
    def is_operation_outcome(self) -> bool:
        return isinstance(self.payload, Mapping) and (
            self.payload.get("resourceType") == "OperationOutcome"
        )


def parse_fhir_response(response: Any) -> FhirResponse:
    """Parse JSON if available and extract all OperationOutcome issues."""
    try:
        payload = response.json()
    except (ValueError, TypeError):
        payload = None

    issues: tuple[OperationOutcomeIssue, ...] = ()
    if isinstance(payload, Mapping) and payload.get("resourceType") == "OperationOutcome":
        raw_issues = payload.get("issue")
        if isinstance(raw_issues, list):
            issues = tuple(
                _parse_issue(issue)
                for issue in raw_issues
                if isinstance(issue, Mapping)
            )

    return FhirResponse(
        status_code=int(response.status_code),
        payload=payload,
        text=str(getattr(response, "text", "") or ""),
        issues=issues,
    )


def report_fhir_error(
    response: FhirResponse,
    *,
    resource: str,
    expected_profile: str | None = None,
    output: OutputFunction | None = None,
    outcome_directory: Path | None = None,
) -> Path | None:
    """Print a readable error summary and persist a complete OperationOutcome."""
    output = output or print
    output(
        typer.style(
            f"FHIR request failed with HTTP status {response.status_code}.",
            fg=typer.colors.RED,
        )
    )
    output(f"Resource: {redact_text(resource)}")
    if expected_profile:
        output(f"Expected profile: {redact_text(expected_profile)}")

    if response.is_operation_outcome:
        if response.issues:
            for number, issue in enumerate(response.issues, start=1):
                output(f"Issue {number}:")
                output(_format_severity(issue.severity))
                output(f"  Code: {_safe_text(issue.code)}")
                output(f"  Path: {_safe_text(', '.join(issue.paths))}")
                output(f"  Details: {_safe_text(issue.details)}")
                output(f"  Diagnostics: {_safe_text(issue.diagnostics)}")
        else:
            output("OperationOutcome contains no issues.")

        try:
            outcome_path = save_operation_outcome(
                response.payload,
                directory=outcome_directory,
                resource=resource,
            )
        except OSError as error:
            output(
                typer.style(
                    f"Complete OperationOutcome could not be saved: {error}",
                    fg=typer.colors.RED,
                )
            )
            return None

        _report_saved_operation_outcome(outcome_path, output=output)
        return outcome_path

    if response.payload is not None:
        output("Server response:")
        output(
            json.dumps(
                redact_sensitive_data(response.payload),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif response.text:
        output("Server response:")
        output(redact_text(response.text))
    else:
        output("The server returned no response body.")
    return None


def save_operation_outcome(
    payload: Any,
    *,
    directory: Path | None = None,
    resource: str = "FHIR resource",
) -> Path:
    """Save a redacted OperationOutcome without overwriting analysis files."""
    if directory is None:
        from igsupload.igsupload_logger import get_logging_directory

        directory = get_logging_directory()
    else:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H%M%S")
    resource_name = _filename_slug(redact_text(resource))
    filename_stem = f"operation-outcome_{resource_name}_{timestamp}"
    path, descriptor = _create_unique_file(directory, filename_stem)

    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        json.dump(
            redact_sensitive_data(payload),
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")

    return path.resolve()


def _create_unique_file(directory: Path, filename_stem: str) -> tuple[Path, int]:
    counter = 1
    while True:
        suffix = "" if counter == 1 else f"_{counter}"
        path = directory / f"{filename_stem}{suffix}.json"
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            return path, descriptor
        except FileExistsError:
            counter += 1


def _filename_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "fhir-resource"


def _report_saved_operation_outcome(
    path: Path,
    *,
    output: OutputFunction,
) -> None:
    heading = typer.style(
        "=== Complete OperationOutcome available ===",
        fg=typer.colors.YELLOW,
        bold=True,
    )
    output("")
    output(heading)
    output("The complete server response was sanitized and saved for analysis:")
    output(f"  {path}")
    output("Sensitive access values were redacted before writing the file.")
    output("Open this JSON file to inspect all OperationOutcome issues.")
    output(typer.style("=" * 43, fg=typer.colors.YELLOW, bold=True))
    output("")


def _format_severity(severity: str | None) -> str:
    value = severity or "not provided"
    color = {
        "fatal": typer.colors.RED,
        "error": typer.colors.RED,
        "warning": typer.colors.YELLOW,
    }.get(value.lower())
    text = f"  Severity: {value}"
    return typer.style(text, fg=color) if color else text


def _safe_text(value: str | None) -> str:
    return redact_text(value) if value else "not provided"


def _parse_issue(issue: Mapping[str, Any]) -> OperationOutcomeIssue:
    details = issue.get("details")
    details_text = details.get("text") if isinstance(details, Mapping) else None

    return OperationOutcomeIssue(
        severity=_optional_string(issue.get("severity")),
        code=_optional_string(issue.get("code")),
        diagnostics=_optional_string(issue.get("diagnostics")),
        details=_optional_string(details_text),
        expressions=_string_tuple(issue.get("expression")),
        locations=_string_tuple(issue.get("location")),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        text
        for item in value
        if (text := _optional_string(item)) is not None
    )
