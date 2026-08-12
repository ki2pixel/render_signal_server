from __future__ import annotations

import pytest
from unittest.mock import MagicMock


def _testapi_headers() -> dict:
    return {"X-API-Key": "test-api-key"}


@pytest.mark.unit
def test_send_test_webhook_dry_run_unauthorized(flask_client):
    # Given: no TEST_API_KEY configured and no X-API-Key header
    payload = {"subject": "Test", "delivery_links": []}

    # When: posting to the dry-run endpoint
    resp = flask_client.post("/api/test/send_test_webhook", json=payload)

    # Then: the request is rejected with 401
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["success"] is False


@pytest.mark.unit
def test_send_test_webhook_dry_run_returns_preview_without_sending(monkeypatch, flask_client):
    # Given: TEST_API_KEY is configured
    import os
    os.environ["TEST_API_KEY"] = "test-api-key"

    # And: the real send flow is mocked to detect any call
    send_mock = MagicMock()
    monkeypatch.setattr(
        "email_processing.orchestrator.send_custom_webhook_flow",
        send_mock,
    )

    payload = {
        "dry_run": True,
        "email_id": "test-email-1",
        "subject": "Test Dry Run",
        "delivery_links": [
            {"provider": "fromsmash", "raw_url": "https://fromsmash.com/abc"}
        ],
        "payload": {"sender_email": "achats@media-solution.fr"},
    }

    # When: posting to the dry-run endpoint
    resp = flask_client.post(
        "/api/test/send_test_webhook", json=payload, headers=_testapi_headers()
    )

    # Then: a preview is returned and no real send happened
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["dry_run"] is True
    assert data["payload"]["sender_email"] == "achats@media-solution.fr"
    assert data["payload"]["delivery_links"] == payload["delivery_links"]
    assert data["payload_size_bytes"] > 0
    assert isinstance(data["delivery_mode_sequence"], list)
    assert data["delivery_mode_sequence"]
    send_mock.assert_not_called()


@pytest.mark.unit
def test_send_test_webhook_dry_run_uses_config_target(monkeypatch, flask_client):
    # Given: TEST_API_KEY is configured and the persisted webhook config
    # contains the real target endpoint
    import os
    os.environ["TEST_API_KEY"] = "test-api-key"
    os.environ.pop("WEBHOOK_URL", None)

    monkeypatch.setattr(
        "email_processing.orchestrator._get_webhook_config_dict",
        lambda: {"webhook_url": "https://webhook.kidpixel.fr/index.php", "webhook_delivery_mode": "json", "webhook_fallback_on_415": True},
    )

    payload = {"dry_run": True, "subject": "Test", "delivery_links": []}

    # When: posting to the dry-run endpoint
    resp = flask_client.post(
        "/api/test/send_test_webhook", json=payload, headers=_testapi_headers()
    )

    # Then: the effective target is the configured endpoint (masked path)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["target_url"] == "https://webhook.kidpixel.fr/index.php"
    assert data["dry_run"] is True


@pytest.mark.unit
def test_send_test_webhook_dry_run_uses_masked_default_target(monkeypatch, flask_client):
    # Given: TEST_API_KEY is configured, no webhook URL configured and no env fallback
    import os
    from config import settings as _settings
    os.environ["TEST_API_KEY"] = "test-api-key"
    monkeypatch.setattr(_settings, "WEBHOOK_URL", "")

    monkeypatch.setattr(
        "email_processing.orchestrator._get_webhook_config_dict",
        lambda: {},
    )

    payload = {"dry_run": True, "subject": "Test", "delivery_links": []}

    # When: posting to the dry-run endpoint
    resp = flask_client.post(
        "/api/test/send_test_webhook", json=payload, headers=_testapi_headers()
    )

    # Then: the fallback default target is used and the response reports it
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["target_url"] == "https://webhook.kidpixel.fr/index.php"
    assert data["fallback_note"] is not None


@pytest.mark.unit
def test_send_test_webhook_real_send_calls_flow(monkeypatch, flask_client):
    # Given: TEST_API_KEY is configured
    import os
    os.environ["TEST_API_KEY"] = "test-api-key"

    # And: the real send flow returns a falsy value (continue flow)
    send_mock = MagicMock(return_value=False)
    monkeypatch.setattr(
        "email_processing.orchestrator.send_custom_webhook_flow",
        send_mock,
    )

    payload = {
        "dry_run": False,
        "email_id": "test-email-2",
        "subject": "Test Real",
        "delivery_links": [],
    }

    # When: posting with dry_run=false
    resp = flask_client.post(
        "/api/test/send_test_webhook", json=payload, headers=_testapi_headers()
    )

    # Then: the flow was called once and the response reports the send
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["dry_run"] is False
    send_mock.assert_called_once()
    kwargs = send_mock.call_args.kwargs
    assert kwargs["email_id"] == "test-email-2"
    assert kwargs["webhook_url"].startswith("https://")
