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

# Region host: default EU
MAKE_HOST = os.environ.get("MAKE_API_HOST", "eu1.make.com").strip()
API_BASE = f"https://{MAKE_HOST}/api/v2"
HEADERS = {"Authorization": f"Token {MAKECOM_API_KEY}"}

TIMEOUT_SEC = 15


def _scenario_action_url(scenario_id: int, enable: bool) -> str:
    action = "start" if enable else "stop"
    return f"{API_BASE}/scenarios/{scenario_id}/{action}"


def _call_make_scenario(scenario_id: int, enable: bool) -> Tuple[bool, str, int]:
    url = _scenario_action_url(scenario_id, enable)
    try:
        resp = requests.post(url, headers=HEADERS, timeout=TIMEOUT_SEC)
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
