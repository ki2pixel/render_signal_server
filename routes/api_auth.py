from __future__ import annotations

from flask import Blueprint, jsonify, current_app, url_for
from flask_login import login_required, current_user

from services import MagicLinkService

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")

_magic_link_service = MagicLinkService.get_instance()


@bp.route("/magic-link", methods=["POST"])
@login_required
def create_magic_link():
    """Génère un magic link à usage unique pour accéder au dashboard."""
    try:
        token, expires_at = _magic_link_service.generate_token()
        magic_link = url_for(
            "dashboard.consume_magic_link_token",
            token=token,
            _external=True,
        )
        current_app.logger.info(
            "MAGIC_LINK: user '%s' generated a token expiring at %s",
            getattr(current_user, "id", "unknown"),
            expires_at.isoformat(),
        )
        return (
            jsonify(
                {
                    "success": True,
                    "magic_link": magic_link,
                    "expires_at": expires_at.isoformat(),
                }
            ),
            201,
        )
    except Exception as exc:  # pragma: no cover - defensive
        current_app.logger.error("MAGIC_LINK: generation failure: %s", exc)
        return jsonify({"success": False, "message": "Impossible de générer un magic link."}), 500
