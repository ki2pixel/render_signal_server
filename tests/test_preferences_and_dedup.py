"""
Tests for preferences/processing_prefs.py and deduplication/subject_group.py
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from preferences import processing_prefs as pp
from deduplication import subject_group as sg


DEFAULTS = {
    "exclude_keywords": [],
    "require_attachments": False,
    "max_email_size_mb": None,
    "sender_priority": {},
    "retry_count": 0,
    "retry_delay_sec": 2,
    "webhook_timeout_sec": 30,
    "rate_limit_per_hour": 0,
    "notify_on_failure": False,
}


@pytest.mark.unit
def test_processing_prefs_validate_edges():
    # invalid types
    ok, msg, out = pp.validate_processing_prefs({"exclude_keywords": "oops"}, DEFAULTS)
    assert ok is False and "liste" in msg

    ok, msg, out = pp.validate_processing_prefs({"sender_priority": {"x@y.z": "invalid"}}, DEFAULTS)
    assert ok is False and "niveau" in msg

    ok, msg, out = pp.validate_processing_prefs({"retry_count": 999}, DEFAULTS)
    assert ok is False and "0..10" in msg

    ok, msg, out = pp.validate_processing_prefs({"retry_delay_sec": 9999}, DEFAULTS)
    assert ok is False and "0..600" in msg

    ok, msg, out = pp.validate_processing_prefs({"webhook_timeout_sec": 0}, DEFAULTS)
    assert ok is False and "1..300" in msg

    ok, msg, out = pp.validate_processing_prefs({"rate_limit_per_hour": -1}, DEFAULTS)
    assert ok is False and "0..100000" in msg

    # valid payload
    good = {
        "exclude_keywords": ["a", "b"],
        "sender_priority": {"x@y.z": "low"},
        "retry_count": 1,
        "retry_delay_sec": 2,
        "webhook_timeout_sec": 30,
        "rate_limit_per_hour": 100,
        "notify_on_failure": True,
    }
    ok, msg, out = pp.validate_processing_prefs(good, DEFAULTS)
    assert ok is True
    assert out["sender_priority"]["x@y.z"] == "low"


@pytest.mark.unit
def test_processing_prefs_file_and_redis_fallbacks(tmp_path):
    fake_file = tmp_path / "prefs.json"
    logger = MagicMock()

    # No redis, no file -> defaults
    out = pp.load_processing_prefs(redis_client=None, file_path=fake_file, defaults=DEFAULTS, logger=logger, redis_key=None)
    assert out == DEFAULTS

    # Save to file path
    ok = pp.save_processing_prefs({"retry_count": 2}, redis_client=None, file_path=fake_file, logger=logger, redis_key=None)
    assert ok is True
    # Load picks up merge
    out2 = pp.load_processing_prefs(redis_client=None, file_path=fake_file, defaults=DEFAULTS, logger=logger, redis_key=None)
    assert out2["retry_count"] == 2

    # Simulate redis success
    class FakeRedis:
        def __init__(self):
            self.d = {}
        def get(self, k):
            return self.d.get(k)
        def set(self, k, v):
            self.d[k] = v
    fr = FakeRedis()
    # Save to redis
    ok2 = pp.save_processing_prefs({"retry_count": 3}, redis_client=fr, file_path=fake_file, logger=logger, redis_key="p")
    assert ok2 is True
    # Load from redis should override
    out3 = pp.load_processing_prefs(redis_client=fr, file_path=fake_file, defaults=DEFAULTS, logger=logger, redis_key="p")
    assert out3["retry_count"] == 3


@pytest.mark.unit
def test_processing_prefs_invalid_json_logs_and_returns_defaults(tmp_path):
    fake_file = tmp_path / "prefs.json"
    fake_file.write_text("invalid { json", encoding="utf-8")
    logger = MagicMock()
    out = pp.load_processing_prefs(redis_client=None, file_path=fake_file, defaults=DEFAULTS, logger=logger, redis_key=None)
    assert out == DEFAULTS
    # Ensure logger.error was called
    assert logger.error.called


@pytest.mark.unit
def test_subject_group_id_generation():
    # Média Solution + lot
    s1 = "Re: Média Solution - Missions Recadrage - Lot 42"
    gid1 = sg.generate_subject_group_id(s1)
    assert gid1.endswith("_lot_42")

    # Generic lot pattern
    s2 = "Fwd: Sujet - lot 7 - info"
    gid2 = sg.generate_subject_group_id(s2)
    assert gid2.endswith("lot_7")

    # Fallback hash
    s3 = "Discussion quelconque sans lot"
    gid3 = sg.generate_subject_group_id(s3)
    assert gid3.startswith("subject_hash_")
