"""
More micro-tests for deduplication/redis_client.py to push coverage >80%.
"""
from datetime import timezone
from unittest.mock import MagicMock

import pytest

from deduplication import redis_client as rc


@pytest.mark.unit
def test_is_email_id_processed_logs_and_returns_false_on_redis_error(monkeypatch):
    class BadRedis:
        def sismember(self, *a, **k):
            raise RuntimeError("conn err")
    logger = MagicMock()
    ok = rc.is_email_id_processed(BadRedis(), "idx", logger, "k")
    assert ok is False
    logger.error.assert_called()


@pytest.mark.unit
def test_mark_email_id_processed_returns_false_on_redis_error(monkeypatch):
    class BadRedis:
        def sadd(self, *a, **k):
            raise RuntimeError("write err")
    logger = MagicMock()
    ok = rc.mark_email_id_processed(BadRedis(), "idy", logger, "k")
    assert ok is False
    logger.error.assert_called()


@pytest.mark.unit
def test_is_subject_group_processed_true_when_ttl_marker_present(monkeypatch):
    class TTLRedis:
        def __init__(self):
            self.store = {"r:ss:subject_group_ttl:2025-10:gid": 1}
        def get(self, key):
            return self.store.get(key)
        def sismember(self, key, value):
            return False
    # Fix current month prefix via monkeypatch
    class FakeDT:
        @classmethod
        def now(cls, tz=None):
            from datetime import datetime
            return datetime(2025, 10, 13, tzinfo=tz)
    monkeypatch.setattr(rc, 'datetime', FakeDT)

    r = TTLRedis()
    ok = rc.is_subject_group_processed(
        r, "gid", MagicMock(), ttl_seconds=60,
        ttl_prefix="r:ss:subject_group_ttl:",
        groups_key="r:ss:processed_subject_groups:v1",
        enable_monthly_scope=True, tz=timezone.utc,
    )
    assert ok is True


@pytest.mark.unit
def test_mark_subject_group_processed_memory_add_failure_returns_false(monkeypatch):
    # Force Redis error to trigger memory fallback, and a memory set that raises on add
    class BadRedis:
        def set(self, *a, **k):
            raise RuntimeError("set err")
        def sadd(self, *a, **k):
            raise RuntimeError("sadd err")
    class BadSet(set):
        def add(self, *a, **k):
            raise RuntimeError("cannot add")
    res = rc.mark_subject_group_processed(
        BadRedis(), "gid", MagicMock(), ttl_seconds=60,
        ttl_prefix="r:ss:subject_group_ttl:", groups_key="r:ss:x",
        enable_monthly_scope=False, tz=timezone.utc, memory_set=BadSet(),
    )
    assert res is False
