from flask import Blueprint, jsonify, Response

# Health check blueprint
bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])
def health() -> Response | tuple[Response, int]:
    return jsonify({"status": "ok"}), 200
