import pytest


def _stub_invoke(monkeypatch, exit_code=0, log="OK", expected_keys=None):
    from routes import api_admin

    def _fake(keys):
        if expected_keys is not None:
            assert tuple(keys) == expected_keys
        return exit_code, log

    monkeypatch.setattr(api_admin, "_invoke_config_migration", _fake)


def _stub_verify(monkeypatch, exit_code=0, results=None, expected_keys=None):
    from routes import api_admin

    def _fake(keys, raw=False):
        if expected_keys is not None:
            assert tuple(keys) == expected_keys
        return exit_code, results or [
            {"key": "polling_config", "valid": True, "message": "ok", "summary": "_updated_at=..."}
        ]

    monkeypatch.setattr(api_admin, "_run_config_store_verification", _fake)


@pytest.mark.unit
def test_migrate_configs_success_with_custom_keys(authenticated_flask_client, monkeypatch):
    desired = ("processing_prefs", "webhook_config")
    _stub_invoke(monkeypatch, exit_code=0, log="ALL GOOD", expected_keys=desired)

    resp = authenticated_flask_client.post(
        "/api/migrate_configs_to_redis",
        json={"keys": list(desired)},
    )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["keys"] == list(desired)
    assert "ALL GOOD" in data["log"]


@pytest.mark.unit
def test_migrate_configs_uses_defaults_when_no_keys(authenticated_flask_client, monkeypatch):
    from routes import api_admin

    _stub_invoke(monkeypatch, exit_code=0, expected_keys=api_admin.ALLOWED_CONFIG_KEYS)

    resp = authenticated_flask_client.post("/api/migrate_configs_to_redis")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["keys"] == list(api_admin.ALLOWED_CONFIG_KEYS)


@pytest.mark.unit
def test_migrate_configs_invalid_key_returns_400(authenticated_flask_client):
    resp = authenticated_flask_client.post(
        "/api/migrate_configs_to_redis",
        json={"keys": ["unknown_key"]},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "invalides" in data["message"].lower()


@pytest.mark.unit
def test_migrate_configs_exit_code_nonzero_returns_502(authenticated_flask_client, monkeypatch):
    _stub_invoke(monkeypatch, exit_code=1, log="FAILED")

    resp = authenticated_flask_client.post("/api/migrate_configs_to_redis")

    assert resp.status_code == 502
    data = resp.get_json()
    assert data["success"] is False
    assert data["exit_code"] == 1
    assert data["log"] == "FAILED"


@pytest.mark.unit
def test_verify_config_store_success_defaults(authenticated_flask_client, monkeypatch):
    from routes import api_admin

    sample = [
        {"key": "polling_config", "valid": True, "message": "ok", "summary": "_updated_at=2026-01-19"},
    ]
    _stub_verify(monkeypatch, exit_code=0, results=sample, expected_keys=api_admin.ALLOWED_CONFIG_KEYS)

    resp = authenticated_flask_client.post("/api/verify_config_store")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["results"] == sample


@pytest.mark.unit
def test_verify_config_store_invalid_key_returns_400(authenticated_flask_client):
    resp = authenticated_flask_client.post(
        "/api/verify_config_store",
        json={"keys": ["invalid_key"]},
    )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "invalides" in data["message"].lower()


@pytest.mark.unit
def test_verify_config_store_exit_code_nonzero_returns_502(authenticated_flask_client, monkeypatch):
    _stub_verify(monkeypatch, exit_code=1, results=[{"key": "polling_config", "valid": False, "message": "missing _updated_at", "summary": "missing"}])

    resp = authenticated_flask_client.post("/api/verify_config_store")

    assert resp.status_code == 502
    data = resp.get_json()
    assert data["success"] is False
    assert data["exit_code"] == 1
