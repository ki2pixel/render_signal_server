"""
More unit tests for email_processing/orchestrator.py
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from email_processing import orchestrator as orch
from email_processing import pattern_matching as pm


@pytest.mark.unit
def test_compute_desabo_time_window_early_ok():
    # now before start -> early_ok True, payload uses start string
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 13, 8, 0, tzinfo=tz)
    # Inputs
    now_local = FakeDT.now(timezone.utc)
    early_ok, start_payload, window_ok = orch.compute_desabo_time_window(
        now_local=now_local,
        webhooks_time_start=now_local.replace(hour=9, minute=0).time(),
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        within_window=False,
    )
    assert early_ok is True
    assert start_payload == "09:00"
    assert window_ok is True


@pytest.mark.unit
def test_compute_desabo_time_window_outside_and_not_early():
    # now after end and not within
    now_local = datetime(2025, 10, 13, 20, 0, tzinfo=timezone.utc)
    early_ok, start_payload, window_ok = orch.compute_desabo_time_window(
        now_local=now_local,
        webhooks_time_start=now_local.replace(hour=9, minute=0).time(),
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        within_window=False,
    )
    assert early_ok is False
    assert start_payload is None
    assert window_ok is False


@pytest.mark.unit
def test_send_custom_webhook_flow_skips_when_no_links_and_policy_forbids(mocker):
    # Prepare inputs
    calls = {}
    def rate_limit_allow_send():
        return True
    def record_send_event():
        calls['record'] = True
    def append_webhook_log(entry):
        calls.setdefault('logs', []).append(entry)
    def mark_email_id_as_processed_redis(eid):
        calls['marked'] = eid
        return True
    def mark_email_as_read_imap(mail, email_num):
        calls['read'] = True
    # Execute
    cont = orch.send_custom_webhook_flow(
        email_id="e1",
        subject="subj",
        payload_for_webhook={"ok": True},
        delivery_links=[],
        webhook_url="https://example.com/hook",
        webhook_ssl_verify=True,
        allow_without_links=False,
        processing_prefs={},
        rate_limit_allow_send=rate_limit_allow_send,
        record_send_event=record_send_event,
        append_webhook_log=append_webhook_log,
        mark_email_id_as_processed_redis=mark_email_id_as_processed_redis,
        mark_email_as_read_imap=mark_email_as_read_imap,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=None,
        time=None,
        logger=SimpleNamespace(info=lambda *a, **k: None),
    )
    assert cont is True
    assert calls.get('marked') == 'e1'


@pytest.mark.unit
def test_send_custom_webhook_flow_rate_limited(mocker):
    calls = {}
    def rate_limit_allow_send():
        return False
    def record_send_event():
        calls['record'] = True
    def append_webhook_log(entry):
        calls.setdefault('logs', []).append(entry)

    cont = orch.send_custom_webhook_flow(
        email_id="e2",
        subject="s",
        payload_for_webhook={},
        delivery_links=['x'],
        webhook_url="https://example.com/hook",
        webhook_ssl_verify=True,
        allow_without_links=True,
        processing_prefs={"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1},
        rate_limit_allow_send=rate_limit_allow_send,
        record_send_event=record_send_event,
        append_webhook_log=append_webhook_log,
        mark_email_id_as_processed_redis=lambda eid: False,
        mark_email_as_read_imap=lambda *a, **k: None,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=SimpleNamespace(post=lambda *a, **k: SimpleNamespace(status_code=500, text="err")),
        time=SimpleNamespace(sleep=lambda s: None),
        logger=SimpleNamespace(warning=lambda *a, **k: None),
    )
    assert cont is True


@pytest.mark.unit
def test_send_custom_webhook_flow_success_marks_and_returns_false():
    # Success 200 with {success: true}
    class Resp:
        status_code = 200
        content = b"{}"
        def json(self):
            return {"success": True}
    calls = {"record": 0}
    def record_send_event():
        calls["record"] += 1
    def append_webhook_log(entry):
        calls.setdefault('logs', []).append(entry)
    def mark_email_id_as_processed_redis(eid):
        calls['marked'] = True
        return True
    def mark_email_as_read_imap(mail, num):
        calls['read'] = True

    cont = orch.send_custom_webhook_flow(
        email_id="e3",
        subject="s",
        payload_for_webhook={},
        delivery_links=['x'],
        webhook_url="https://example.com/hook",
        webhook_ssl_verify=True,
        allow_without_links=True,
        processing_prefs={"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1},
        rate_limit_allow_send=lambda: True,
        record_send_event=record_send_event,
        append_webhook_log=append_webhook_log,
        mark_email_id_as_processed_redis=mark_email_id_as_processed_redis,
        mark_email_as_read_imap=mark_email_as_read_imap,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=SimpleNamespace(post=lambda *a, **k: Resp()),
        time=SimpleNamespace(sleep=lambda s: None),
        logger=SimpleNamespace(info=lambda *a, **k: None),
    )
    assert cont is False
    assert calls.get('marked') is True
    assert calls.get('read') is True


@pytest.mark.unit
def test_outside_window_recadrage_is_marked_and_not_sent(monkeypatch):
    """Outside webhook window, detector=recadrage → skip send, mark read+processed."""
    # Arrange: force time to 10:00 (before 10h30 window)
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tz)
    # ENV/webhook window + force outside-window branch (set BEFORE any imports)
    monkeypatch.setenv('WEBHOOK_URL', 'https://example.com/hook')
    monkeypatch.setenv('WEBHOOK_SENDING_ENABLED', 'true')
    monkeypatch.setenv('POLLING_ACTIVE_DAYS', 'Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday')
    monkeypatch.setenv('POLLING_ACTIVE_START_HOUR', '0')
    monkeypatch.setenv('POLLING_ACTIVE_END_HOUR', '23')
    monkeypatch.setenv('WEBHOOK_TIME_START', '10h30')
    monkeypatch.setenv('WEBHOOK_TIME_END', '19h00')

    # Import orchestrator AFTER setting env vars so it picks up correct config
    import sys
    # Remove cached modules to force reimport
    for mod in ['config.settings', 'app_render', 'email_processing.orchestrator', 'email_processing.pattern_matching']:
        sys.modules.pop(mod, None)
    
    from email_processing import orchestrator as orch_local
    from email_processing import pattern_matching as pm_local
    
    monkeypatch.setattr(orch_local, 'datetime', FakeDT)
    monkeypatch.setattr(orch_local, 'is_within_time_window_local', lambda now, s, e: False)
    # Also patch the underlying helper to be safe
    import utils.time_helpers as th
    monkeypatch.setattr(th, 'is_within_time_window_local', lambda *a, **k: False)
    # Force webhook sending enabled helper to return True
    monkeypatch.setattr(orch_local, '_is_webhook_sending_enabled', lambda: True, raising=False)

    # Patch detectors: recadrage matches
    monkeypatch.setattr(pm_local, 'check_media_solution_pattern', lambda s, b, tz, l: {"matches": True, "delivery_time": "11h00"})
    monkeypatch.setattr(pm_local, 'check_desabo_conditions', lambda s, b, l: {"matches": False})
    monkeypatch.setattr(
        orch_local,
        'pattern_matching',
        SimpleNamespace(
            check_media_solution_pattern=lambda s, b, tz, l: {"matches": True, "delivery_time": "11h00"},
            check_desabo_conditions=lambda s, b, l: {"matches": False},
        ),
        raising=False,
    )

    # Prepare runtime symbols (patch on app_render namespace used by orchestrator)
    import app_render as ar
    # Ensure no legacy delegation short-circuits the test
    monkeypatch.setattr(ar, '_legacy_check_new_emails_and_trigger_webhook', None, raising=False)
    calls = {"marked": 0, "read": 0, "send": 0}

    class FakeMail:
        def select(self, box):
            return ('OK', [])
        def search(self, *_):
            return ('OK', [b'1'])
        def fetch(self, num, *_):
            raw = (b"Subject: Media Solution - Missions Recadrage - Lot 1\r\n"
                   b"From: allowed@example.com\r\n"
                   b"Date: Wed, 22 Oct 2025 10:00:00 +0200\r\n"
                   b"Content-Type: text/plain; charset=utf-8\r\n"
                   b"\r\n"
                   b"Lien: https://www.dropbox.com/scl/fo/abc\r\n")
            return ('OK', [(b'1', raw)])

    monkeypatch.setattr(ar, 'create_imap_connection', lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, 'close_imap_connection', lambda m: None, raising=False)
    monkeypatch.setattr(ar, 'decode_email_header', lambda s: s, raising=False)
    monkeypatch.setattr(ar, 'extract_sender_email', lambda s: 'allowed@example.com', raising=False)
    monkeypatch.setattr(ar, 'mark_email_as_read_imap', lambda m, n: calls.__setitem__('read', calls['read'] + 1), raising=False)
    monkeypatch.setattr(ar, 'mark_email_id_as_processed_redis', lambda eid: calls.__setitem__('marked', calls['marked'] + 1), raising=False)
    monkeypatch.setattr(ar, 'is_email_id_processed_redis', lambda eid: False, raising=False)
    monkeypatch.setattr(ar, 'generate_subject_group_id', lambda s: 'g1', raising=False)
    monkeypatch.setattr(ar, 'is_subject_group_processed', lambda gid: False, raising=False)
    monkeypatch.setattr(ar, '_rate_limit_allow_send', lambda: True, raising=False)
    monkeypatch.setattr(ar, '_record_send_event', lambda: None, raising=False)
    monkeypatch.setattr(ar, '_append_webhook_log', lambda e: None, raising=False)
    # Also patch orchestrator-level mark functions (names used after runtime import)
    monkeypatch.setattr(orch_local, 'mark_email_as_read_imap', lambda m, n: calls.__setitem__('read', calls['read'] + 1), raising=False)
    monkeypatch.setattr(orch_local, 'mark_email_id_as_processed_redis', lambda eid: calls.__setitem__('marked', calls['marked'] + 1), raising=False)
    # Prevent send path from being used in this test (should not be called)
    monkeypatch.setattr(orch_local, 'send_custom_webhook_flow', lambda **k: calls.__setitem__('send', calls['send'] + 1), raising=False)

    # Required config symbols (set on app_render, used by orchestrator)
    monkeypatch.setattr(ar, 'WEBHOOK_URL', 'https://example.com/hook', raising=False)
    monkeypatch.setattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', True, raising=False)
    monkeypatch.setattr(ar, 'PROCESSING_PREFS', {}, raising=False)
    monkeypatch.setattr(ar, 'SENDER_LIST_FOR_POLLING', ['allowed@example.com'], raising=False)
    monkeypatch.setattr(ar, 'TZ_FOR_POLLING', timezone.utc, raising=False)
    # Logger on app_render.app
    monkeypatch.setattr(ar, 'app', SimpleNamespace(logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None, debug=lambda *a, **k: None)), raising=False)

    # Act
    cnt = orch_local.check_new_emails_and_trigger_webhook()

    # Assert
    assert calls['send'] == 0  # no webhook send
    assert calls['marked'] == 1 and calls['read'] == 1  # marked processed + read
    assert isinstance(cnt, int)


@pytest.mark.unit
def test_outside_window_desabo_bypasses_and_sent(monkeypatch):
    """Outside webhook window, detector=DESABO → bypass window and send."""
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tz)

    monkeypatch.setenv('WEBHOOK_URL', 'https://example.com/hook')
    monkeypatch.setenv('WEBHOOK_SENDING_ENABLED', 'true')
    monkeypatch.setenv('POLLING_ACTIVE_DAYS', 'Monday,Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday')
    monkeypatch.setenv('POLLING_ACTIVE_START_HOUR', '0')
    monkeypatch.setenv('POLLING_ACTIVE_END_HOUR', '23')
    monkeypatch.setenv('WEBHOOK_TIME_START', '10h30')
    monkeypatch.setenv('WEBHOOK_TIME_END', '19h00')

    # Import orchestrator AFTER setting env vars
    import sys
    for mod in ['config.settings', 'app_render', 'email_processing.orchestrator', 'email_processing.pattern_matching']:
        sys.modules.pop(mod, None)
    
    from email_processing import orchestrator as orch_local
    from email_processing import pattern_matching as pm_local
    
    monkeypatch.setattr(orch_local, 'datetime', FakeDT)
    monkeypatch.setattr(orch_local, 'is_within_time_window_local', lambda *a, **k: False)
    monkeypatch.setattr(orch_local, '_is_webhook_sending_enabled', lambda: True, raising=False)

    # Force DESABO
    monkeypatch.setattr(pm_local, 'check_media_solution_pattern', lambda s, b, tz, l: {"matches": False})
    monkeypatch.setattr(pm_local, 'check_desabo_conditions', lambda s, b, l: {"matches": True, "has_dropbox_request": True})
    monkeypatch.setattr(
        orch_local,
        'pattern_matching',
        SimpleNamespace(
            check_media_solution_pattern=lambda s, b, tz, l: {"matches": False},
            check_desabo_conditions=lambda s, b, l: {"matches": True, "has_dropbox_request": True},
        ),
        raising=False,
    )

    import app_render as ar
    # Ensure no legacy delegation short-circuits the test
    monkeypatch.setattr(ar, '_legacy_check_new_emails_and_trigger_webhook', None, raising=False)
    calls = {"send": 0}

    class FakeMail:
        def select(self, box):
            return ('OK', [])
        def search(self, *_):
            return ('OK', [b'1'])
        def fetch(self, num, *_):
            raw = (b"Subject: DESABO\r\n"
                   b"From: allowed@example.com\r\n"
                   b"Date: Wed, 22 Oct 2025 10:00:00 +0200\r\n"
                   b"Content-Type: text/plain; charset=utf-8\r\n"
                   b"\r\n"
                   b"se desabonner / tarifs habituels https://www.dropbox.com/request/abc\r\n")
            return ('OK', [(b'1', raw)])

    monkeypatch.setattr(ar, 'create_imap_connection', lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, 'close_imap_connection', lambda m: None, raising=False)
    monkeypatch.setattr(ar, 'decode_email_header', lambda s: s, raising=False)
    monkeypatch.setattr(ar, 'extract_sender_email', lambda s: 'allowed@example.com', raising=False)
    monkeypatch.setattr(ar, 'mark_email_as_read_imap', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ar, 'mark_email_id_as_processed_redis', lambda eid: None, raising=False)
    monkeypatch.setattr(ar, 'is_email_id_processed_redis', lambda eid: False, raising=False)
    monkeypatch.setattr(ar, 'generate_subject_group_id', lambda s: 'g2', raising=False)
    monkeypatch.setattr(ar, 'is_subject_group_processed', lambda gid: False, raising=False)
    monkeypatch.setattr(ar, '_rate_limit_allow_send', lambda: True, raising=False)
    monkeypatch.setattr(ar, '_record_send_event', lambda: None, raising=False)
    monkeypatch.setattr(ar, '_append_webhook_log', lambda e: None, raising=False)

    def fake_send_custom_webhook_flow(**kwargs):
        calls['send'] += 1
        return False  # indicate an attempted send occurred

    monkeypatch.setattr(orch_local, 'send_custom_webhook_flow', fake_send_custom_webhook_flow, raising=False)

    monkeypatch.setattr(ar, 'WEBHOOK_URL', 'https://example.com/hook', raising=False)
    monkeypatch.setattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', True, raising=False)
    monkeypatch.setattr(ar, 'PROCESSING_PREFS', {}, raising=False)
    monkeypatch.setattr(ar, 'SENDER_LIST_FOR_POLLING', ['allowed@example.com'], raising=False)
    monkeypatch.setattr(ar, 'TZ_FOR_POLLING', timezone.utc, raising=False)
    monkeypatch.setattr(ar, 'app', SimpleNamespace(logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None, debug=lambda *a, **k: None)), raising=False)

    cnt = orch_local.check_new_emails_and_trigger_webhook()
    assert calls['send'] == 1
    assert isinstance(cnt, int)


@pytest.mark.unit
def test_outside_window_neutral_skips_without_marking(monkeypatch):
    """Outside webhook window, neutral (no detector) → skip send, do not mark read/processed."""
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tz)
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    monkeypatch.setenv('WEBHOOK_SENDING_ENABLED', 'true')
    monkeypatch.setenv('WEBHOOK_TIME_START', '10h30')
    monkeypatch.setenv('WEBHOOK_TIME_END', '19h00')

    # No detectors match
    monkeypatch.setattr(pm, 'check_media_solution_pattern', lambda s, b, tz, l: {"matches": False})
    monkeypatch.setattr(pm, 'check_desabo_conditions', lambda s, b, l: {"matches": False},)

    import app_render as ar
    calls = {"marked": 0, "read": 0, "send": 0}

    class FakeMail:
        def select(self, box):
            return ('OK', [])
        def search(self, *_):
            return ('OK', [b'1'])
        def fetch(self, num, *_):
            raw = (b"Subject: Neutral\r\n"
                   b"From: allowed@example.com\r\n"
                   b"Date: Wed, 22 Oct 2025 10:00:00 +0200\r\n"
                   b"Content-Type: text/plain; charset=utf-8\r\n"
                   b"\r\n"
                   b"Hello world\r\n")
            return ('OK', [(b'1', raw)])
    # Ensure no legacy delegation short-circuits the test
    monkeypatch.setattr(ar, '_legacy_check_new_emails_and_trigger_webhook', None, raising=False)

    monkeypatch.setattr(ar, 'create_imap_connection', lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, 'close_imap_connection', lambda m: None, raising=False)
    monkeypatch.setattr(ar, 'decode_email_header', lambda s: s, raising=False)
    monkeypatch.setattr(ar, 'extract_sender_email', lambda s: 'allowed@example.com', raising=False)
    monkeypatch.setattr(ar, 'mark_email_as_read_imap', lambda m, n: calls.__setitem__('read', calls['read'] + 1), raising=False)
    monkeypatch.setattr(ar, 'mark_email_id_as_processed_redis', lambda eid: calls.__setitem__('marked', calls['marked'] + 1), raising=False)
    monkeypatch.setattr(ar, 'is_email_id_processed_redis', lambda eid: False, raising=False)
    monkeypatch.setattr(ar, 'generate_subject_group_id', lambda s: 'g3', raising=False)
    monkeypatch.setattr(ar, 'is_subject_group_processed', lambda gid: False, raising=False)
    monkeypatch.setattr(ar, '_rate_limit_allow_send', lambda: True, raising=False)
    monkeypatch.setattr(ar, '_record_send_event', lambda: None, raising=False)
    monkeypatch.setattr(ar, '_append_webhook_log', lambda e: None, raising=False)

    monkeypatch.setattr(orch, 'send_custom_webhook_flow', lambda **k: calls.__setitem__('send', calls['send'] + 1), raising=False)

    monkeypatch.setattr(ar, 'WEBHOOK_URL', 'https://example.com/hook', raising=False)
    monkeypatch.setattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', True, raising=False)
    monkeypatch.setattr(ar, 'PROCESSING_PREFS', {}, raising=False)
    monkeypatch.setattr(ar, 'SENDER_LIST_FOR_POLLING', ['allowed@example.com'], raising=False)
    monkeypatch.setattr(ar, 'TZ_FOR_POLLING', timezone.utc, raising=False)
    monkeypatch.setattr(ar, 'app', SimpleNamespace(logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None, debug=lambda *a, **k: None)), raising=False)

    cnt = orch.check_new_emails_and_trigger_webhook()
    # Assert: skipped outside window, no marking and no send
    assert calls['send'] == 0
    assert calls['marked'] == 0 and calls['read'] == 0
    assert isinstance(cnt, int)
