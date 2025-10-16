from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Tuple

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config import webhook_time_window, polling_config, settings
from config import app_config_store as _store
from config.runtime_flags import load_runtime_flags, save_runtime_flags
from config.settings import (
    RUNTIME_FLAGS_FILE,
    DISABLE_EMAIL_ID_DEDUP as DEFAULT_DISABLE_EMAIL_ID_DEDUP,
    ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS as DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS,
    POLLING_TIMEZONE_STR,
    EMAIL_POLLING_INTERVAL_SECONDS,
    POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
    POLLING_CONFIG_FILE,
)

bp = Blueprint("api_config", __name__, url_prefix="/api")

# Module-level aliases used by some tests to patch runtime values directly
# Note: primary source of truth remains config.settings; these aliases are
# provided for backward-compatibility with legacy tests.
POLLING_ACTIVE_DAYS = settings.POLLING_ACTIVE_DAYS
POLLING_ACTIVE_START_HOUR = settings.POLLING_ACTIVE_START_HOUR
POLLING_ACTIVE_END_HOUR = settings.POLLING_ACTIVE_END_HOUR
ENABLE_SUBJECT_GROUP_DEDUP = settings.ENABLE_SUBJECT_GROUP_DEDUP


def _load_runtime_flags_file() -> dict:
    defaults = {
        "disable_email_id_dedup": bool(DEFAULT_DISABLE_EMAIL_ID_DEDUP),
        "allow_custom_webhook_without_links": bool(DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
    }
    return load_runtime_flags(RUNTIME_FLAGS_FILE, defaults)


def _save_runtime_flags_file(data: dict) -> bool:
    return save_runtime_flags(RUNTIME_FLAGS_FILE, data)


# ---- Time window (session-protected) ----

@bp.route("/get_webhook_time_window", methods=["GET"])  # GET /api/get_webhook_time_window
@login_required
def get_webhook_time_window():
    try:
        # Best-effort: pull latest values from external store to reflect remote edits
        try:
            cfg = _store.get_config_json("webhook_config") or {}
            gs = (cfg.get("global_time_start") or "").strip()
            ge = (cfg.get("global_time_end") or "").strip()
            # If both provided (or both empty), sync into in-app state to keep orchestrator aligned
            if (gs != "" and ge != "") or (gs == "" and ge == ""):
                webhook_time_window.update_time_window(gs, ge)
        except Exception:
            pass
        info = webhook_time_window.get_time_window_info()
        return (
            jsonify(
                {
                    "success": True,
                    "webhooks_time_start": info.get("start") or None,
                    "webhooks_time_end": info.get("end") or None,
                    "timezone": POLLING_TIMEZONE_STR,
                }
            ),
            200,
        )
    except Exception:
        return jsonify({"success": False, "message": "Erreur lors de la récupération de la fenêtre horaire."}), 500


@bp.route("/set_webhook_time_window", methods=["POST"])  # POST /api/set_webhook_time_window
@login_required
def set_webhook_time_window():
    try:
        payload = request.get_json(silent=True) or {}
        start = payload.get("start", "")
        end = payload.get("end", "")
        ok, msg = webhook_time_window.update_time_window(start, end)
        status = 200 if ok else 400
        info = webhook_time_window.get_time_window_info()
        # Best-effort: mirror the global time window to external config store under
        # webhook_config as global_time_start/global_time_end so that
        # https://webhook.kidpixel.fr/data/app_config/webhook_config.json reflects it too.
        try:
            cfg = _store.get_config_json("webhook_config") or {}
            cfg["global_time_start"] = (info.get("start") or "") or None
            cfg["global_time_end"] = (info.get("end") or "") or None
            # Do not fail the request if external store is unavailable
            _store.set_config_json("webhook_config", cfg)
        except Exception:
            pass
        return (
            jsonify(
                {
                    "success": ok,
                    "message": msg,
                    "webhooks_time_start": info.get("start") or None,
                    "webhooks_time_end": info.get("end") or None,
                }
            ),
            status,
        )
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}), 500


# ---- Runtime flags (session-protected) ----

