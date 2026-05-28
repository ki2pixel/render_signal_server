from __future__ import annotations

import sys
from flask import Blueprint, jsonify, request, Response

from services import AuthService, ConfigService

bp = Blueprint("api_ingress", __name__, url_prefix="/api/ingress")

_config_service = ConfigService()
_auth_service = AuthService(_config_service)


@bp.route("/gmail", methods=["POST"])
def ingest_gmail() -> tuple[Response, int] | Response:
    if not _auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Invalid JSON payload"}), 400

    ar = sys.modules.get("app_render")
    if ar is None:
        return jsonify({"success": False, "message": "Server not ready"}), 503

    ingress_service = getattr(ar, "_ingress_service", None)
    if not ingress_service:
        return jsonify({"success": False, "message": "Service unavailable"}), 503

    result, status_code = ingress_service.process_gmail_push(payload)
    return jsonify(result), status_code