"""
Tests for deduplication/redis_client.py
"""
from datetime import timezone
from unittest.mock import MagicMock

import pytest

from deduplication import redis_client as rc


@pytest.mark.unit
def test_email_id_dedup_with_none_redis_returns_false():
    assert rc.is_email_id_processed(None, "id1", MagicMock(), "k") is False
    assert rc.mark_email_id_processed(None, "id1", MagicMock(), "k") is False


@pytest.mark.unit
def test_email_id_dedup_with_redis_ok(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.s = set()
        def sismember(self, key, value):
            return value in self.s
        def sadd(self, key, value):
            self.s.add(value)
    r = FakeRedis()
    assert rc.is_email_id_processed(r, "id2", MagicMock(), "k") is False
    assert rc.mark_email_id_processed(r, "id2", MagicMock(), "k") is True
    assert rc.is_email_id_processed(r, "id2", MagicMock(), "k") is True


@pytest.mark.unit
def test_subject_group_ttl_and_monthly_scope_with_fallback(monkeypatch):
    # Simulate Redis error; fallback to memory_set
    class BadRedis:
        def sismember(self, *a, **k):
            raise RuntimeError("conn error")
        def get(self, *a, **k):
            raise RuntimeError("conn error")
        def sadd(self, *a, **k):
            raise RuntimeError("conn error")
        def set(self, *a, **k):
            raise RuntimeError("conn error")
    br = BadRedis()
    mem = set()

    tz = timezone.utc
    ttl_seconds = 60
    ttl_prefix = "r:ss:subject_group_ttl:"
    groups_key = "r:ss:processed_subject_groups:v1"

    # Initially not processed
    assert rc.is_subject_group_processed(br, "gid", MagicMock(), ttl_seconds, ttl_prefix, groups_key, True, tz, memory_set=mem) is False
    # Mark processed (fallback to memory)
    assert rc.mark_subject_group_processed(br, "gid", MagicMock(), ttl_seconds, ttl_prefix, groups_key, True, tz, memory_set=mem) is True
    # Now reported as processed from memory
    assert rc.is_subject_group_processed(br, "gid", MagicMock(), ttl_seconds, ttl_prefix, groups_key, True, tz, memory_set=mem) is True


@pytest.mark.unit
def test_subject_group_monthly_scoped_id_changes(monkeypatch):
    # Control datetime.now to return two months
    class FakeDT:
        _calls = 0
        @classmethod
        def now(cls, tz=None):
            # First call January 2025, second call February 2025
            cls._calls += 1
            if cls._calls == 1:
                from datetime import datetime
                return datetime(2025, 1, 15, tzinfo=tz)
            else:
                from datetime import datetime
                return datetime(2025, 2, 15, tzinfo=tz)
    monkeypatch.setattr(rc, 'datetime', FakeDT)

    # Check scoped id prefix changes per month
    gid_jan = rc._monthly_scope_group_id("gid", timezone.utc)
    gid_feb = rc._monthly_scope_group_id("gid", timezone.utc)
    assert gid_jan.startswith("2025-01:")
    assert gid_feb.startswith("2025-02:")


@pytest.mark.unit
def test_subject_group_ttl_happy_path_with_redis(monkeypatch):
    class TTLRedis:
        def __init__(self):
            self.store = {}
            self.sets = set()
        def set(self, key, value, ex=None):
            # ignore ex in this fake but record presence
            self.store[key] = value
        def get(self, key):
            return self.store.get(key)
        def sadd(self, key, value):
            self.sets.add((key, value))
        def sismember(self, key, value):
            return (key, value) in self.sets

    r = TTLRedis()
    ttl_seconds = 60
    ttl_prefix = "r:ss:subject_group_ttl:"
    groups_key = "r:ss:processed_subject_groups:v1"
    tz = timezone.utc

    # Initially false
    assert rc.is_subject_group_processed(r, "gidttl", MagicMock(), ttl_seconds, ttl_prefix, groups_key, False, tz) is False
    # Mark processed sets both TTL marker and set membership
    assert rc.mark_subject_group_processed(r, "gidttl", MagicMock(), ttl_seconds, ttl_prefix, groups_key, False, tz) is True
    # TTL present triggers True
    assert rc.is_subject_group_processed(r, "gidttl", MagicMock(), ttl_seconds, ttl_prefix, groups_key, False, tz) is True
