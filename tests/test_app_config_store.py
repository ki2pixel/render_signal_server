import json

import pytest

from config import app_config_store


@pytest.mark.unit
def test_get_config_json_redis_first_returns_redis_value(monkeypatch, mock_redis, tmp_path):
    # Given: Redis contains a config value and a file fallback exists with different content
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid/0")
    monkeypatch.setenv("CONFIG_STORE_MODE", "redis_first")
    monkeypatch.setenv("CONFIG_STORE_REDIS_PREFIX", "testprefix:")
    monkeypatch.delenv("CONFIG_STORE_DISABLE_REDIS", raising=False)

    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", mock_redis)

    mock_redis.set("testprefix:mycfg", json.dumps({"value": "from_redis"}))

    fallback_path = tmp_path / "fallback.json"
    fallback_path.write_text(json.dumps({"value": "from_file"}), encoding="utf-8")

    # When: reading config via store
    data = app_config_store.get_config_json("mycfg", file_fallback=fallback_path)

    # Then: Redis wins
    assert data["value"] == "from_redis"


@pytest.mark.unit
def test_set_config_json_redis_first_writes_to_redis(monkeypatch, mock_redis):
    # Given: Redis-first store
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid/0")
    monkeypatch.setenv("CONFIG_STORE_MODE", "redis_first")
    monkeypatch.setenv("CONFIG_STORE_REDIS_PREFIX", "testprefix:")
    monkeypatch.delenv("CONFIG_STORE_DISABLE_REDIS", raising=False)

    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", mock_redis)

    # When: writing config
    ok = app_config_store.set_config_json("mycfg", {"x": 1})

    # Then: write succeeded and value is in Redis
    assert ok is True
    raw = mock_redis.get("testprefix:mycfg")
    assert isinstance(raw, str)
    assert json.loads(raw) == {"x": 1}


@pytest.mark.unit
def test_get_config_json_falls_back_to_file_when_redis_disabled(monkeypatch, tmp_path):
    # Given: Redis disabled and file exists
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("CONFIG_STORE_DISABLE_REDIS", "1")
    monkeypatch.delenv("EXTERNAL_CONFIG_BASE_URL", raising=False)
    monkeypatch.delenv("CONFIG_API_TOKEN", raising=False)

    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", None)

    fallback_path = tmp_path / "fallback.json"
    fallback_path.write_text(json.dumps({"value": "from_file"}), encoding="utf-8")

    # When: reading config
    data = app_config_store.get_config_json("mycfg", file_fallback=fallback_path)

    # Then: file is used
    assert data["value"] == "from_file"


@pytest.mark.unit
def test_get_config_json_php_first_uses_redis_if_php_unavailable(monkeypatch, mock_redis):
    # Given: php_first mode, PHP is not configured, Redis is available
    monkeypatch.setenv("REDIS_URL", "redis://example.invalid/0")
    monkeypatch.setenv("CONFIG_STORE_MODE", "php_first")
    monkeypatch.setenv("CONFIG_STORE_REDIS_PREFIX", "testprefix:")
    monkeypatch.delenv("EXTERNAL_CONFIG_BASE_URL", raising=False)
    monkeypatch.delenv("CONFIG_API_TOKEN", raising=False)
    monkeypatch.delenv("CONFIG_STORE_DISABLE_REDIS", raising=False)

    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", mock_redis)
    mock_redis.set("testprefix:mycfg", json.dumps({"value": "from_redis"}))

    # When: reading config
    data = app_config_store.get_config_json("mycfg")

    # Then: Redis provides the value
    assert data["value"] == "from_redis"


@pytest.mark.unit
def test_set_config_json_falls_back_to_file_when_redis_disabled(monkeypatch, tmp_path):
    # Given: Redis disabled and a file fallback target is provided
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("CONFIG_STORE_DISABLE_REDIS", "1")
    monkeypatch.delenv("EXTERNAL_CONFIG_BASE_URL", raising=False)
    monkeypatch.delenv("CONFIG_API_TOKEN", raising=False)
    monkeypatch.setattr(app_config_store, "_REDIS_CLIENT", None)

    fallback_path = tmp_path / "fallback.json"
    assert fallback_path.exists() is False

    # When: writing config
    ok = app_config_store.set_config_json("mycfg", {"value": "from_file"}, file_fallback=fallback_path)

    # Then: file is created and contains the payload
    assert ok is True
    assert fallback_path.exists() is True
    loaded = json.loads(fallback_path.read_text(encoding="utf-8"))
    assert loaded["value"] == "from_file"
