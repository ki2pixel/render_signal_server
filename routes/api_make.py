from __future__ import annotations

import os
import requests
from typing import Dict, Tuple

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required

from config.settings import MAKECOM_API_KEY

bp = Blueprint("api_make", __name__, url_prefix="/api/make")
# Scenario IDs: can be overridden by env vars, fallback to provided IDs
# ENV overrides (optional): MAKE_SCENARIO_ID_AUTOREPONDEUR, MAKE_SCENARIO_ID_RECADRAGE, MAKE_SCENARIO_ID_PRESENCE_TRUE, MAKE_SCENARIO_ID_PRESENCE_FALSE
SCENARIO_IDS = {
    "autorepondeur": int(os.environ.get("MAKE_SCENARIO_ID_AUTOREPONDEUR", "7448207")),
    "recadrage": int(os.environ.get("MAKE_SCENARIO_ID_RECADRAGE", "6649843")),
    "presence_true": int(os.environ.get("MAKE_SCENARIO_ID_PRESENCE_TRUE", "7407389")),
    "presence_false": int(os.environ.get("MAKE_SCENARIO_ID_PRESENCE_FALSE", "7407408")),
}

# Configuration du webhook de contrôle (solution alternative)
MAKE_WEBHOOK_CONTROL_URL = os.environ.get("MAKE_WEBHOOK_CONTROL_URL", "").strip()
MAKE_WEBHOOK_API_KEY = os.environ.get("MAKE_WEBHOOK_API_KEY", "").strip()

# Configuration API directe (si webhook non configuré)
MAKE_HOST = os.environ.get("MAKE_API_HOST", "eu1.make.com").strip()
API_BASE = f"https://{MAKE_HOST}/api/v2"

# Auth type: Token (default) or Bearer (for OAuth access tokens)
MAKE_AUTH_TYPE = os.environ.get("MAKE_API_AUTH_TYPE", "Token").strip()
MAKE_ORG_ID = os.environ.get("MAKE_API_ORG_ID", "").strip()

TIMEOUT_SEC = 15


def build_headers() -> dict:
    headers = {}
    if MAKE_AUTH_TYPE.lower() == "bearer":
        headers["Authorization"] = f"Bearer {MAKECOM_API_KEY}"
    else:
        headers["Authorization"] = f"Token {MAKECOM_API_KEY}"
    if MAKE_ORG_ID:
        headers["X-Organization"] = MAKE_ORG_ID
    return headers


def _scenario_action_url(scenario_id: int, enable: bool) -> str:
    action = "start" if enable else "stop"
    return f"{API_BASE}/scenarios/{scenario_id}/{action}"


def _call_make_scenario(scenario_id: int, enable: bool) -> Tuple[bool, str, int]:
    """Appelle l'API Make soit directement, soit via webhook de contrôle"""
    action = "start" if enable else "stop"
    
    # Si webhook de contrôle configuré, l'utiliser
    if MAKE_WEBHOOK_CONTROL_URL and MAKE_WEBHOOK_API_KEY:
        try:
            response = requests.post(
                MAKE_WEBHOOK_CONTROL_URL,
                json={
                    "action": action,
                    "scenario_id": scenario_id,
                    "api_key": MAKE_WEBHOOK_API_KEY
                },
                timeout=TIMEOUT_SEC
            )
            ok = response.status_code == 200
            return ok, f"Webhook {action} for {scenario_id}", response.status_code
        except Exception as e:
            return False, f"Webhook error: {str(e)}", -1
    
    # Sinon, utiliser l'API directe
    url = _scenario_action_url(scenario_id, enable)
    try:
        resp = requests.post(url, headers=build_headers(), timeout=TIMEOUT_SEC)
        ok = resp.ok
        return ok, url, resp.status_code
    except Exception as e:
        return False, url, -1


# Exposed function for internal use from other blueprints
# Returns dict of results per scenario key

def toggle_all_scenarios(enable: bool, logger=None) -> Dict[str, dict]:
    results: Dict[str, dict] = {}
    for key, sid in SCENARIO_IDS.items():
        ok, url, status = _call_make_scenario(sid, enable)
        results[key] = {"scenario_id": sid, "ok": ok, "status": status, "url": url}
        if logger:
            logger.info(
                "MAKE API: %s scenario '%s' (id=%s) -> ok=%s status=%s",
                "start" if enable else "stop",
                key,
                sid,
                ok,
                status,
            )
    return results


@bp.route("/toggle_all", methods=["POST"])  # POST /api/make/toggle_all { enable: bool }
@login_required
def api_toggle_all():
    try:
        payload = request.get_json(silent=True) or {}
        enable = bool(payload.get("enable", False))
        if not MAKECOM_API_KEY:
            return jsonify({"success": False, "message": "Clé API Make manquante (MAKECOM_API_KEY)."}), 400
        res = toggle_all_scenarios(enable, logger=current_app.logger)
        return jsonify({"success": True, "enable": enable, "results": res}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne lors de l'appel Make."}), 500


@bp.route("/status_all", methods=["GET"])  # Optional placeholder; Make API lacks direct status endpoint
@login_required
def api_status_all():
    # Make n'expose pas de /status simple par scénario dans v2 publique.
    # On retourne simplement la configuration des IDs connus côté serveur.
    try:
        return jsonify({
            "success": True,
            "scenarios": {
                k: {"scenario_id": v} for k, v in SCENARIO_IDS.items()
            },
            "host": MAKE_HOST,
        }), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne."}), 500
