import importlib
import sys

import pytest


_REQUIRED_ENV = {
    "FLASK_SECRET_KEY": "test-secret-key",
    "TRIGGER_PAGE_PASSWORD": "test-dashboard-password",
    "EMAIL_ADDRESS": "test@example.com",
    "EMAIL_PASSWORD": "test-email-password",
    "IMAP_SERVER": "imap.example.com",
    "PROCESS_API_TOKEN": "test-process-api-token",
    "WEBHOOK_URL": "https://example.com/webhook",
    "MAKECOM_API_KEY": "test-makecom-api-key",
}


@pytest.mark.unit
def test_settings_import_succeeds_when_required_env_present(monkeypatch):
    for k, v in _REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)

    sys.modules.pop("config.settings", None)

    settings = importlib.import_module("config.settings")

    assert settings.FLASK_SECRET_KEY == _REQUIRED_ENV["FLASK_SECRET_KEY"]
    assert settings.EMAIL_ADDRESS == _REQUIRED_ENV["EMAIL_ADDRESS"]
    assert settings.IMAP_SERVER == _REQUIRED_ENV["IMAP_SERVER"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing_env",
    [
        "FLASK_SECRET_KEY",
        "TRIGGER_PAGE_PASSWORD",
        "EMAIL_ADDRESS",
        "EMAIL_PASSWORD",
        "IMAP_SERVER",
        "PROCESS_API_TOKEN",
        "WEBHOOK_URL",
        "MAKECOM_API_KEY",
    ],
)
def test_settings_import_raises_when_required_env_missing(monkeypatch, missing_env):
    for k, v in _REQUIRED_ENV.items():
        if k != missing_env:
            monkeypatch.setenv(k, v)

    monkeypatch.delenv(missing_env, raising=False)
    sys.modules.pop("config.settings", None)

    with pytest.raises(ValueError) as exc:
        importlib.import_module("config.settings")

    assert f"Missing required environment variable: {missing_env}" in str(exc.value)

    sys.modules.pop("config.settings", None)
