import json

import pytest

from config import app_config_store
from scripts import check_config_store


@pytest.fixture(autouse=True)
def reset_store_client(monkeypatch):
    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", None)


def _setup_env(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid/0")
    monkeypatch.setenv("CONFIG_STORE_MODE", "redis_first")
    monkeypatch.setenv("CONFIG_STORE_REDIS_PREFIX", "testprefix:")
    monkeypatch.delenv("CONFIG_STORE_DISABLE_REDIS", raising=False)


@pytest.mark.unit
def test_run_returns_zero_when_all_keys_valid(monkeypatch, mock_redis):
    _setup_env(monkeypatch)
    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", mock_redis)

    mock_redis.set(
        "testprefix:magic_link_tokens",
        json.dumps({"token_a": {"created_at": "2026-01-01T00:00:00Z"}}),
    )
    mock_redis.set(
        "testprefix:polling_config",
        json.dumps({"_updated_at": "2026-01-19T00:00:00Z", "enabled": True}),
    )
    mock_redis.set(
        "testprefix:processing_prefs",
        json.dumps({"_updated_at": "2026-01-19T00:00:00Z", "rules": []}),
    )
    mock_redis.set(
        "testprefix:webhook_config",
        json.dumps({"_updated_at": "2026-01-19T00:00:00Z", "webhook_url": "https://x"}),
    )

    mock_redis.set(
        "testprefix:routing_rules",
        json.dumps({"_updated_at": "2026-01-19T00:00:00Z", "rules": []}),
    )

    exit_code = check_config_store._run(check_config_store.KEY_CHOICES, raw=False)

    assert exit_code == 0


@pytest.mark.unit
def test_run_allows_empty_routing_rules(monkeypatch, mock_redis):
    _setup_env(monkeypatch)
    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", mock_redis)

    mock_redis.set(
        "testprefix:routing_rules",
        json.dumps({}),
    )

    exit_code = check_config_store._run(("routing_rules",), raw=False)

    assert exit_code == 0


@pytest.mark.unit
def test_run_returns_one_when_missing_updated_at(monkeypatch, mock_redis):
    _setup_env(monkeypatch)
    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", mock_redis)

    mock_redis.set(
        "testprefix:processing_prefs",
        json.dumps({"rules": []}),
    )

    exit_code = check_config_store._run(("processing_prefs",), raw=False)

    assert exit_code == 1
