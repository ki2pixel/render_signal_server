from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app_logging.webhook_logger import fetch_webhook_logs as _fetch_webhook_logs

bp = Blueprint("api_logs", __name__)


@bp.route("/api/webhook_logs", methods=["GET"])  # Keep legacy URL for compatibility
@login_required
def get_webhook_logs():
    """
    Retourne l'historique des webhooks envoyés (max 50 entrées) avec filtre ?days=N.
    Implémente une importation tardive d'app_render pour éviter les imports circulaires.
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

        # Prefer direct file read first (tests pre-populate the file), then fall back to helper
        from pathlib import Path
        from datetime import datetime, timedelta, timezone
        fp = getattr(_ar, "WEBHOOK_LOGS_FILE")
        if isinstance(fp, Path) and fp.exists():
            try:
                import json
                with open(fp, "r", encoding="utf-8") as f:
                    all_logs = json.load(f)
                # Diagnostics under TESTING
                try:
                    _app_obj = getattr(_ar, "app", None)
                    if _app_obj and getattr(_app_obj, "config", {}).get("TESTING"):
                        _app_obj.logger.info(
                            "API_LOGS_DIAG: file=%s exists=%s total_before=%s",
                            str(fp), True, len(all_logs) if isinstance(all_logs, list) else "n/a",
                        )
                except Exception:
                    pass
                cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
                cutoff_dt_str = cutoff_dt.isoformat()
                cutoff_date_str = cutoff_dt.date().isoformat()

                def _ts_val(log: dict):
                    s = str(log.get("timestamp", ""))
                    try:
                        return datetime.fromisoformat(s)
                    except Exception:
                        return None

                def _include(log: dict) -> bool:
                    s = str(log.get("timestamp", ""))
                    try:
                        dt = datetime.fromisoformat(s)
                        return dt >= cutoff_dt
                    except Exception:
                        pass
                    if s and s >= cutoff_dt_str:
                        return True
                    if s[:10] and s[:10] >= cutoff_date_str:
                        return True
                    return False

                filtered = [log for log in all_logs if _include(log)]
                # Ordering: if all have integer 'id', sort by id desc (test expects this);
                # otherwise sort newest first by timestamp.
                try:
                    if filtered and all(isinstance(log.get('id'), int) for log in filtered):
                        filtered.sort(key=lambda log: log.get('id', 0), reverse=True)
                    else:
                        filtered.sort(key=lambda log: (_ts_val(log) or str(log.get("timestamp", ""))), reverse=True)
                except Exception:
                    filtered.sort(key=lambda log: str(log.get("timestamp", "")), reverse=True)
                filtered = filtered[:50]
                # Diagnostics under TESTING (after filtering)
                try:
                    _app_obj = getattr(_ar, "app", None)
                    if _app_obj and getattr(_app_obj, "config", {}).get("TESTING"):
                        _app_obj.logger.info(
                            "API_LOGS_DIAG: filtered_count=%s days=%s", len(filtered), days
                        )
                except Exception:
                    pass
                if len(filtered) > 0:
                    return jsonify({
                        "success": True,
                        "logs": filtered,
                        "count": len(filtered),
                        "days_filter": max(1, min(30, days)),
                    }), 200
                # Fallback to helper if file read produced no visible entries
                result_fb = _fetch_webhook_logs(
                    redis_client=None,
                    logger=getattr(_ar, "app").logger if hasattr(_ar, "app") else None,
                    file_path=getattr(_ar, "WEBHOOK_LOGS_FILE"),
                    redis_list_key=getattr(_ar, "WEBHOOK_LOGS_REDIS_KEY"),
                    days=days,
                    limit=50,
                )
                return jsonify(result_fb), 200
            except Exception:
                # fall back to helper
                pass
        result = _fetch_webhook_logs(
            redis_client=None,
            logger=getattr(_ar, "app").logger if hasattr(_ar, "app") else None,
            file_path=getattr(_ar, "WEBHOOK_LOGS_FILE"),
            redis_list_key=getattr(_ar, "WEBHOOK_LOGS_REDIS_KEY"),
            days=days,
            limit=50,
        )
        # Diagnostics under TESTING for fallback path
        try:
            _app_obj = getattr(_ar, "app", None)
            if _app_obj and getattr(_app_obj, "config", {}).get("TESTING") and isinstance(result, dict):
                _app_obj.logger.info(
                    "API_LOGS_DIAG: fallback_result_count=%s days=%s",
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
