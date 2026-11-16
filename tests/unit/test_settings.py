"""Synthetic environment checks through the actual CLI boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_doctor(tmp_path: Path, overrides: dict[str, str] | None = None):
    env = {key: value for key, value in os.environ.items() if not key.startswith("BUSCONFIG_")}
    env.update(BUSCONFIG_DATA_DIR=str(tmp_path / "data"))
    env.update(overrides or {})
    return subprocess.run(
        [sys.executable, "-m", "busconfig.cli", "doctor"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_doctor_redacts_credentials(tmp_path):
    secrets = {
        "BUSCONFIG_MODEL_API_KEY": "synthetic-api-secret-123",
        "BUSCONFIG_DATABASE_URL": "postgresql://demo:synthetic-db-secret@localhost/demo",
        "BUSCONFIG_AUTH_SECRET": "synthetic-auth-secret-456",
    }
    result = run_doctor(tmp_path, secrets)
    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    assert result.stdout.strip(), "doctor must emit its diagnostic report"
    for secret in (*secrets.values(), "synthetic-db-secret"):
        assert secret not in output
    report = json.loads(result.stdout)
    assert report["model_mode"] == "disabled"
    assert report["data_dir"]["writable"] is True
    assert report["versions"]["python"]
    assert report["versions"]["busconfig"]


def test_doctor_disabled_mode_needs_no_model_settings(tmp_path):
    result = run_doctor(tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["model_mode"] == "disabled"
    assert Path(report["data_dir"]["path"]) == tmp_path / "data"
    assert list((tmp_path / "data").iterdir()) == []


@pytest.mark.parametrize(
    "setting,value",
    [
        ("BUSCONFIG_MODEL_MODE", "unsupported"),
        ("BUSCONFIG_MODEL_TIMEOUT_SECONDS", "0"),
        ("BUSCONFIG_MODEL_TIMEOUT_SECONDS", "nan"),
        ("BUSCONFIG_MODEL_TRANSPORT_RETRIES", "-1"),
        ("BUSCONFIG_MODEL_SCHEMA_REPAIRS", "-1"),
        ("BUSCONFIG_EVIDENCE_FOLLOWUPS", "-1"),
        ("BUSCONFIG_MODEL_CONCURRENCY", "0"),
        ("BUSCONFIG_PREPARATION_LIMIT", "0"),
        ("BUSCONFIG_SEARCH_MAX_NODES", "0"),
        ("BUSCONFIG_SEARCH_TIMEOUT_SECONDS", "inf"),
        ("BUSCONFIG_SEARCH_TIMEOUT_SECONDS", "not-a-number"),
        ("BUSCONFIG_DATA_DIR", ""),
    ],
)
def test_doctor_rejects_invalid_settings_without_echoing_values(tmp_path, setting, value):
    secret = "synthetic-sensitive-input-789"
    result = run_doctor(tmp_path, {setting: value, "BUSCONFIG_MODEL_API_KEY": secret})
    assert result.returncode == 2
    assert setting in result.stderr
    assert secret not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "settings",
    [
        {"BUSCONFIG_MODEL_MODE": "http"},
        {
            "BUSCONFIG_MODEL_MODE": "http",
            "BUSCONFIG_MODEL_BASE_URL": "http://127.0.0.1:8001/v1",
            "BUSCONFIG_MODEL_NAME": "replace-with-served-model-name",
        },
        {
            "BUSCONFIG_MODEL_MODE": "http",
            "BUSCONFIG_MODEL_BASE_URL": "file:///synthetic-secret",
            "BUSCONFIG_MODEL_NAME": "synthetic-model",
        },
        {
            "BUSCONFIG_MODEL_MODE": "http",
            "BUSCONFIG_MODEL_BASE_URL": "http://127.0.0.1:8001/v1",
            "BUSCONFIG_MODEL_NAME": "  replace-with-served-model-name  ",
        },
    ],
)
def test_doctor_http_settings_must_be_explicit_and_valid(tmp_path, settings):
    result = run_doctor(tmp_path, settings)
    assert result.returncode == 2
    assert "BUSCONFIG_MODEL" in result.stderr
    assert "synthetic-secret" not in result.stderr


def test_doctor_checks_configuration_without_contacting_endpoint(tmp_path):
    result = run_doctor(
        tmp_path,
        {
            "BUSCONFIG_MODEL_MODE": "http",
            "BUSCONFIG_MODEL_BASE_URL": "http://demo:synthetic-url-secret@127.0.0.1:1/v1?key=synthetic-query-secret",
            "BUSCONFIG_MODEL_NAME": "synthetic-model",
        },
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["model_mode"] == "http"
    assert "synthetic-url-secret" not in result.stdout + result.stderr
    assert "synthetic-query-secret" not in result.stdout + result.stderr


def test_doctor_reports_unusable_path_as_operational_failure(tmp_path):
    occupied = tmp_path / "occupied"
    occupied.write_text("synthetic file", encoding="utf-8")
    result = run_doctor(tmp_path, {"BUSCONFIG_DATA_DIR": str(occupied / "data")})
    assert result.returncode == 3
    assert json.loads(result.stdout)["data_dir"]["writable"] is False
    assert "Traceback" not in result.stderr


def test_doctor_redacts_secrets_embedded_in_diagnostic_path(tmp_path):
    secret = 'synthetic-secret-"quoted"'
    result = run_doctor(
        tmp_path,
        {
            "BUSCONFIG_MODEL_API_KEY": secret,
            "BUSCONFIG_DATA_DIR": str(tmp_path / secret),
        },
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert secret not in report["data_dir"]["path"]
    assert "[REDACTED]" in report["data_dir"]["path"]
    assert (tmp_path / secret).is_dir()


def test_doctor_validation_errors_do_not_echo_sensitive_input(tmp_path):
    secret = "synthetic-invalid-setting-secret"
    result = run_doctor(tmp_path, {"BUSCONFIG_MODEL_CONCURRENCY": secret})
    assert result.returncode == 2
    assert secret not in result.stdout + result.stderr
    assert "BUSCONFIG_MODEL_CONCURRENCY" in result.stderr


@pytest.mark.parametrize("mode", ["disabled", "fake"])
def test_doctor_allows_zero_optional_budgets_without_endpoint(tmp_path, mode):
    result = run_doctor(
        tmp_path,
        {
            "BUSCONFIG_MODEL_MODE": mode,
            "BUSCONFIG_MODEL_TRANSPORT_RETRIES": "0",
            "BUSCONFIG_MODEL_SCHEMA_REPAIRS": "0",
            "BUSCONFIG_EVIDENCE_FOLLOWUPS": "0",
        },
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["model_mode"] == mode
