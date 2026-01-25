from __future__ import annotations

from pathlib import Path
import re

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


def _resolve_sender_allowlist_pattern() -> str | None:
    try:
        from config import polling_config as _polling_config
        from config import settings as _settings

        service = _polling_config.PollingConfigService(
            settings_module=_settings,
            config_store=_store,
        )
        senders = service.get_sender_list()
    except Exception:
        senders = []

    cleaned = []
    for sender in senders or []:
        if isinstance(sender, str) and sender.strip():
            cleaned.append(re.escape(sender.strip().lower()))

    if not cleaned:
        return None
    return rf"^({'|'.join(cleaned)})$"


def _build_backend_fallback_rules() -> list[dict] | None:
    webhook_url = _resolve_backend_webhook_url()
    if not webhook_url:
        return None

    sender_pattern = _resolve_sender_allowlist_pattern()
    sender_condition = None
    if sender_pattern:
        sender_condition = {
            "field": "sender",
            "operator": "regex",
            "value": sender_pattern,
            "case_sensitive": False,
        }

    recadrage_conditions = []
    if sender_condition:
        recadrage_conditions.append(dict(sender_condition))
    recadrage_conditions.extend(
        [
            {
                "field": "subject",
                "operator": "regex",
                "value": r"m[ée]dia solution.*missions recadrage.*\blot\b",
                "case_sensitive": False,
            },
            {
                "field": "body",
                "operator": "regex",
                "value": r"(dropbox\.com/scl/fo|fromsmash\.com/|swisstransfer\.com/d/)",
                "case_sensitive": False,
            },
        ]
    )

    desabo_subject_conditions = []
    if sender_condition:
        desabo_subject_conditions.append(dict(sender_condition))
    desabo_subject_conditions.extend(
        [
            {
                "field": "subject",
                "operator": "regex",
                "value": r"d[ée]sabonn",
                "case_sensitive": False,
            },
            {
                "field": "body",
                "operator": "contains",
                "value": "journee",
                "case_sensitive": False,
            },
            {
                "field": "body",
                "operator": "contains",
                "value": "tarifs habituels",
                "case_sensitive": False,
            },
        ]
    )

    desabo_body_conditions = []
    if sender_condition:
        desabo_body_conditions.append(dict(sender_condition))
    desabo_body_conditions.extend(
        [
            {
                "field": "body",
                "operator": "regex",
                "value": r"(d[ée]sabonn|dropbox\.com/request/)",
                "case_sensitive": False,
            },
            {
                "field": "body",
                "operator": "contains",
                "value": "journee",
                "case_sensitive": False,
            },
            {
                "field": "body",
                "operator": "contains",
                "value": "tarifs habituels",
                "case_sensitive": False,
            },
        ]
    )

    # Pourquoi : exposer la logique Recadrage/Désabo existante en règles UI modifiables.
    return [
        {
            "id": "backend-recadrage",
            "name": "Confirmation Mission Recadrage (backend)",
            "conditions": recadrage_conditions,
            "actions": {
                "webhook_url": webhook_url,
                "priority": "normal",
                "stop_processing": False,
            },
        },
        {
            "id": "backend-desabo-subject",
            "name": "Confirmation Disponibilité Mission Recadrage (backend - sujet)",
            "conditions": desabo_subject_conditions,
            "actions": {
                "webhook_url": webhook_url,
                "priority": "normal",
                "stop_processing": False,
            },
        },
        {
            "id": "backend-desabo-body",
            "name": "Confirmation Disponibilité Mission Recadrage (backend - corps)",
            "conditions": desabo_body_conditions,
            "actions": {
                "webhook_url": webhook_url,
                "priority": "normal",
                "stop_processing": False,
            },
        },
    ]


def _is_legacy_backend_default_rule(rule: dict) -> bool:
    if not isinstance(rule, dict):
        return False
    rule_id = str(rule.get("id") or "").strip()
    rule_name = str(rule.get("name") or "").strip()
    if rule_id != "backend-default" and rule_name != "Webhook par défaut (backend)":
        return False
    conditions = rule.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != 1:
        return False
    condition = conditions[0]
    if not isinstance(condition, dict):
        return False
    return (
        str(condition.get("field") or "").strip().lower() == "subject"
        and str(condition.get("operator") or "").strip().lower() == "regex"
        and str(condition.get("value") or "").strip() == ".*"
        and bool(condition.get("case_sensitive", False)) is False
    )


@bp.route("", methods=["GET"])
@login_required
def get_routing_rules():
    try:
        payload = _load_routing_rules()
        rules = payload.get("rules") if isinstance(payload, dict) else None
        response_config = payload if isinstance(payload, dict) else {}
        if isinstance(rules, list) and len(rules) == 1 and _is_legacy_backend_default_rule(rules[0]):
            response_config = dict(response_config)
            response_config["rules"] = []
            rules = []
        fallback_rules = None
        if not isinstance(rules, list) or not rules:
            fallback_rules = _build_backend_fallback_rules()
        response_payload = {"success": True, "config": response_config}
        if fallback_rules:
            response_payload["fallback_rules"] = fallback_rules
            response_payload["fallback_rule"] = fallback_rules[0]
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
