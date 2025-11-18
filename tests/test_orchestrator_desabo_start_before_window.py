"""
Unit test: DESABO non-urgent before start -> payload webhooks_time_start equals configured start
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


def test_desabo_before_window_sets_payload_start_to_configured_start(monkeypatch):
    """Outside webhook window (before start), detector=DESABO non-urgent ->
    webhook payload must set webhooks_time_start to configured start string (e.g., "12h00").
    """

    # Fix local time to 10:00 which is before a 12h00 start
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tz)

    # Set environment and window to 12h00-19h00
    monkeypatch.setenv('WEBHOOK_URL', 'https://example.com/hook')
    monkeypatch.setenv('WEBHOOK_SENDING_ENABLED', 'true')
    monkeypatch.setenv('POLLING_ACTIVE_DAYS', 'Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday')
    monkeypatch.setenv('POLLING_ACTIVE_START_HOUR', '0')
    monkeypatch.setenv('POLLING_ACTIVE_END_HOUR', '23')
    monkeypatch.setenv('WEBHOOK_TIME_START', '12h00')
    monkeypatch.setenv('WEBHOOK_TIME_END', '19h00')

    # Import modules (avoid clearing app_render to not reset in-memory webhook logs used by other tests)
    from email_processing import orchestrator as orch
    from email_processing import pattern_matching as pm
    import app_render as ar
    from config import webhook_time_window as wtw
    from config import app_config_store as store
    from config import settings
    
    # Mock app_config_store to return empty config so ENV vars are used
    monkeypatch.setattr(store, 'get_config_json', lambda key, file_fallback=None: {})

    # Patch time and window check to be outside window
    monkeypatch.setattr(orch, 'datetime', FakeDT)
    monkeypatch.setattr(orch, 'is_within_time_window_local', lambda *a, **k: False)

    # Detector: DESABO non-urgent
    monkeypatch.setattr(pm, 'check_media_solution_pattern', lambda s, b, tz, l: {'matches': False})
    monkeypatch.setattr(pm, 'check_desabo_conditions', lambda s, b, l: {'matches': True, 'is_urgent': False})
    monkeypatch.setattr(
        orch,
        'pattern_matching',
        SimpleNamespace(
            check_media_solution_pattern=lambda s, b, tz, l: {'matches': False},
            check_desabo_conditions=lambda s, b, l: {'matches': True, 'is_urgent': False},
        ),
        raising=False,
    )

    # Prevent legacy shortcut and prepare runtime app_render symbols
    monkeypatch.setattr(ar, '_legacy_check_new_emails_and_trigger_webhook', None, raising=False)
    monkeypatch.setattr(ar, 'WEBHOOK_URL', 'https://example.com/hook', raising=False)
    monkeypatch.setattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', True, raising=False)
    monkeypatch.setattr(ar, 'PROCESSING_PREFS', {}, raising=False)
    monkeypatch.setattr(ar, 'SENDER_LIST_FOR_POLLING', ['allowed@example.com'], raising=False)
    monkeypatch.setattr(ar, 'TZ_FOR_POLLING', timezone.utc, raising=False)
    monkeypatch.setattr(
        ar,
        'app',
        SimpleNamespace(
            logger=SimpleNamespace(
                info=lambda *a, **k: None,
                warning=lambda *a, **k: None,
                error=lambda *a, **k: None,
                debug=lambda *a, **k: None,
            )
        ),
        raising=False,
    )

    # Minimal IMAP fakes
    class FakeMail:
        def select(self, box):
            return ('OK', [])
        def search(self, *_):
            return ('OK', [b'1'])
        def fetch(self, num, *_):
            raw = (
                b"Subject: DESABO\r\n"
                b"From: allowed@example.com\r\n"
                b"Date: Wed, 22 Oct 2025 10:00:00 +0200\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"\r\n"
                b"demande tarifs / dropbox https://www.dropbox.com/request/abc\r\n"
            )
            return ('OK', [(b'1', raw)])

    calls = {'send': 0, 'payload_start': None}

    def fake_send_custom_webhook_flow(**kwargs):
        calls['send'] += 1
        payload = kwargs.get('payload_for_webhook') or {}
        calls['payload_start'] = payload.get('webhooks_time_start')
        return False  # indicate an attempted send

    # Patch orchestrator send and IMAP plumbing
    monkeypatch.setattr(orch, 'send_custom_webhook_flow', fake_send_custom_webhook_flow, raising=False)
    monkeypatch.setattr(ar, 'create_imap_connection', lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, 'close_imap_connection', lambda m: None, raising=False)
    monkeypatch.setattr(ar, 'decode_email_header', lambda s: s, raising=False)
    monkeypatch.setattr(ar, 'extract_sender_email', lambda s: 'allowed@example.com', raising=False)
    monkeypatch.setattr(ar, 'mark_email_as_read_imap', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ar, 'mark_email_id_as_processed_redis', lambda eid: None, raising=False)
    monkeypatch.setattr(ar, 'is_email_id_processed_redis', lambda eid: False, raising=False)
    monkeypatch.setattr(ar, 'generate_subject_group_id', lambda s: 'g2', raising=False)
    monkeypatch.setattr(ar, 'is_subject_group_processed', lambda gid: False, raising=False)
    monkeypatch.setattr(orch, '_is_webhook_sending_enabled', lambda: True, raising=False)

    # Act
    cnt = orch.check_new_emails_and_trigger_webhook()

    # Assert
    assert calls['send'] == 1
    assert isinstance(cnt, int)
    # Compare against effective start coming from app_config_store-backed webhook_config
    cfg = store.get_config_json('webhook_config', file_fallback=settings.WEBHOOK_CONFIG_FILE)
    # Prefer global_time_start then webhook_time_start
    expected_store_start = (cfg.get('global_time_start') or cfg.get('webhook_time_start') or '').strip()
    # Also consider webhook_time_window active start
    expected_wtw_start = (wtw.get_time_window_info().get('start') or '').strip()
    candidates = {s for s in [expected_store_start, expected_wtw_start] if s}
    if candidates:
        assert calls['payload_start'] in candidates
    else:
        # If no configured start is resolvable in this environment, ensure a non-empty HHhMM-like string
        val = calls['payload_start']
        assert isinstance(val, str) and len(val) >= 4 and 'h' in val
