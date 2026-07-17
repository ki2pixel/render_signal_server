from __future__ import annotations

import os
import socket
import sys
from flask import Blueprint, current_app, jsonify, request, Response

bp = Blueprint("api_ingress", __name__, url_prefix="/api/ingress")


def _check_google_ip(ip: str) -> bool:
    """Verify that an IP address belongs to Google via reverse DNS lookup.

    Returns True if the hostname ends with .google.com or .googleusercontent.com.
    """
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname.endswith(".google.com") or hostname.endswith(".googleusercontent.com")
    except socket.herror:
        return False
    except Exception:
        try:
            current_app.logger.warning(
                "INGRESS_IP: Reverse DNS lookup failed for %s", ip, exc_info=True
            )
        except Exception:
            pass
        return False


def _get_auth_service():
    svc = getattr(current_app, "auth_service", None)
    if svc is not None:
        return svc
    ar = sys.modules.get("app_render")
    return getattr(ar, "_auth_service", None) if ar else None


def _get_ingress_service():
    svc = getattr(current_app, "ingress_service", None)
    if svc is not None:
        return svc
    ar = sys.modules.get("app_render")
    return getattr(ar, "_ingress_service", None) if ar else None


@bp.route("/gmail", methods=["POST"])
def ingest_gmail() -> tuple[Response, int] | Response:
    auth_service = _get_auth_service()
    if auth_service is None or not auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    # IP source filtering (SEC-10: restrict Gmail ingress to Google IP ranges)
    if os.environ.get("GMAIL_INGRESS_IP_CHECK_ENABLED", "").strip().lower() in ("1", "true", "yes"):
        client_ip = request.remote_addr
        if client_ip and not _check_google_ip(client_ip):
            try:
                current_app.logger.warning(
                    "INGRESS_IP: Blocked non-Google IP %s from Gmail ingress", client_ip
                )
            except Exception:
                pass
            return jsonify({"success": False, "message": "Forbidden: IP not from Google"}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Invalid JSON payload"}), 400

    ingress_service = _get_ingress_service()
    if not ingress_service:
        return jsonify({"success": False, "message": "Service unavailable"}), 503

    result, status_code = ingress_service.process_gmail_push(payload)
    return jsonify(result), status_code