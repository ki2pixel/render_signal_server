from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _auth_headers() -> dict:
    return {"Authorization": "Bearer test-process-api-token"}


@pytest.mark.unit
def test_ingress_gmail_unauthorized(flask_client):
    # Given: a request without Authorization header
    payload = {"subject": "Hello", "sender": "a@b.com", "body": "hello", "date": ""}

    # When: posting to the ingress endpoint
    resp = flask_client.post("/api/ingress/gmail", json=payload)

    # Then: the request is rejected
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["success"] is False


@pytest.mark.unit
def test_ingress_gmail_invalid_json_payload(flask_client):
    # Given: a request with invalid JSON body

    # When: posting invalid JSON
    resp = flask_client.post(
        "/api/ingress/gmail",
        data="not-json",
        headers={**_auth_headers(), "Content-Type": "application/json"},
    )

    # Then: 400 is returned
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


@pytest.mark.unit
def test_ingress_gmail_missing_required_fields(flask_client):
    # Given: a request missing required fields
    payload = {"subject": "Hello", "sender": "", "body": "", "date": ""}

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: 400 is returned
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


@pytest.mark.unit
def test_ingress_gmail_skips_sender_not_allowed(monkeypatch, flask_client):
    # Given: Gmail Push has a sender allowlist that does not include the sender
    import app_render

    monkeypatch.setattr(app_render, "GMAIL_SENDER_ALLOWLIST", ["allowed@example.com"])

    mark_mock = MagicMock(return_value=True)
    monkeypatch.setattr(app_render, "mark_email_id_as_processed_redis", mark_mock)

    payload = {
        "subject": "Hello",
        "sender": "blocked@example.com",
        "body": "hello",
        "date": "2026-01-01T00:00:00Z",
    }

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: it is skipped (best-effort marked processed)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "skipped_sender_not_allowed"
    assert mark_mock.call_count == 1


@pytest.mark.unit
def test_ingress_gmail_webhook_sending_disabled(monkeypatch, flask_client):
    # Given: webhook sending is disabled
    import app_render

    monkeypatch.setattr(app_render, "SENDER_LIST_FOR_POLLING", [])

    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._is_webhook_sending_enabled",
        lambda: False,
    )

    payload = {
        "subject": "Hello",
        "sender": "sender@example.com",
        "body": "hello",
        "date": "2026-01-01T00:00:00Z",
    }

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: conflict returned
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["success"] is False


@pytest.mark.unit
def test_ingress_gmail_skips_recadrage_outside_time_window(monkeypatch, flask_client):
    # Given: detector=recadrage and time window is not within
    import app_render

    monkeypatch.setattr(app_render, "SENDER_LIST_FOR_POLLING", [])

    monkeypatch.setattr(
        "routes.api_ingress.pattern_matching.check_media_solution_pattern",
        lambda *_args, **_kwargs: {"matches": True, "delivery_time": "10h00"},
    )
    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._load_webhook_global_time_window",
        lambda: ("09:00", "10:00"),
    )
    monkeypatch.setattr("routes.api_ingress.parse_time_hhmm", lambda *_a, **_k: object())
    monkeypatch.setattr("routes.api_ingress.is_within_time_window_local", lambda *_a, **_k: False)

    payload = {
        "subject": "Média Solution - Missions Recadrage - Lot 42",
        "sender": "sender@example.com",
        "body": "hello https://www.dropbox.com/scl/fo/abc123",
        "date": "2026-01-01T00:00:00Z",
    }

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: it is skipped
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["success"] is False
    assert data["message"] == "Webhook sending disabled"


@pytest.mark.unit
def test_ingress_gmail_happy_path(monkeypatch, flask_client):
    # Given: system is configured and send_custom_webhook_flow succeeds
    import app_render

    monkeypatch.setattr(app_render, "SENDER_LIST_FOR_POLLING", [])

    monkeypatch.setattr(app_render, "is_email_id_processed_redis", lambda *_a, **_k: False)
    monkeypatch.setattr(app_render, "_rate_limit_allow_send", lambda: True)
    monkeypatch.setattr(app_render, "_record_send_event", lambda: None)
    monkeypatch.setattr(app_render, "_append_webhook_log", lambda *_a, **_k: None)
    monkeypatch.setattr(app_render, "mark_email_id_as_processed_redis", lambda *_a, **_k: True)

    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._is_webhook_sending_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._get_webhook_config_dict",
        lambda: {"webhook_url": "https://example.com/webhook", "webhook_ssl_verify": True},
    )

    send_mock = MagicMock(return_value=False)
    monkeypatch.setattr("routes.api_ingress.email_orchestrator.send_custom_webhook_flow", send_mock)

    payload = {
        "subject": "Hello",
        "sender": "sender@example.com",
        "body": "hello https://www.dropbox.com/scl/fo/abc123",
        "date": "2026-01-01T00:00:00Z",
    }

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: it is processed and underlying flow is called
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "processed"
    assert send_mock.call_count == 1


