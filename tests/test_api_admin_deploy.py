import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_requests_get(monkeypatch):
    calls = []

    def _factory(status_code=202, json_data=None, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        if json_data is None:
            resp.json.side_effect = ValueError("no json")
            resp.text = text
        else:
            resp.json.return_value = json_data
        return resp

    def _set(status_code=202, json_data=None, text=""):
        resp = _factory(status_code=status_code, json_data=json_data, text=text)
        from routes import api_admin
        monkeypatch.setattr(api_admin.requests, "get", lambda *a, **k: resp)
        calls.append(resp)
        return resp

    return _set


@pytest.fixture
def mock_requests_post(monkeypatch):
    calls = []

    def _factory(status_code=201, json_data=None, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        if json_data is None:
            resp.json.side_effect = ValueError("no json")
            resp.text = text
        else:
            resp.json.return_value = json_data
        return resp

    def _set(status_code=201, json_data=None, text=""):
        resp = _factory(status_code=status_code, json_data=json_data, text=text)
        from routes import api_admin
        monkeypatch.setattr(api_admin.requests, "post", lambda *a, **k: resp)
        calls.append(resp)
        return resp

    return _set


@pytest.fixture
def mock_popen(monkeypatch):
    popen = MagicMock()
    from routes import api_admin
    monkeypatch.setattr(api_admin.subprocess, "Popen", popen)
    return popen


def _set_render_config(monkeypatch, **overrides):
    from routes import api_admin

    # Base config
    cfg = {
        "api_key": "",
        "service_id": "",
        "deploy_hook_url": "",
        "clear_cache": "do_not_clear",
    }
    cfg.update(overrides)
    monkeypatch.setattr(
        api_admin._config_service, "get_render_config", lambda: cfg
    )
    return cfg


def test_deploy_via_render_hook_success(authenticated_flask_client, monkeypatch, mock_requests_get):
    # Arrange: valid hook URL, requests.get returns success
    _set_render_config(
        monkeypatch,
        deploy_hook_url="https://api.render.com/deploy/svc_123?key=secret",
        api_key="",
        service_id="",
    )
    mock_requests_get(status_code=202)

    # Act
    resp = authenticated_flask_client.post("/api/deploy_application")

    # Assert
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "Deploy Hook" in data["message"]


def test_deploy_via_render_hook_invalid_prefix(authenticated_flask_client, monkeypatch):
    # Arrange: invalid hook URL prefix
    _set_render_config(
        monkeypatch,
        deploy_hook_url="https://example.com/deploy/svc_123?key=secret",
        api_key="",
        service_id="",
    )

    # Act
    resp = authenticated_flask_client.post("/api/deploy_application")

    # Assert
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "invalide" in data["message"].lower()


def test_deploy_via_render_api_success(authenticated_flask_client, monkeypatch, mock_requests_post):
    # Arrange: no hook; API credentials provided
    _set_render_config(
        monkeypatch,
        deploy_hook_url="",
        api_key="rk_live_abc",
        service_id="svc_456",
        clear_cache="do_not_clear",
    )
    mock_requests_post(status_code=201, json_data={"id": "dep_1", "status": "queued"})

    # Act
    resp = authenticated_flask_client.post("/api/deploy_application")

    # Assert
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["deploy_id"] == "dep_1"
    assert data["status"] == "queued"


def test_deploy_fallback_local(authenticated_flask_client, monkeypatch, mock_popen):
    # Arrange: no hook and no API credentials
    _set_render_config(
        monkeypatch,
        deploy_hook_url="",
        api_key="",
        service_id="",
    )

    # Act
    resp = authenticated_flask_client.post("/api/deploy_application")

    # Assert
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    # ensure subprocess was invoked for fallback command
    assert mock_popen.called
