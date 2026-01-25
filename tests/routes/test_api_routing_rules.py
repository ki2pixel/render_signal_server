from __future__ import annotations

import pytest

from services.routing_rules_service import RoutingRulesService


@pytest.fixture(autouse=True)
def reset_routing_rules_singleton():
    RoutingRulesService.reset_instance()
    yield
    RoutingRulesService.reset_instance()


def _stub_service(monkeypatch, payload=None, update_result=(True, "ok", {})):
    class _FakeService:
        def __init__(self):
            self.payload = payload or {"rules": [], "_updated_at": "ts"}
            self.update_result = update_result

        def reload(self) -> None:
            return None

        def get_payload(self) -> dict:
            return self.payload

        def update_rules(self, rules):
            return self.update_result

    fake = _FakeService()
    monkeypatch.setattr("routes.api_routing_rules._routing_rules_service", fake)
    return fake


@pytest.mark.unit
def test_get_routing_rules_success(authenticated_flask_client, monkeypatch):
    payload = {"rules": ["dummy"], "_updated_at": "2026-01-01"}
    _stub_service(monkeypatch, payload=payload)

    resp = authenticated_flask_client.get("/api/routing_rules")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["config"] == payload


@pytest.mark.unit
def test_update_routing_rules_success(authenticated_flask_client, monkeypatch):
    updated = {"rules": ["ok"], "_updated_at": "2026-01-02"}
    _stub_service(monkeypatch, update_result=(True, "saved", updated))

    resp = authenticated_flask_client.post("/api/routing_rules", json={"rules": []})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["message"] == "saved"
    assert data["config"] == updated


@pytest.mark.unit
def test_update_routing_rules_validation_error(authenticated_flask_client, monkeypatch):
    _stub_service(monkeypatch, update_result=(False, "Chaque règle doit contenir…", {}))

    resp = authenticated_flask_client.post("/api/routing_rules", json={"rules": []})

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert "règle" in data["message"].lower()