@pytest.mark.unit
def test_ingress_gmail_enriches_delivery_links_with_r2_when_enabled(monkeypatch, flask_client):
    # Given: R2 transfer is enabled and returns an r2_url
    import app_render

    monkeypatch.setattr(app_render, "SENDER_LIST_FOR_POLLING", [])
    monkeypatch.setattr(app_render, "is_email_id_processed_redis", lambda *_a, **_k: False)
    monkeypatch.setattr(app_render, "_rate_limit_allow_send", lambda: True)
    monkeypatch.setattr(app_render, "_record_send_event", lambda: None)
    monkeypatch.setattr(app_render, "_append_webhook_log", lambda *_a, **_k: None)
    monkeypatch.setattr(app_render, "mark_email_id_as_processed_redis", lambda *_a, **_k: True)

    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._is_webhook_sending_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._get_webhook_config_dict",
        lambda: {"webhook_url": "https://example.com/webhook", "webhook_ssl_verify": True},
    )

    class _FakeR2:
        def is_enabled(self):
            return True

        def normalize_source_url(self, source_url, provider):
            return source_url

        def request_remote_fetch(self, *, source_url, provider, email_id=None, timeout=30):
            return ("https://media.example.com/r2-object", "file.zip")

        def persist_link_pair(self, *, source_url, r2_url, provider, original_filename=None):
            return True

    monkeypatch.setattr("routes.api_ingress.R2TransferService", MagicMock(get_instance=lambda: _FakeR2()))

    captured = {}

    def _capture_send(*, delivery_links, **kwargs):
        captured["delivery_links"] = delivery_links
        return False

    monkeypatch.setattr("routes.api_ingress.email_orchestrator.send_custom_webhook_flow", _capture_send)

    payload = {
        "subject": "Hello",
        "sender": "sender@example.com",
        "body": "hello https://www.dropbox.com/scl/fo/abc123",
        "date": "2026-01-01T00:00:00Z",
    }

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: delivery_links includes an r2_url for PHP logging
    assert resp.status_code == 200
    assert isinstance(captured.get("delivery_links"), list)
    assert len(captured["delivery_links"]) >= 1
    assert captured["delivery_links"][0].get("r2_url") == "https://media.example.com/r2-object"
    assert captured["delivery_links"][0].get("original_filename") == "file.zip"


@pytest.mark.unit
def test_ingress_gmail_r2_errors_do_not_block_send(monkeypatch, flask_client):
    # Given: R2 transfer is enabled but remote fetch errors
    import app_render

    monkeypatch.setattr(app_render, "SENDER_LIST_FOR_POLLING", [])
    monkeypatch.setattr(app_render, "is_email_id_processed_redis", lambda *_a, **_k: False)
    monkeypatch.setattr(app_render, "_rate_limit_allow_send", lambda: True)
    monkeypatch.setattr(app_render, "_record_send_event", lambda: None)
    monkeypatch.setattr(app_render, "_append_webhook_log", lambda *_a, **_k: None)
    monkeypatch.setattr(app_render, "mark_email_id_as_processed_redis", lambda *_a, **_k: True)

    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._is_webhook_sending_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "routes.api_ingress.email_orchestrator._get_webhook_config_dict",
        lambda: {"webhook_url": "https://example.com/webhook", "webhook_ssl_verify": True},
    )

    class _FakeR2:
        def is_enabled(self):
            return True

        def normalize_source_url(self, source_url, provider):
            return source_url

        def request_remote_fetch(self, *, source_url, provider, email_id=None, timeout=30):
            raise RuntimeError("worker down")

    monkeypatch.setattr("routes.api_ingress.R2TransferService", MagicMock(get_instance=lambda: _FakeR2()))

    captured = {}

    def _capture_send(*, delivery_links, **kwargs):
        captured["delivery_links"] = delivery_links
        return False

    monkeypatch.setattr("routes.api_ingress.email_orchestrator.send_custom_webhook_flow", _capture_send)

    payload = {
        "subject": "Hello",
        "sender": "sender@example.com",
        "body": "hello https://www.dropbox.com/scl/fo/abc123",
        "date": "2026-01-01T00:00:00Z",
    }

    # When: posting to ingress
    resp = flask_client.post("/api/ingress/gmail", json=payload, headers=_auth_headers())

    # Then: request succeeds and delivery_links does not include r2_url
    assert resp.status_code == 200
    assert isinstance(captured.get("delivery_links"), list)
    assert len(captured["delivery_links"]) >= 1
    assert captured["delivery_links"][0].get("provider") == "dropbox"
    assert "r2_url" not in captured["delivery_links"][0]
