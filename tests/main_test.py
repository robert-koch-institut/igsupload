import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.igsupload.main import app

runner = CliRunner()


def test_help_command():
    result = runner.invoke(app, ["intro"])
    assert result.exit_code == 0
    assert "IGS Uploader - Help & Troubleshooting" in result.output
    assert "Usage:" in result.output
    assert "igsupload --csv ./test_data/metadata/test_data.csv" in result.output


def test_root_without_csv_requires_flag():
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Error: --csv is required." in result.output


def test_root_with_nonexistent_csv_path():
    result = runner.invoke(app, ["--csv", "/nicht/vorhanden.csv"])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_root_with_valid_path(monkeypatch):
    # Temporäre CSV erzeugen
    with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
        path = tmp.name

        called = {}

        def fake_start(p):
            called["was_called"] = True
            called["path"] = p

        monkeypatch.setattr("src.igsupload.main.start", fake_start)

        result = runner.invoke(app, ["--csv", path])
        assert result.exit_code == 0
        assert "load CSV-file" in result.output
        assert called.get("was_called") is True
        assert called.get("path") == str(Path(path).expanduser().resolve())


def test_root_with_valid_path_and_config(monkeypatch, tmp_path):
    # Temp .csv und .env
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("colA\nval\n")

    env_file = tmp_path / ".env"
    env_file.write_text("BASE_URL=https://example.org\n")

    called = {}

    def fake_start(p):
        called["was_called"] = True
        called["path"] = p

    monkeypatch.setattr("src.igsupload.main.start", fake_start)

    result = runner.invoke(app, ["--csv", str(csv_file), "--config", str(env_file)])
    assert result.exit_code == 0
    assert "load CSV-file" in result.output
    assert called.get("was_called") is True
    assert called.get("path") == str(csv_file.resolve())
