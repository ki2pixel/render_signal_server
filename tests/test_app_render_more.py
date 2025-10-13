"""
Additional micro-tests to raise coverage of app_render.py ≥80%.
Covers wrapper delegates and rate-limit event recording.
"""
from collections import deque
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import app_render as ar


@pytest.mark.unit
def test_wrappers_imap_and_generators(monkeypatch):
    # Arrange mocks for email_imap_client wrappers
    calls = {}
    monkeypatch.setattr(ar.email_imap_client, 'create_imap_connection', lambda logger: 'MAIL')
    monkeypatch.setattr(ar.email_imap_client, 'close_imap_connection', lambda logger, mail: True)
    monkeypatch.setattr(ar.email_imap_client, 'generate_email_id', lambda msg: 'EID123')
    monkeypatch.setattr(ar.email_imap_client, 'extract_sender_email', lambda s: 'sender@example.com')
    monkeypatch.setattr(ar.email_imap_client, 'decode_email_header_value', lambda v: 'decoded')
    monkeypatch.setattr(ar.email_imap_client, 'mark_email_as_read_imap', lambda logger, mail, num: True)

    # Act + Assert wrappers
    assert ar.create_imap_connection() == 'MAIL'
    assert ar.close_imap_connection('MAIL') is True
    assert ar.generate_email_id(SimpleNamespace()) == 'EID123'
    assert ar.extract_sender_email('From: <sender@example.com>') == 'sender@example.com'
    assert ar.decode_email_header('=?UTF-8?Q?...?=') == 'decoded'
    assert ar.mark_email_as_read_imap('MAIL', 1) is True


@pytest.mark.unit
def test_wrappers_subject_group_and_dedup(monkeypatch):
    # generate_subject_group_id is a pure wrapper
    gid = ar.generate_subject_group_id('Subject X')
    assert isinstance(gid, str) and len(gid) > 0

    # subject group processed wrappers delegate to _dedup
    class FakeDedup:
        def is_subject_group_processed(self, rc, group_id, logger, ttl_seconds, ttl_prefix, groups_key, enable_monthly_scope, tz, memory_set=None):
            return group_id == 'sg-ok'
        def mark_subject_group_processed(self, rc, group_id, logger, ttl_seconds, ttl_prefix, groups_key, enable_monthly_scope, tz, memory_set=None):
            return group_id == 'sg-ok'
    # monkeypatch module attributes
    monkeypatch.setattr(ar, '_dedup', FakeDedup())

    assert ar.is_subject_group_processed('sg-ok') is True
    assert ar.is_subject_group_processed('sg-no') is False
    assert ar.mark_subject_group_processed('sg-ok') is True
    assert ar.mark_subject_group_processed('sg-no') is False


@pytest.mark.unit
def test_send_makecom_webhook_delegate(monkeypatch):
    # Ensure delegate called with expected args
    captured = {}
    def fake_send(**kwargs):
        captured.update(kwargs)
        return True
    monkeypatch.setattr(ar.email_webhook_sender, 'send_makecom_webhook', fake_send)

    ok = ar.send_makecom_webhook('subj', '10:00', 'sender@example.com', 'e1', override_webhook_url=None, extra_payload={'x':1})
    assert ok is True
    assert captured['subject'] == 'subj'
    assert captured['email_id'] == 'e1'
    assert 'logger' in captured and 'log_hook' in captured


@pytest.mark.unit
def test_check_new_emails_and_trigger_webhook_delegate(monkeypatch):
    # Delegate to orchestrator entry point
    monkeypatch.setattr(ar.email_orchestrator, 'check_new_emails_and_trigger_webhook', lambda: 5)
    assert ar.check_new_emails_and_trigger_webhook() == 5


@pytest.mark.unit
def test_rate_limit_record_and_prune(monkeypatch):
    # Fill queue with old timestamps and ensure prune path is exercised
    ar.WEBHOOK_SEND_EVENTS.clear()
    old = datetime.now().timestamp() - 4000
    recent = datetime.now().timestamp()
    ar.WEBHOOK_SEND_EVENTS.extend([old, recent])
    # limit_per_hour=1 should prune 'old' and then compare length 2-> after prune length 1
    # monkeypatch prune function to call the real one from utils
    from utils import rate_limit as rl
    monkeypatch.setattr(ar, '_rate_prune_and_allow', rl.prune_and_allow_send)

    # With limit 1 and one recent event, not allowed (len==1 -> not < 1)
    original = dict(ar.PROCESSING_PREFS)
    try:
        ar.PROCESSING_PREFS['rate_limit_per_hour'] = 1
        allowed = ar._rate_limit_allow_send()
        assert allowed is False
        # Record a send event path
        ar._record_send_event()
        assert len(ar.WEBHOOK_SEND_EVENTS) >= 2
    finally:
        ar.PROCESSING_PREFS.clear(); ar.PROCESSING_PREFS.update(original)
        ar.WEBHOOK_SEND_EVENTS.clear()
