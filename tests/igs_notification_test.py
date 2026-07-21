from dataclasses import fields
from unittest import mock

import igsupload.config as config
import igsupload.igs_notification as igs_notification
from igsupload.extract_csv import CsvRow


def _row(**overrides) -> CsvRow:
    values = {field.name: "" for field in fields(CsvRow)}
    values.update(
        {
            "DEMIS_NOTIFICATION_ID": "6cb7099d-8d53-4ee4-96ca-c55761b347d4",
            "STATUS": "final",
        }
    )
    values.update(overrides)
    return CsvRow(**values)


def test_send_notification_posts_current_bundle_to_demis(monkeypatch):
    bundle = {"resourceType": "Bundle", "type": "document"}
    row = _row()
    response = mock.Mock(status_code=200)
    post = mock.Mock(return_value=response)

    monkeypatch.setattr(
        igs_notification,
        "build_notification_bundle",
        mock.Mock(return_value=bundle),
    )
    monkeypatch.setattr(igs_notification.requests, "post", post)
    monkeypatch.setattr(config, "BASE_URL", "https://demis.example.org/api")
    monkeypatch.setattr(config, "CERT", "/cert.pem")
    monkeypatch.setattr(config, "KEY", "/key.pem")
    monkeypatch.setattr(igs_notification.token_module, "current_token", "token-value")

    result = igs_notification.send_notification(
        row,
        ["document-1", "document-2"],
    )

    assert result is response
    igs_notification.build_notification_bundle.assert_called_once_with(
        row=row,
        doc_ids=["document-1", "document-2"],
    )
    post.assert_called_once_with(
        "https://demis.example.org/api/v5/fhir/$process-notification-sequence",
        headers={
            "Authorization": "Bearer token-value",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=bundle,
        cert=("/cert.pem", "/key.pem"),
    )


def test_send_notification_returns_error_response_for_central_handling(monkeypatch):
    response = mock.Mock(status_code=422)
    post = mock.Mock(return_value=response)
    monkeypatch.setattr(
        igs_notification,
        "build_notification_bundle",
        mock.Mock(return_value={"resourceType": "Bundle"}),
    )
    monkeypatch.setattr(igs_notification.requests, "post", post)
    monkeypatch.setattr(config, "BASE_URL", "https://demis.example.org/api")
    monkeypatch.setattr(config, "CERT", "/cert.pem")
    monkeypatch.setattr(config, "KEY", "/key.pem")
    monkeypatch.setattr(igs_notification.token_module, "current_token", "token-value")

    result = igs_notification.send_notification(
        _row(),
        ["document-1", "document-2"],
    )

    assert result is response
    response.json.assert_not_called()
    response.raise_for_status.assert_not_called()
