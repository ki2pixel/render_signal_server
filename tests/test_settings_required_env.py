import importlib
import sys

import pytest


_REQUIRED_ENV = {
    "FLASK_SECRET_KEY": "test-secret-key",
    "TRIGGER_PAGE_PASSWORD": "test-dashboard-password",
    "PROCESS_API_TOKEN": "test-process-api-token",
    "WEBHOOK_URL": "https://example.com/webhook",
}


@pytest.mark.unit
def test_settings_import_succeeds_when_required_env_present(monkeypatch):
    for k, v in _REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)

    sys.modules.pop("config.settings", None)

    settings = importlib.import_module("config.settings")

    assert settings.FLASK_SECRET_KEY == _REQUIRED_ENV["FLASK_SECRET_KEY"]
    assert settings.EXPECTED_API_TOKEN == _REQUIRED_ENV["PROCESS_API_TOKEN"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "missing_env",
    [
        "FLASK_SECRET_KEY",
        "TRIGGER_PAGE_PASSWORD",
        "PROCESS_API_TOKEN",
        "WEBHOOK_URL",
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
