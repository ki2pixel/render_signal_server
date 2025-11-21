"""
Extra micro-tests to raise coverage of email_processing/orchestrator.py toward ≥80%.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from email_processing import orchestrator as orch


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_returns_false_when_not_thu_or_fri(monkeypatch):
    # Force a Monday (weekday=0) to trigger the early return False
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tz)  # Monday
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    routed = orch.handle_presence_route(
        subject="Samedi présent",
        full_email_content="Contenu samedi",
        email_id="e0",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=True,
        presence_true_url="https://hook.eu2.make.com/abc",
        presence_false_url=None,
        is_within_time_window_local=lambda now: True,
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=lambda **k: True,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert routed is False


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_valid_day_but_window_not_satisfied_returns_false(monkeypatch):
    # Force Thursday (weekday=3), but time window check returns False
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 9, 10, 0, tzinfo=tz)
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    routed = orch.handle_presence_route(
        subject="Samedi présent",
        full_email_content="Il sera bien samedi.",
        email_id="e21",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=True,
        presence_true_url="https://hook.eu2.make.com/true",
        presence_false_url=None,
        is_within_time_window_local=lambda now: False,  # window not satisfied
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=lambda **k: True,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert routed is False


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_send_fails_but_routes_true(monkeypatch):
    # Force Friday (weekday=4) within window; send returns False but function still routes True
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 10, 10, 0, tzinfo=tz)
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    calls = {"sent": 0}
    def fake_send(**kwargs):
        calls["sent"] += 1
        return False

    routed = orch.handle_presence_route(
        subject="Samedi présent",
        full_email_content="samedi dans le corps",
        email_id="e22",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=True,
        presence_true_url="https://hook.eu2.make.com/true",
        presence_false_url=None,
        is_within_time_window_local=lambda now: True,
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=fake_send,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
    )
    assert routed is True
    assert calls["sent"] == 1


@pytest.mark.unit
def test_compute_desabo_time_window_exception_path():
    # Cause exception in early check by making webhooks_time_start incomparable
    class Bad:
        def __repr__(self):
            return "Bad()"

    now_local = datetime(2025, 10, 13, 8, 0, tzinfo=timezone.utc)
    early_ok, time_start_payload, window_ok = orch.compute_desabo_time_window(
        now_local=now_local,
        webhooks_time_start=Bad(),
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        within_window=False,
    )
    assert early_ok is False and time_start_payload is None and window_ok is False


@pytest.mark.unit
def test_check_new_emails_and_trigger_webhook_delegation(monkeypatch):
    # Ensure delegation to legacy function returns value
    monkeypatch.setattr(
        orch, 'check_new_emails_and_trigger_webhook',
        orch.check_new_emails_and_trigger_webhook  # ensure symbol exists
    )
    # Patch in app_render legacy function target
    import app_render as ar
    # The attribute may not exist in app_render; create it for the duration of the test
    monkeypatch.setattr(ar, '_legacy_check_new_emails_and_trigger_webhook', lambda: 7, raising=False)
    assert orch.check_new_emails_and_trigger_webhook() == 7


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_valid_day_time_missing_url_still_returns_true(monkeypatch):
    # Force Thursday (weekday=3)
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 9, 10, 0, tzinfo=tz)
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    routed = orch.handle_presence_route(
        subject="Samedi présent",
        full_email_content="... samedi ...",
        email_id="e12",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=True,
        presence_true_url=None,  # missing URL
        presence_false_url=None,
        is_within_time_window_local=lambda now: True,
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=lambda **k: True,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    # Exclusivity is applied; returns True even without URL
    assert routed is True


@pytest.mark.unit
def test_handle_media_solution_route_match_but_send_returns_false():
    logger = SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None)
    ok = orch.handle_media_solution_route(
        subject="Média Solution - Missions Recadrage - Lot 7",
        full_email_content="Lien: https://www.dropbox.com/scl/fo/def",
        email_id="e13",
        processing_prefs={},
        tz_for_polling=timezone.utc,
        check_media_solution_pattern=lambda s,b,tz,l: {"matches": True, "delivery_time": "11h00"},
        extract_sender_email=lambda s: "from@example.com",
        sender_raw="from@example.com",
        send_makecom_webhook=lambda **kwargs: False,  # send fails
        mark_subject_group_processed=lambda gid: None,
        subject_group_id="sg3",
        logger=logger,
    )
    assert ok is False


@pytest.mark.unit
def test_handle_media_solution_route_excluded_by_body_only_keyword():
    logger = SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None)
    processing_prefs = {"exclude_keywords_recadrage": ["forbidden-body"]}
    ok = orch.handle_media_solution_route(
        subject="MS Recadrage",
        full_email_content="This contains forbidden-body token.",
        email_id="e14",
        processing_prefs=processing_prefs,
        tz_for_polling=timezone.utc,
        check_media_solution_pattern=lambda s,b,tz,l: {"matches": True, "delivery_time": "12h00"},
        extract_sender_email=lambda s: "from@example.com",
        sender_raw="from@example.com",
        send_makecom_webhook=lambda **kwargs: True,
        mark_subject_group_processed=lambda gid: None,
        subject_group_id=None,
        logger=logger,
    )
    assert ok is False


@pytest.mark.unit
def test_send_custom_webhook_flow_200_success_false_returns_false():
    class Resp:
        status_code = 200
        content = b"{}"
        def json(self):
            return {"success": False, "message": "Not processed"}
        text = "{}"

    calls = {"logs": [], "records": 0}
    def record_send_event():
        calls["records"] += 1
    def append_webhook_log(entry):
        calls["logs"].append(entry)

    cont = orch.send_custom_webhook_flow(
        email_id="e15",
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
        mark_email_id_as_processed_redis=lambda eid: False,
        mark_email_as_read_imap=lambda *a, **k: None,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=SimpleNamespace(post=lambda *a, **k: Resp()),
        time=SimpleNamespace(sleep=lambda s: None),
        logger=SimpleNamespace(error=lambda *a, **k: None),
    )
    assert cont is False
    assert any(l.get("status") == "error" for l in calls["logs"])


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_false_flag_invalid_url_still_routes_true(monkeypatch):
    # Force Thursday (weekday=3)
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 9, 10, 0, tzinfo=tz)
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    sent = {}
    def fake_send(**kwargs):
        sent['called'] = True
        sent['override_webhook_url'] = kwargs.get('override_webhook_url')
        return True

    routed = orch.handle_presence_route(
        subject="Samedi présent",
        full_email_content="... samedi ...",
        email_id="e18",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=False,
        presence_true_url=None,
        presence_false_url="not-a-url",
        is_within_time_window_local=lambda now: True,
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=fake_send,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert routed is True
    assert sent.get('called') is True
    assert sent.get('override_webhook_url') == "not-a-url"


@pytest.mark.unit
def test_send_custom_webhook_flow_200_json_without_success_returns_false():
    class Resp:
        status_code = 200
        content = b"{\"message\":\"ok\"}"
        def json(self):
            return {"message": "ok"}
        text = "{\"message\":\"ok\"}"
    calls = {"logs": []}
    def append_webhook_log(entry):
        calls["logs"].append(entry)

    cont = orch.send_custom_webhook_flow(
        email_id="e19",
        subject="s",
        payload_for_webhook={},
        delivery_links=['x'],
        webhook_url="https://example.com/hook",
        webhook_ssl_verify=True,
        allow_without_links=True,
        processing_prefs={"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1},
        rate_limit_allow_send=lambda: True,
        record_send_event=lambda: None,
        append_webhook_log=append_webhook_log,
        mark_email_id_as_processed_redis=lambda eid: False,
        mark_email_as_read_imap=lambda *a, **k: None,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=SimpleNamespace(post=lambda *a, **k: Resp()),
        time=SimpleNamespace(sleep=lambda s: None),
        logger=SimpleNamespace(error=lambda *a, **k: None),
    )
    assert cont is False
    assert any(l.get("status") == "error" for l in calls["logs"])


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.unit
def test_handle_presence_route_false_flag_sends_false_url(monkeypatch):
    # Force Friday (weekday=4)
    class FakeDT:
        @classmethod
        def now(cls, tz):
            return datetime(2025, 10, 10, 10, 0, tzinfo=tz)
    monkeypatch.setattr(orch, 'datetime', FakeDT)

    sent = {}
    def fake_send(**kwargs):
        sent['called'] = True
        sent['override_webhook_url'] = kwargs.get('override_webhook_url')
        return True

    routed = orch.handle_presence_route(
        subject="Samedi présent",
        full_email_content="... samedi ...",
        email_id="e16",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        presence_flag=False,
        presence_true_url=None,
        presence_false_url="https://hook.eu2.make.com/false",
        is_within_time_window_local=lambda now: True,
        extract_sender_email=lambda s: "from@example.com",
        send_makecom_webhook=fake_send,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, warning=lambda *a, **k: None),
    )
    assert routed is True
    assert sent.get('called') is True
    assert sent.get('override_webhook_url') == "https://hook.eu2.make.com/false"


@pytest.mark.unit
def test_send_custom_webhook_flow_200_empty_content_returns_false():
    class Resp:
        status_code = 200
        content = b""  # empty
        text = ""
        def json(self):
            return {}
    calls = {"logs": []}
    def append_webhook_log(entry):
        calls["logs"].append(entry)

    cont = orch.send_custom_webhook_flow(
        email_id="e17",
        subject="s",
        payload_for_webhook={},
        delivery_links=['x'],
        webhook_url="https://example.com/hook",
        webhook_ssl_verify=True,
        allow_without_links=True,
        processing_prefs={"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1},
        rate_limit_allow_send=lambda: True,
        record_send_event=lambda: None,
        append_webhook_log=append_webhook_log,
        mark_email_id_as_processed_redis=lambda eid: False,
        mark_email_as_read_imap=lambda *a, **k: None,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=SimpleNamespace(post=lambda *a, **k: Resp()),
        time=SimpleNamespace(sleep=lambda s: None),
        logger=SimpleNamespace(error=lambda *a, **k: None),
    )
    assert cont is False
    assert any(l.get("status") == "error" for l in calls["logs"])


@pytest.mark.unit
def test_send_custom_webhook_flow_http_400_error_logs_and_returns_false():
    class Resp:
        status_code = 400
        text = "Bad"
        content = b"{\"message\": \"Bad\"}"
        def json(self):
            return {"message": "Bad"}
    calls = {"records": 0, "logs": []}
    def record_send_event():
        calls["records"] += 1
    def append_webhook_log(entry):
        calls["logs"].append(entry)

    cont = orch.send_custom_webhook_flow(
        email_id="e9",
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
        mark_email_id_as_processed_redis=lambda eid: False,
        mark_email_as_read_imap=lambda *a, **k: None,
        mail=SimpleNamespace(),
        email_num=1,
        urlparse=None,
        requests=SimpleNamespace(post=lambda *a, **k: Resp()),
        time=SimpleNamespace(sleep=lambda s: None),
        logger=SimpleNamespace(error=lambda *a, **k: None),
    )
    assert cont is False
    assert calls["records"] == 1
    assert any(l.get("status") == "error" for l in calls["logs"])  # error logged


@pytest.mark.unit
def test_send_custom_webhook_flow_raises_after_retries(monkeypatch):
    calls = {"post": 0, "records": 0}
    class BadRequests:
        @staticmethod
        def post(*a, **k):
            calls["post"] += 1
            raise RuntimeError("network down")
    def record_send_event():
        calls["records"] += 1

    with pytest.raises(RuntimeError):
        orch.send_custom_webhook_flow(
            email_id="e10",
            subject="s",
            payload_for_webhook={},
            delivery_links=['x'],
            webhook_url="https://example.com/hook",
            webhook_ssl_verify=True,
            allow_without_links=True,
            processing_prefs={"retry_count": 1, "retry_delay_sec": 0, "webhook_timeout_sec": 1},
            rate_limit_allow_send=lambda: True,
            record_send_event=record_send_event,
            append_webhook_log=lambda *a, **k: None,
            mark_email_id_as_processed_redis=lambda eid: False,
            mark_email_as_read_imap=lambda *a, **k: None,
            mail=SimpleNamespace(),
            email_num=1,
            urlparse=None,
            requests=BadRequests,
            time=SimpleNamespace(sleep=lambda s: None),
            logger=SimpleNamespace(warning=lambda *a, **k: None),
        )
    # Should have attempted 2 posts (retry_count + 1)
    assert calls["post"] == 2
    assert calls["records"] == 1


@pytest.mark.unit
def test_handle_desabo_route_outside_window_returns_false(monkeypatch):
    # DESABO requires window_ok True; simulate outside
    routed = orch.handle_desabo_route(
        subject="Je veux me désabonner",
        full_email_content="corps",
        html_email_content="",
        email_id="e11",
        sender_raw="from@example.com",
        tz_for_polling=timezone.utc,
        webhooks_time_start=None,
        webhooks_time_start_str="09:00",
        webhooks_time_end_str="17:00",
        processing_prefs={},
        extract_sender_email=lambda s: "from@example.com",
        check_desabo_conditions=lambda a,b,c: {"matches": True, "has_dropbox_request": True},
        build_desabo_make_payload=lambda **k: {},
        send_makecom_webhook=lambda **k: True,
        override_webhook_url="https://hook.eu2.make.com/xyz",
        mark_subject_group_processed=lambda gid: None,
        subject_group_id="sg1",
        is_within_time_window_local=lambda now: False,
        logger=SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None, error=lambda *a, **k: None),
    )
    assert routed is False
