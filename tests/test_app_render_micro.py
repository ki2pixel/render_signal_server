"""
Micro-tests to push app_render.py coverage ≥80%.
"""
from collections import deque
from unittest.mock import MagicMock

import pytest

import app_render as ar


@pytest.mark.unit
def test__load_processing_prefs_happy(monkeypatch, tmp_path):
    # Monkeypatch loader to verify call and return value
    called = {}
    def fake_load_processing_prefs(*, redis_client, file_path, defaults, logger, redis_key):
        called['args'] = {
            'redis_client': redis_client,
            'file_path': file_path,
            'defaults': defaults,
            'redis_key': redis_key,
        }
        return {'rate_limit_per_hour': 0, 'retry_count': 0}
    monkeypatch.setattr(ar._processing_prefs, 'load_processing_prefs', fake_load_processing_prefs)

    res = ar._load_processing_prefs()
    assert isinstance(res, dict)
    assert 'rate_limit_per_hour' in res
    assert called['args']['redis_key'] == ar.PROCESSING_PREFS_REDIS_KEY


@pytest.mark.unit
def test__save_processing_prefs_false(monkeypatch):
    # Monkeypatch saver to return False
    def fake_save_processing_prefs(prefs, *, redis_client, file_path, logger, redis_key):
        return False
    monkeypatch.setattr(ar._processing_prefs, 'save_processing_prefs', fake_save_processing_prefs)

    ok = ar._save_processing_prefs({'x': 1})
    assert ok is False


@pytest.mark.unit
def test__rate_limit_allow_send_with_invalid_and_zero(monkeypatch):
    # Ensure rate limit returns True when invalid or zero
    # Backup and modify PROCESSING_PREFS temporarily
    original = dict(ar.PROCESSING_PREFS)
    try:
        ar.WEBHOOK_SEND_EVENTS.clear()
        ar.PROCESSING_PREFS['rate_limit_per_hour'] = 'not-an-int'
        assert ar._rate_limit_allow_send() is True
        ar.PROCESSING_PREFS['rate_limit_per_hour'] = 0
        assert ar._rate_limit_allow_send() is True
    finally:
        ar.PROCESSING_PREFS.clear()
        ar.PROCESSING_PREFS.update(original)


@pytest.mark.unit
def test_check_media_solution_pattern_exception_path(monkeypatch):
    # Force underlying checker to raise to trigger exception path and default return
    def bad_checker(**kwargs):
        raise RuntimeError('boom')
    monkeypatch.setattr(ar.email_pattern_matching, 'check_media_solution_pattern', bad_checker)

    out = ar.check_media_solution_pattern('subj', 'content')
    assert out == {"matches": False, "delivery_time": None}


@pytest.mark.unit
def test__append_webhook_log_delegates(monkeypatch):
    # Verify that helper is called with expected redis key and file path
    called = {}
    def fake_append_helper(log_entry, *, redis_client, logger, file_path, redis_list_key, max_entries):
        called['entry'] = log_entry
        called['redis_key'] = redis_list_key
        called['file_path'] = str(file_path)
        called['max'] = max_entries
    monkeypatch.setattr(ar, '_append_webhook_log_helper', fake_append_helper)

    ar._append_webhook_log({'hello': 'world'})
    assert called['entry'] == {'hello': 'world'}
    assert called['redis_key'] == ar.WEBHOOK_LOGS_REDIS_KEY
    assert called['max'] == 500
