import pytest
from types import SimpleNamespace


@pytest.mark.integration
def test_r2_worker_failure_does_not_break_webhook_send_exception(monkeypatch):
    # // Given: an IMAP email containing a Dropbox link and an R2 service that raises
    from email_processing import orchestrator as orch
    import app_render as ar
    import services

    dropbox_url = "https://www.dropbox.com/scl/fo/abc123"

    class FakeR2Service:
        def is_enabled(self):
            return True

        def normalize_source_url(self, source_url, provider):
            return source_url

        def request_remote_fetch(self, **kwargs):
            raise RuntimeError("worker down")

        def persist_link_pair(self, **kwargs):
            return True

    monkeypatch.setattr(services.R2TransferService, "get_instance", lambda: FakeR2Service())

    captured = {"posts": []}

    class Resp:
        status_code = 200
        content = b"{\"success\": true}"
        text = "{\"success\": true}"

        def json(self):
            return {"success": True}

    def fake_post(url, json=None, **kwargs):
        captured["posts"].append({"url": url, "json": json, "kwargs": kwargs})
        return Resp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    class FakeMail:
        def select(self, box):
            return ("OK", [])

        def search(self, *_):
            return ("OK", [b"1"])

        def fetch(self, num, *_):
            raw = (
                b"Subject: Test R2 exception\r\n"
                b"From: allowed@example.com\r\n"
                b"Date: Wed, 22 Oct 2025 10:00:00 +0200\r\n"
                b"Message-ID: <r2-exception@example.com>\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"\r\n"
                + f"Lien: {dropbox_url}\r\n".encode("utf-8")
            )
            return ("OK", [(b"1", raw)])

    monkeypatch.setattr(ar, "_legacy_check_new_emails_and_trigger_webhook", None, raising=False)
    monkeypatch.setattr(ar, "create_imap_connection", lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, "close_imap_connection", lambda m: None, raising=False)
    monkeypatch.setattr(ar, "decode_email_header", lambda s: s, raising=False)
    monkeypatch.setattr(ar, "extract_sender_email", lambda s: "allowed@example.com", raising=False)
    monkeypatch.setattr(ar, "is_email_id_processed_redis", lambda eid: False, raising=False)
    monkeypatch.setattr(ar, "mark_email_id_as_processed_redis", lambda eid: True, raising=False)
    monkeypatch.setattr(ar, "mark_email_as_read_imap", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ar, "generate_subject_group_id", lambda s: "g-r2-1", raising=False)
    monkeypatch.setattr(ar, "is_subject_group_processed", lambda gid: False, raising=False)
    monkeypatch.setattr(ar, "_rate_limit_allow_send", lambda: True, raising=False)
    monkeypatch.setattr(ar, "_record_send_event", lambda: None, raising=False)
    monkeypatch.setattr(ar, "_append_webhook_log", lambda e: None, raising=False)
    monkeypatch.setattr(ar, "WEBHOOK_URL", "https://example.com/hook", raising=False)
    monkeypatch.setattr(ar, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", True, raising=False)
    monkeypatch.setattr(ar, "PROCESSING_PREFS", {"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1}, raising=False)
    monkeypatch.setattr(ar, "SENDER_LIST_FOR_POLLING", ["allowed@example.com"], raising=False)
    monkeypatch.setattr(ar, "TZ_FOR_POLLING", orch.timezone.utc, raising=False)
    monkeypatch.setattr(
        ar,
        "app",
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

    monkeypatch.setattr(orch, "_is_webhook_sending_enabled", lambda: True, raising=False)
    monkeypatch.setattr(orch, "is_within_time_window_local", lambda *a, **k: True, raising=False)

    # // When: running a full polling cycle
    cnt = orch.check_new_emails_and_trigger_webhook()

    # // Then: webhook is sent and raw_url is preserved (no r2_url)
    assert cnt == 1
    assert len(captured["posts"]) == 1
    sent_json = captured["posts"][0]["json"] or {}
    links = sent_json.get("delivery_links") or []
    assert links and isinstance(links, list)
    assert links[0].get("raw_url") == dropbox_url
    assert ("r2_url" not in links[0]) or (links[0].get("r2_url") is None)


@pytest.mark.integration
def test_r2_worker_failure_does_not_break_webhook_send_none(monkeypatch):
    # // Given: an IMAP email containing a Dropbox link and an R2 service that returns None
    from email_processing import orchestrator as orch
    import app_render as ar
    import services

    dropbox_url = "https://www.dropbox.com/scl/fo/abc123"

    class FakeR2Service:
        def is_enabled(self):
            return True

        def normalize_source_url(self, source_url, provider):
            return source_url

        def request_remote_fetch(self, **kwargs):
            return None

        def persist_link_pair(self, **kwargs):
            return True

    monkeypatch.setattr(services.R2TransferService, "get_instance", lambda: FakeR2Service())

    captured = {"posts": []}

    class Resp:
        status_code = 200
        content = b"{\"success\": true}"
        text = "{\"success\": true}"

        def json(self):
            return {"success": True}

    def fake_post(url, json=None, **kwargs):
        captured["posts"].append({"url": url, "json": json, "kwargs": kwargs})
        return Resp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    class FakeMail:
        def select(self, box):
            return ("OK", [])

        def search(self, *_):
            return ("OK", [b"1"])

        def fetch(self, num, *_):
            raw = (
                b"Subject: Test R2 none\r\n"
                b"From: allowed@example.com\r\n"
                b"Date: Wed, 22 Oct 2025 10:00:00 +0200\r\n"
                b"Message-ID: <r2-none@example.com>\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"\r\n"
                + f"Lien: {dropbox_url}\r\n".encode("utf-8")
            )
            return ("OK", [(b"1", raw)])

    monkeypatch.setattr(ar, "_legacy_check_new_emails_and_trigger_webhook", None, raising=False)
    monkeypatch.setattr(ar, "create_imap_connection", lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, "close_imap_connection", lambda m: None, raising=False)
    monkeypatch.setattr(ar, "decode_email_header", lambda s: s, raising=False)
    monkeypatch.setattr(ar, "extract_sender_email", lambda s: "allowed@example.com", raising=False)
    monkeypatch.setattr(ar, "is_email_id_processed_redis", lambda eid: False, raising=False)
    monkeypatch.setattr(ar, "mark_email_id_as_processed_redis", lambda eid: True, raising=False)
    monkeypatch.setattr(ar, "mark_email_as_read_imap", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ar, "generate_subject_group_id", lambda s: "g-r2-2", raising=False)
    monkeypatch.setattr(ar, "is_subject_group_processed", lambda gid: False, raising=False)
    monkeypatch.setattr(ar, "_rate_limit_allow_send", lambda: True, raising=False)
    monkeypatch.setattr(ar, "_record_send_event", lambda: None, raising=False)
    monkeypatch.setattr(ar, "_append_webhook_log", lambda e: None, raising=False)
    monkeypatch.setattr(ar, "WEBHOOK_URL", "https://example.com/hook", raising=False)
    monkeypatch.setattr(ar, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", True, raising=False)
    monkeypatch.setattr(ar, "PROCESSING_PREFS", {"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1}, raising=False)
    monkeypatch.setattr(ar, "SENDER_LIST_FOR_POLLING", ["allowed@example.com"], raising=False)
    monkeypatch.setattr(ar, "TZ_FOR_POLLING", orch.timezone.utc, raising=False)
    monkeypatch.setattr(
        ar,
        "app",
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

    monkeypatch.setattr(orch, "_is_webhook_sending_enabled", lambda: True, raising=False)
    monkeypatch.setattr(orch, "is_within_time_window_local", lambda *a, **k: True, raising=False)

    # // When: running a full polling cycle
    cnt = orch.check_new_emails_and_trigger_webhook()

    # // Then: webhook is sent and raw_url is preserved (no r2_url)
    assert cnt == 1
    assert len(captured["posts"]) == 1
    sent_json = captured["posts"][0]["json"] or {}
    links = sent_json.get("delivery_links") or []
    assert links and isinstance(links, list)
    assert links[0].get("raw_url") == dropbox_url
    assert ("r2_url" not in links[0]) or (links[0].get("r2_url") is None)


@pytest.mark.integration
def test_html_body_over_1mb_is_truncated_and_warning_logged(monkeypatch):
    # // Given: an IMAP email with a >1MB HTML part
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from email_processing import orchestrator as orch
    import app_render as ar

    dropbox_url = "https://www.dropbox.com/scl/fo/abc123"

    html_padding = "A" * (orch.MAX_HTML_BYTES + 100)
    html_text = f"<html><body>Lien: {dropbox_url} {html_padding}</body></html>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Test HTML huge"
    msg["From"] = "allowed@example.com"
    msg["Date"] = "Wed, 22 Oct 2025 10:00:00 +0200"
    msg["Message-ID"] = "<huge-html@example.com>"
    msg.attach(MIMEText("plain", "plain", "utf-8"))
    msg.attach(MIMEText(html_text, "html", "utf-8"))

    raw_bytes = msg.as_bytes()

    captured = {"posts": []}

    class Resp:
        status_code = 200
        content = b"{\"success\": true}"
        text = "{\"success\": true}"

        def json(self):
            return {"success": True}

    def fake_post(url, json=None, **kwargs):
        captured["posts"].append({"url": url, "json": json, "kwargs": kwargs})
        return Resp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    class FakeMail:
        def select(self, box):
            return ("OK", [])

        def search(self, *_):
            return ("OK", [b"1"])

        def fetch(self, num, *_):
            return ("OK", [(b"1", raw_bytes)])

    logger_calls = {"warnings": []}

    def warn(*args, **kwargs):
        if args:
            logger_calls["warnings"].append(args[0])

    monkeypatch.setattr(ar, "_legacy_check_new_emails_and_trigger_webhook", None, raising=False)
    monkeypatch.setattr(ar, "create_imap_connection", lambda: FakeMail(), raising=False)
    monkeypatch.setattr(ar, "close_imap_connection", lambda m: None, raising=False)
    monkeypatch.setattr(ar, "decode_email_header", lambda s: s, raising=False)
    monkeypatch.setattr(ar, "extract_sender_email", lambda s: "allowed@example.com", raising=False)
    monkeypatch.setattr(ar, "is_email_id_processed_redis", lambda eid: False, raising=False)
    monkeypatch.setattr(ar, "mark_email_id_as_processed_redis", lambda eid: True, raising=False)
    monkeypatch.setattr(ar, "mark_email_as_read_imap", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ar, "generate_subject_group_id", lambda s: "g-html-1", raising=False)
    monkeypatch.setattr(ar, "is_subject_group_processed", lambda gid: False, raising=False)
    monkeypatch.setattr(ar, "_rate_limit_allow_send", lambda: True, raising=False)
    monkeypatch.setattr(ar, "_record_send_event", lambda: None, raising=False)
    monkeypatch.setattr(ar, "_append_webhook_log", lambda e: None, raising=False)
    monkeypatch.setattr(ar, "WEBHOOK_URL", "https://example.com/hook", raising=False)
    monkeypatch.setattr(ar, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", True, raising=False)
    monkeypatch.setattr(ar, "PROCESSING_PREFS", {"retry_count": 0, "retry_delay_sec": 0, "webhook_timeout_sec": 1}, raising=False)
    monkeypatch.setattr(ar, "SENDER_LIST_FOR_POLLING", ["allowed@example.com"], raising=False)
    monkeypatch.setattr(ar, "TZ_FOR_POLLING", orch.timezone.utc, raising=False)
    monkeypatch.setattr(
        ar,
        "app",
        SimpleNamespace(
            logger=SimpleNamespace(
                info=lambda *a, **k: None,
                warning=warn,
                error=lambda *a, **k: None,
                debug=lambda *a, **k: None,
            )
        ),
        raising=False,
    )

    monkeypatch.setattr(orch, "_is_webhook_sending_enabled", lambda: True, raising=False)
    monkeypatch.setattr(orch, "is_within_time_window_local", lambda *a, **k: True, raising=False)

    # // When: running a full polling cycle
    cnt = orch.check_new_emails_and_trigger_webhook()

    # // Then: HTML is truncated (and warning is logged) and webhook still sent
    assert cnt == 1
    assert any(w == "HTML content truncated (exceeded 1MB limit)" for w in logger_calls["warnings"])
    assert len(captured["posts"]) == 1
    sent_json = captured["posts"][0]["json"] or {}
    email_content = sent_json.get("email_content") or ""
    assert dropbox_url in email_content
    assert len(email_content.encode("utf-8", errors="ignore")) <= (orch.MAX_HTML_BYTES + 1024)
