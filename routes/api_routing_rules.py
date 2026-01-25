from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config import app_config_store as _store
from services.routing_rules_service import RoutingRulesService

bp = Blueprint("api_routing_rules", __name__, url_prefix="/api/routing_rules")

ROUTING_RULES_FILE = Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"

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


@bp.route("", methods=["GET"])
@login_required
def get_routing_rules():
    try:
        payload = _load_routing_rules()
        return jsonify({"success": True, "config": payload}), 200
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
