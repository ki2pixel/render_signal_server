from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from services.routing_rules_service import RoutingRulesService


class _DummyStore:
    def __init__(self) -> None:
        self.saved: dict | None = None
        self.set_calls: int = 0

    def get_config_json(self, key: str, file_fallback: Path | None = None) -> dict | None:
        return self.saved

    def set_config_json(self, key: str, value: dict, file_fallback: Path | None = None) -> bool:
        self.saved = value
        self.set_calls += 1
        return True


@pytest.fixture(autouse=True)
def reset_service_singleton():
    RoutingRulesService.reset_instance()
    yield
    RoutingRulesService.reset_instance()


@pytest.fixture
def temp_rules_file(tmp_path: Path) -> Path:
    return tmp_path / "routing_rules.json"


def _build_rule(name: str = "Factures", *, webhook: str = "https://hook.eu2.make.com/abc") -> list[dict]:
    return [
        {
            "id": "r1",
            "name": name,
            "conditions": [
                {"field": "sender", "operator": "contains", "value": "@client.com"}
            ],
            "actions": {"webhook_url": webhook, "priority": "high", "stop_processing": True},
        }
    ]


def test_update_rules_success_sets_timestamp_and_persists(temp_rules_file: Path):
    store = _DummyStore()
    service = RoutingRulesService.get_instance(file_path=temp_rules_file, external_store=store)

    ok, msg, payload = service.update_rules(_build_rule())

    assert ok is True
    assert msg == "Règles mises à jour."
    assert isinstance(payload.get("_updated_at"), str)
    assert store.saved is not None
    assert store.set_calls == 1
    saved_rule = store.saved["rules"][0]
    assert saved_rule["actions"]["webhook_url"].startswith("https://")


def test_update_rules_refuses_rules_without_conditions(temp_rules_file: Path):
    service = RoutingRulesService.get_instance(file_path=temp_rules_file, external_store=_DummyStore())
    invalid_rules = [
        {
            "id": "r2",
            "name": "Sans condition",
            "conditions": [],
            "actions": {"webhook_url": "https://hook.eu2.make.com/test"},
        }
    ]

    ok, msg, payload = service.update_rules(invalid_rules)

    assert ok is False
    assert "condition" in msg.lower()
    assert payload["rules"] == []


def test_get_rules_reload_reads_from_store(temp_rules_file: Path):
    store = _DummyStore()
    store.saved = {
        "rules": _build_rule("Support"),
        "_updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    service = RoutingRulesService.get_instance(file_path=temp_rules_file, external_store=store)

    service.reload()
    rules = service.get_rules()

    assert len(rules) == 1
    assert rules[0]["name"] == "Support"
    assert rules[0]["actions"]["priority"] == "high"
