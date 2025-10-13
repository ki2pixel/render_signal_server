from flask import Blueprint, jsonify

# Health check blueprint
bp = Blueprint("health", __name__)


@bp.route("/health", methods=["GET"])  # Simple liveness endpoint
def health():
    return jsonify({"status": "ok"}), 200