@bp.route("/get_runtime_flags", methods=["GET"])  # GET /api/get_runtime_flags
@login_required
def get_runtime_flags():
    try:
        data = _load_runtime_flags_file()
        return jsonify({"success": True, "flags": data}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500


@bp.route("/update_runtime_flags", methods=["POST"])  # POST /api/update_runtime_flags
@login_required
def update_runtime_flags():
    try:
        payload = request.get_json(silent=True) or {}
        data = _load_runtime_flags_file()
        if "disable_email_id_dedup" in payload:
            try:
                data["disable_email_id_dedup"] = bool(payload.get("disable_email_id_dedup"))
            except Exception:
                pass
        if "allow_custom_webhook_without_links" in payload:
            try:
                data["allow_custom_webhook_without_links"] = bool(payload.get("allow_custom_webhook_without_links"))
            except Exception:
                pass
        if not _save_runtime_flags_file(data):
            return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
        return jsonify({"success": True, "flags": data, "message": "Modifications enregistrées. Un redémarrage peut être nécessaire."}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500


# ---- Polling configuration (session-protected) ----

@bp.route("/get_polling_config", methods=["GET"])  # GET /api/get_polling_config
@login_required
def get_polling_config():
    try:
        # Prefer values from external store/file if available to reflect persisted UI choices
        persisted = _store.get_config_json("polling_config", file_fallback=POLLING_CONFIG_FILE) or {}
        cfg = {
            # Days and hours: prefer persisted values, else aliases for test patching
            "active_days": persisted.get("active_days", POLLING_ACTIVE_DAYS),
            "active_start_hour": persisted.get("active_start_hour", POLLING_ACTIVE_START_HOUR),
            "active_end_hour": persisted.get("active_end_hour", POLLING_ACTIVE_END_HOUR),
            # Dedup flag: prefer persisted
            "enable_subject_group_dedup": persisted.get("enable_subject_group_dedup", ENABLE_SUBJECT_GROUP_DEDUP),
            "timezone": POLLING_TIMEZONE_STR,
            "sender_of_interest_for_polling": persisted.get("sender_of_interest_for_polling", settings.SENDER_LIST_FOR_POLLING),
            "vacation_start": persisted.get("vacation_start", polling_config.POLLING_VACATION_START_DATE.isoformat() if polling_config.POLLING_VACATION_START_DATE else None),
            "vacation_end": persisted.get("vacation_end", polling_config.POLLING_VACATION_END_DATE.isoformat() if polling_config.POLLING_VACATION_END_DATE else None),
            # Global enable toggle: prefer persisted, fallback helper
            "enable_polling": persisted.get("enable_polling", polling_config.get_enable_polling(True)),
        }
        return jsonify({"success": True, "config": cfg}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration polling."}), 500


@bp.route("/update_polling_config", methods=["POST"])  # POST /api/update_polling_config
@login_required
def update_polling_config():
    try:
        payload = request.get_json(silent=True) or {}
        # Charger l'existant depuis le store (fallback fichier)
        existing: dict = _store.get_config_json("polling_config", file_fallback=POLLING_CONFIG_FILE) or {}

        # Normalisation des champs
        new_days = None
        if 'active_days' in payload:
            days_val = payload['active_days']
            parsed_days: list[int] = []
            if isinstance(days_val, str):
                parts = [p.strip() for p in days_val.split(',') if p.strip()]
                for p in parts:
                    if p.isdigit():
                        d = int(p)
                        if 0 <= d <= 6:
                            parsed_days.append(d)
            elif isinstance(days_val, list):
                for p in days_val:
                    try:
                        d = int(p)
                        if 0 <= d <= 6:
                            parsed_days.append(d)
                    except Exception:
                        continue
            if parsed_days:
                new_days = sorted(set(parsed_days))
            else:
                new_days = [0, 1, 2, 3, 4]

        new_start = None
        if 'active_start_hour' in payload:
            try:
                v = int(payload['active_start_hour'])
                if 0 <= v <= 23:
                    new_start = v
                else:
                    return jsonify({"success": False, "message": "active_start_hour doit être entre 0 et 23."}), 400
            except Exception:
                return jsonify({"success": False, "message": "active_start_hour invalide (entier attendu)."}), 400

        new_end = None
        if 'active_end_hour' in payload:
            try:
                v = int(payload['active_end_hour'])
                if 0 <= v <= 23:
                    new_end = v
                else:
                    return jsonify({"success": False, "message": "active_end_hour doit être entre 0 et 23."}), 400
            except Exception:
                return jsonify({"success": False, "message": "active_end_hour invalide (entier attendu)."}), 400

        new_dedup = None
        if 'enable_subject_group_dedup' in payload:
            new_dedup = bool(payload['enable_subject_group_dedup'])

        new_senders = None
        if 'sender_of_interest_for_polling' in payload:
            candidates = payload['sender_of_interest_for_polling']
            normalized: list[str] = []
            if isinstance(candidates, str):
                parts = [p.strip() for p in candidates.split(',') if p.strip()]
            elif isinstance(candidates, list):
                parts = [str(p).strip() for p in candidates if str(p).strip()]
            else:
                parts = []
            email_re = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
            for p in parts:
                low = p.lower()
                if email_re.match(low):
                    normalized.append(low)
            seen = set()
            unique_norm = []
            for s in normalized:
                if s not in seen:
                    seen.add(s)
                    unique_norm.append(s)
            new_senders = unique_norm

        # Vacation dates (ISO YYYY-MM-DD)
        new_vac_start = None
        if 'vacation_start' in payload:
            vs = payload['vacation_start']
            if vs in (None, ""):
                new_vac_start = None
            else:
                try:
                    new_vac_start = datetime.fromisoformat(str(vs)).date()
                except Exception:
                    return jsonify({"success": False, "message": "vacation_start invalide (format YYYY-MM-DD)."}), 400

        new_vac_end = None
        if 'vacation_end' in payload:
            ve = payload['vacation_end']
            if ve in (None, ""):
                new_vac_end = None
            else:
                try:
                    new_vac_end = datetime.fromisoformat(str(ve)).date()
                except Exception:
                    return jsonify({"success": False, "message": "vacation_end invalide (format YYYY-MM-DD)."}), 400

        if new_vac_start is not None and new_vac_end is not None and new_vac_start > new_vac_end:
            return jsonify({"success": False, "message": "vacation_start doit être <= vacation_end."}), 400

        # Global enable (boolean)
        new_enable_polling = None
        if 'enable_polling' in payload:
            try:
                new_enable_polling = bool(payload.get('enable_polling'))
            except Exception:
                new_enable_polling = None

        # Mettre à jour les variables runtime du module polling_config
        if new_vac_start is not None:
            polling_config.POLLING_VACATION_START_DATE = new_vac_start
        if new_vac_end is not None:
            polling_config.POLLING_VACATION_END_DATE = new_vac_end

        # Mettre à jour dynamiquement les réglages globaux utilisés par l'API/UI
        # Cela évite que des valeurs importées à l'initialisation restent figées.
        if new_days is not None:
            settings.POLLING_ACTIVE_DAYS = new_days
        if new_start is not None:
            settings.POLLING_ACTIVE_START_HOUR = new_start
        if new_end is not None:
            settings.POLLING_ACTIVE_END_HOUR = new_end
        if new_dedup is not None:
            settings.ENABLE_SUBJECT_GROUP_DEDUP = new_dedup
        if new_senders is not None:
            settings.SENDER_LIST_FOR_POLLING = new_senders

        # Persistance via store (avec fallback fichier)
        merged = dict(existing)
        if new_days is not None:
            merged['active_days'] = new_days
        if new_start is not None:
            merged['active_start_hour'] = new_start
        if new_end is not None:
            merged['active_end_hour'] = new_end
        if new_dedup is not None:
            merged['enable_subject_group_dedup'] = new_dedup
        if new_senders is not None:
            merged['sender_of_interest_for_polling'] = new_senders
        if 'vacation_start' in payload:
            merged['vacation_start'] = polling_config.POLLING_VACATION_START_DATE.isoformat() if polling_config.POLLING_VACATION_START_DATE else None
        if 'vacation_end' in payload:
            merged['vacation_end'] = polling_config.POLLING_VACATION_END_DATE.isoformat() if polling_config.POLLING_VACATION_END_DATE else None
        if new_enable_polling is not None:
            merged['enable_polling'] = new_enable_polling

        try:
            ok = _store.set_config_json("polling_config", merged, file_fallback=POLLING_CONFIG_FILE)
            if not ok:
                return jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration polling."}), 500
        except Exception:
            return jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration polling."}), 500

        return jsonify({
            "success": True,
            "config": {
                "active_days": merged.get('active_days', settings.POLLING_ACTIVE_DAYS),
                "active_start_hour": merged.get('active_start_hour', settings.POLLING_ACTIVE_START_HOUR),
                "active_end_hour": merged.get('active_end_hour', settings.POLLING_ACTIVE_END_HOUR),
                "enable_subject_group_dedup": merged.get('enable_subject_group_dedup', settings.ENABLE_SUBJECT_GROUP_DEDUP),
                "sender_of_interest_for_polling": merged.get('sender_of_interest_for_polling', settings.SENDER_LIST_FOR_POLLING),
                "vacation_start": merged.get('vacation_start'),
                "vacation_end": merged.get('vacation_end'),
                "enable_polling": merged.get('enable_polling', polling_config.get_enable_polling(True)),
            },
            "message": "Configuration polling mise à jour. Un redémarrage peut être nécessaire pour prise en compte complète."
        }), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne lors de la mise à jour du polling."}), 500
