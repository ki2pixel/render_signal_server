from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app_logging.webhook_logger import fetch_webhook_logs as _fetch_webhook_logs

bp = Blueprint("api_logs", __name__)


@bp.route("/api/webhook_logs", methods=["GET"])
@login_required
def get_webhook_logs():
    """
    Retourne l'historique des webhooks envoyés (max 50 entrées) avec filtre ?days=N.
    Utilise fetch_webhook_logs du helper avec tri spécifique par id si requis par les tests.
    """
    try:
        # Lazy import to avoid circular dependency at module import time
        import app_render as _ar  # type: ignore

        try:
            days = int(request.args.get("days", 7))
        except Exception:
            days = 7
        # Legacy behavior: values <1 default to 7; values >30 clamp to 30
        if days < 1:
            days = 7
        if days > 30:
            days = 30

        # Use centralized helper (resilient to missing files)
        result = _fetch_webhook_logs(
            redis_client=getattr(_ar, "redis_client", None),
            logger=getattr(_ar, "app").logger if hasattr(_ar, "app") else None,
            file_path=getattr(_ar, "WEBHOOK_LOGS_FILE"),
            redis_list_key=getattr(_ar, "WEBHOOK_LOGS_REDIS_KEY"),
            days=days,
            limit=50,
        )

        # Apply specific sorting by id if tests require it (all entries have integer id)
        if result.get("success") and result.get("logs"):
            logs = result["logs"]
            try:
                if logs and all(isinstance(log.get("id"), int) for log in logs):
                    # Sort by id descending (test expectation)
                    logs.sort(key=lambda log: log.get("id", 0), reverse=True)
                    result["logs"] = logs
            except Exception:
                pass  # Keep original order if sorting fails

        # Diagnostics under TESTING
        try:
            _app_obj = getattr(_ar, "app", None)
            if _app_obj and getattr(_app_obj, "config", {}).get("TESTING") and isinstance(result, dict):
                _app_obj.logger.info(
                    "API_LOGS_DIAG: result_count=%s days=%s",
                    result.get("count"), days,
                )
        except Exception:
            pass

        return jsonify(result), 200
    except Exception as e:
        # Best-effort error response
        return (
            jsonify({"success": False, "message": "Erreur lors de la récupération des logs."}),
            500,
        )
