"""
Additional integration tests for routes/api_config.py
"""
import json
from unittest.mock import patch

import pytest


@pytest.mark.integration
def test_time_window_set_invalid_returns_400(authenticated_flask_client):
    # Missing one bound
    r = authenticated_flask_client.post(
        '/api/set_webhook_time_window',
        json={"start": "09h00", "end": ""},
        content_type='application/json',
    )
    assert r.status_code == 400
    data = r.get_json(); assert data["success"] is False


@pytest.mark.integration
def test_time_window_set_and_get_reflects(authenticated_flask_client, tmp_path):
    # Point the override file inside module via patch
    from config import webhook_time_window as wtw
    override = tmp_path / "webhook_time_window.json"
    with patch.object(wtw, 'TIME_WINDOW_OVERRIDE_FILE', override):
        # Set valid
        r = authenticated_flask_client.post(
            '/api/set_webhook_time_window',
            json={"start": "09:00", "end": "17h00"},
            content_type='application/json',
        )
        assert r.status_code == 200
        data = r.get_json(); assert data["success"] is True
        # Get reflects
        r2 = authenticated_flask_client.get('/api/get_webhook_time_window')
        assert r2.status_code == 200
        info = r2.get_json(); assert info["success"] is True
        assert info["webhooks_time_start"] in ("09h00", "09:00")
        assert info["webhooks_time_end"].startswith("17")


@pytest.mark.integration
def test_runtime_flags_update_and_get(authenticated_flask_client, tmp_path):
    # Patch flags file path to temp via module-level settings
    from routes import api_config as api_cfg
    with patch.object(api_cfg, 'RUNTIME_FLAGS_FILE', tmp_path / 'runtime_flags.json'):
        # Update flags
        payload = {"disable_email_id_dedup": True, "allow_custom_webhook_without_links": False}
        r = authenticated_flask_client.post('/api/update_runtime_flags', json=payload, content_type='application/json')
        assert r.status_code == 200
        data = r.get_json(); assert data["success"] is True
        # Get reflects
        r2 = authenticated_flask_client.get('/api/get_runtime_flags')
        assert r2.status_code == 200
        flags = r2.get_json()["flags"]
        assert flags["disable_email_id_dedup"] is True
        assert flags["allow_custom_webhook_without_links"] is False


@pytest.mark.integration
def test_update_polling_config_invalid_values_return_400(authenticated_flask_client, tmp_path):
    from routes import api_config as api_cfg
    with patch.object(api_cfg, 'POLLING_CONFIG_FILE', tmp_path / 'polling.json'):
        # invalid start hour
        r1 = authenticated_flask_client.post('/api/update_polling_config', json={"active_start_hour": 999}, content_type='application/json')
        assert r1.status_code == 400
        # invalid end hour
        r2 = authenticated_flask_client.post('/api/update_polling_config', json={"active_end_hour": -1}, content_type='application/json')
        assert r2.status_code == 400
        # invalid vacation formats
        r3 = authenticated_flask_client.post('/api/update_polling_config', json={"vacation_start": "2025/01/01"}, content_type='application/json')
        assert r3.status_code == 400
        r4 = authenticated_flask_client.post('/api/update_polling_config', json={"vacation_end": "01-01-2025"}, content_type='application/json')
        assert r4.status_code == 400
        # start> end yields 400
        r5 = authenticated_flask_client.post('/api/update_polling_config', json={"vacation_start": "2025-10-13", "vacation_end": "2025-10-12"}, content_type='application/json')
        assert r5.status_code == 400
