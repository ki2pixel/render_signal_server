"""
More unit tests for email_processing/orchestrator.py
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from email_processing import orchestrator as orch


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
