"""
Unit tests for routes/api_utility.py to increase coverage:
- ping()
- check_local_workflow_trigger() for present/absent and malformed JSON
- api_get_local_status() (login required)
"""
import json
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_ping_returns_pong(flask_client):
    r = flask_client.get('/api/ping')
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "pong"
    assert "timestamp_utc" in data


@pytest.mark.unit
def test_check_trigger_absent(tmp_path, flask_client):
    from routes import api_utility as mod

    with patch.object(mod, 'TRIGGER_SIGNAL_FILE', tmp_path / 'trigger.json'):
        r = flask_client.get('/api/check_trigger')
        assert r.status_code == 200
        data = r.get_json()
        assert data == {"command_pending": False, "payload": None}


@pytest.mark.unit
def test_check_trigger_present_valid_json(tmp_path, flask_client):
    from routes import api_utility as mod

    p = tmp_path / 'trigger.json'
    p.write_text(json.dumps({"action": "start", "job_id": 1}), encoding='utf-8')

    with patch.object(mod, 'TRIGGER_SIGNAL_FILE', p):
        r = flask_client.get('/api/check_trigger')
        assert r.status_code == 200
        data = r.get_json()
        assert data["command_pending"] is True
        assert data["payload"]["action"] == "start"
        # File should be removed after read
        assert p.exists() is False


@pytest.mark.unit
def test_check_trigger_present_malformed_json(tmp_path, flask_client):
    from routes import api_utility as mod

    p = tmp_path / 'trigger.json'
    p.write_text('{not-json}', encoding='utf-8')

    with patch.object(mod, 'TRIGGER_SIGNAL_FILE', p):
        r = flask_client.get('/api/check_trigger')
        assert r.status_code == 200
        data = r.get_json()
        # payload becomes None on parse error, still command_pending True then cleared
        assert data["command_pending"] is True
        assert data["payload"] is None
        assert p.exists() is False


@pytest.mark.integration
def test_get_local_status_authenticated(authenticated_flask_client):
    r = authenticated_flask_client.get('/api/get_local_status')
    assert r.status_code == 200
    data = r.get_json()
    # Verify structure stays stable for UI
    for key in [
        'overall_status_text', 'status_text', 'overall_status_code_from_worker',
        'progress_current', 'progress_total', 'current_step_name', 'recent_downloads'
    ]:
        assert key in data
