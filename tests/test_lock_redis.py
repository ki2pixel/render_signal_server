"""Unit tests for Redis-based singleton lock fallback."""

import logging
import os
import sys
from types import SimpleNamespace

import pytest

from background import lock


@pytest.mark.unit
def test_acquire_singleton_lock_uses_redis_when_redis_url_present(monkeypatch, tmp_path):
    # // Given: REDIS_URL is present and Redis SET returns True
    monkeypatch.setenv("REDIS_URL", "redis://example/0")
    lock.REDIS_LOCK_CLIENT = None
    lock.REDIS_LOCK_TOKEN = None

    calls = {}

    class FakeClient:
        def set(self, key, value, nx, ex):
            calls["key"] = key
            calls["value"] = value
            calls["nx"] = nx
            calls["ex"] = ex
            return True

    fake_client = FakeClient()
    fake_redis_module = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda url: fake_client)
    )
    monkeypatch.setitem(sys.modules, "redis", fake_redis_module)

    lock_file = tmp_path / "poller.lock"

    # // When: acquiring the singleton lock
    ok = lock.acquire_singleton_lock(str(lock_file))

    # // Then: Redis path is used and file lock is not created
    assert ok is True
    assert calls["key"] == "render_signal:poller_lock"
    assert calls["nx"] is True
    assert calls["ex"] == 300
    assert str(os.getpid()) in str(calls["value"])
    assert not lock_file.exists()


@pytest.mark.unit
def test_acquire_singleton_lock_redis_returns_false(monkeypatch, tmp_path):
    # // Given: REDIS_URL is present and Redis SET returns False (already locked)
    monkeypatch.setenv("REDIS_URL", "redis://example/0")
    lock.REDIS_LOCK_CLIENT = None
    lock.REDIS_LOCK_TOKEN = None

    class FakeClient:
        def set(self, key, value, nx, ex):
            return False

    fake_client = FakeClient()
    fake_redis_module = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda url: fake_client)
    )
    monkeypatch.setitem(sys.modules, "redis", fake_redis_module)

    lock_file = tmp_path / "poller.lock"

    # // When: acquiring the singleton lock
    ok = lock.acquire_singleton_lock(str(lock_file))

    # // Then: lock is not acquired and file lock is not used
    assert ok is False
    assert not lock_file.exists()


@pytest.mark.unit
def test_acquire_singleton_lock_redis_exception_falls_back_to_file_lock(monkeypatch, tmp_path, caplog):
    # // Given: REDIS_URL is present but Redis raises
    monkeypatch.setenv("REDIS_URL", "redis://example/0")
    lock.REDIS_LOCK_CLIENT = None
    lock.REDIS_LOCK_TOKEN = None

    caplog.set_level(logging.WARNING)

    def bad_from_url(_url):
        raise RuntimeError("redis down")

    fake_redis_module = SimpleNamespace(Redis=SimpleNamespace(from_url=bad_from_url))
    monkeypatch.setitem(sys.modules, "redis", fake_redis_module)

    lock_file = tmp_path / "poller.lock"

    # // When: acquiring the singleton lock
    ok = lock.acquire_singleton_lock(str(lock_file))

    # // Then: fallback file lock is acquired and warning is logged
    assert ok is True
    assert lock_file.exists()
    assert "Using file-based lock (unsafe for multi-container deployments)" in caplog.text


@pytest.mark.unit
def test_acquire_singleton_lock_without_redis_url_uses_file_lock(monkeypatch, tmp_path, caplog):
    # // Given: no REDIS_URL
    monkeypatch.delenv("REDIS_URL", raising=False)
    lock.REDIS_LOCK_CLIENT = None
    lock.REDIS_LOCK_TOKEN = None

    caplog.set_level(logging.WARNING)

    lock_file = tmp_path / "poller.lock"

    # // When: acquiring the singleton lock
    ok = lock.acquire_singleton_lock(str(lock_file))

    # // Then: fallback file lock is acquired and warning is logged
    assert ok is True
    assert lock_file.exists()
    assert "Using file-based lock (unsafe for multi-container deployments)" in caplog.text
