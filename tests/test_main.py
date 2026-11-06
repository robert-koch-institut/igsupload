from unittest import mock

from typer.testing import CliRunner

import igsupload.main as main_module
from tests.conftest import TEST_BASE_URL

runner = CliRunner()


def test_cli_runs_workflow_with_test_configuration(
    tmp_path,
    monkeypatch,
    test_settings,
):
    csv_path = tmp_path / "metadata.csv"
    csv_path.write_text("FILE_1_NAME;FILE_2_NAME\n", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    api = mock.Mock()
    token_provider = mock.Mock()
    report = mock.Mock(file_path=log_dir / "igsupload_report.csv")
    start = mock.Mock(return_value=True)

    monkeypatch.setattr(main_module, "setup_logging", lambda path: log_dir)
    monkeypatch.setattr(main_module, "load_env", lambda path=None: test_settings)
    token_provider_factory = mock.Mock(return_value=token_provider)
    api_factory = mock.Mock(return_value=api)
    monkeypatch.setattr(main_module, "TokenProvider", token_provider_factory)
    monkeypatch.setattr(main_module, "ApiClient", api_factory)
    monkeypatch.setattr(main_module, "UploadReport", mock.Mock(return_value=report))
    monkeypatch.setattr(main_module, "start", start)

    result = runner.invoke(main_module.app, ["--csv", str(csv_path)])

    assert result.exit_code == 0
    start.assert_called_once_with(
        csv_path.resolve(),
        TEST_BASE_URL,
        api,
        report,
    )
    token_provider_factory.assert_called_once_with(test_settings)
    api_factory.assert_called_once_with(
        base_url=test_settings.base_url,
        token_provider=token_provider,
        pkcs12_path=test_settings.pkcs12_path,
        password=test_settings.password,
    )
    api.close.assert_called_once_with()


def test_cli_returns_failure_when_any_metadata_row_failed(
    tmp_path,
    monkeypatch,
    test_settings,
):
    csv_path = tmp_path / "metadata.csv"
    csv_path.write_text("FILE_1_NAME;FILE_2_NAME\n", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    api = mock.Mock()
    token_provider = mock.Mock()
    monkeypatch.setattr(main_module, "setup_logging", lambda path: log_dir)
    monkeypatch.setattr(main_module, "load_env", lambda path=None: test_settings)
    monkeypatch.setattr(
        main_module,
        "TokenProvider",
        mock.Mock(return_value=token_provider),
    )
    monkeypatch.setattr(main_module, "ApiClient", mock.Mock(return_value=api))
    monkeypatch.setattr(main_module, "UploadReport", mock.Mock())
    monkeypatch.setattr(main_module, "start", mock.Mock(return_value=False))

    result = runner.invoke(main_module.app, ["--csv", str(csv_path)])

    assert result.exit_code == 1
    api.close.assert_called_once_with()
