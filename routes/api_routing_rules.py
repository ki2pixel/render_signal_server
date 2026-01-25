from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config import app_config_store as _store
from services.routing_rules_service import RoutingRulesService

bp = Blueprint("api_routing_rules", __name__, url_prefix="/api/routing_rules")

ROUTING_RULES_FILE = Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"
WEBHOOK_CONFIG_FILE = Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"

try:
    _routing_rules_service = RoutingRulesService.get_instance()
except ValueError:
    _routing_rules_service = RoutingRulesService.get_instance(
        file_path=ROUTING_RULES_FILE,
        external_store=_store,
    )


def _load_routing_rules() -> dict:
    """Charge les règles persistées (cache rechargé)."""
    _routing_rules_service.reload()
    return _routing_rules_service.get_payload()


def _resolve_backend_webhook_url() -> str | None:
    try:
        persisted = _store.get_config_json("webhook_config", file_fallback=WEBHOOK_CONFIG_FILE) or {}
    except Exception:
        persisted = {}
    if isinstance(persisted, dict):
        webhook_url = persisted.get("webhook_url")
        if isinstance(webhook_url, str) and webhook_url.strip():
            return webhook_url.strip()

    try:
        from config import settings as _settings

        fallback_url = getattr(_settings, "WEBHOOK_URL", "")
        if isinstance(fallback_url, str) and fallback_url.strip():
            return fallback_url.strip()
    except Exception:
        return None
    return None


def _build_backend_fallback_rule() -> dict | None:
    webhook_url = _resolve_backend_webhook_url()
    if not webhook_url:
        return None
    # Pourquoi : rendre visible la règle backend (webhook par défaut) lorsqu'aucune règle UI n'existe.
    return {
        "id": "backend-default",
        "name": "Webhook par défaut (backend)",
        "conditions": [
            {
                "field": "subject",
                "operator": "regex",
                "value": ".*",
                "case_sensitive": False,
            }
        ],
        "actions": {
            "webhook_url": webhook_url,
            "priority": "normal",
            "stop_processing": False,
        },
    }


@bp.route("", methods=["GET"])
@login_required
def get_routing_rules():
    try:
        payload = _load_routing_rules()
        rules = payload.get("rules") if isinstance(payload, dict) else None
        fallback_rule = None
        if not isinstance(rules, list) or not rules:
            fallback_rule = _build_backend_fallback_rule()
        response_payload = {"success": True, "config": payload}
        if fallback_rule is not None:
            response_payload["fallback_rule"] = fallback_rule
        return jsonify(response_payload), 200
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500


@bp.route("", methods=["POST"])
@login_required
def update_routing_rules():
    try:
        payload = request.get_json(silent=True) or {}
        rules_raw = payload.get("rules")
        ok, msg, updated = _routing_rules_service.update_rules(rules_raw)  # type: ignore[arg-type]
        if not ok:
            return jsonify({"success": False, "message": msg}), 400
        return jsonify({"success": True, "message": msg, "config": updated}), 200
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500
