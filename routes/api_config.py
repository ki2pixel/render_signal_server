from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Tuple

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config import webhook_time_window, polling_config, settings
from config import app_config_store as _store
from config.settings import (
    RUNTIME_FLAGS_FILE,
    DISABLE_EMAIL_ID_DEDUP as DEFAULT_DISABLE_EMAIL_ID_DEDUP,
    ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS as DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS,
    POLLING_TIMEZONE_STR,
    EMAIL_POLLING_INTERVAL_SECONDS,
    POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
    POLLING_CONFIG_FILE,
)
from services import RuntimeFlagsService

bp = Blueprint("api_config", __name__, url_prefix="/api")

# Récupérer l'instance RuntimeFlagsService (Singleton)
# L'instance est déjà initialisée dans app_render.py
try:
    _runtime_flags_service = RuntimeFlagsService.get_instance()
except ValueError:
    # Fallback: initialiser si pas encore fait (cas tests)
    _runtime_flags_service = RuntimeFlagsService.get_instance(
        file_path=RUNTIME_FLAGS_FILE,
        defaults={
            "disable_email_id_dedup": bool(DEFAULT_DISABLE_EMAIL_ID_DEDUP),
            "allow_custom_webhook_without_links": bool(DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
        }
    )


# Wrappers legacy supprimés - Appels directs aux services


# ---- Time window (session-protected) ----

@bp.route("/get_webhook_time_window", methods=["GET"])
@login_required
def get_webhook_time_window():
    try:
        # Best-effort: pull latest values from external store to reflect remote edits
        try:
            cfg = _store.get_config_json("webhook_config") or {}
            gs = (cfg.get("global_time_start") or "").strip()
            ge = (cfg.get("global_time_end") or "").strip()
            # Only sync when BOTH values are provided (non-empty). Do NOT clear on double-empty here.
            if (gs != "" and ge != ""):
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


@bp.route("/set_webhook_time_window", methods=["POST"])
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

@bp.route("/get_runtime_flags", methods=["GET"])
@login_required
def get_runtime_flags():
    """Récupère les flags runtime.
    
    Appel direct à RuntimeFlagsService (cache intelligent 60s).
    """
    try:
        # Appel direct au service (cache si valide, sinon reload)
        data = _runtime_flags_service.get_all_flags()
        return jsonify({"success": True, "flags": data}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500


@bp.route("/update_runtime_flags", methods=["POST"])
@login_required
def update_runtime_flags():
    """Met à jour les flags runtime.
    
    Appel direct à RuntimeFlagsService.update_flags() - Atomic update + invalidation cache.
    """
    try:
        payload = request.get_json(silent=True) or {}
        
        # Préparer les mises à jour (validation)
        updates = {}
        if "disable_email_id_dedup" in payload:
            updates["disable_email_id_dedup"] = bool(payload.get("disable_email_id_dedup"))
        if "allow_custom_webhook_without_links" in payload:
            updates["allow_custom_webhook_without_links"] = bool(payload.get("allow_custom_webhook_without_links"))
        
        # Appel direct au service (mise à jour atomique + persiste + invalide cache)
        if not _runtime_flags_service.update_flags(updates):
            return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
        
        # Récupérer les flags à jour
        data = _runtime_flags_service.get_all_flags()
        return jsonify({
            "success": True,
            "flags": data,
            "message": "Modifications enregistrées. Un redémarrage peut être nécessaire."
        }), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500


# ---- Polling configuration (session-protected) ----

@bp.route("/get_polling_config", methods=["GET"])
@login_required
def get_polling_config():
    try:
        # Read live settings at call time to honor pytest patch.object overrides
        from importlib import import_module as _import_module
        live_settings = _import_module('config.settings')
        # Prefer values from external store/file if available to reflect persisted UI choices
        persisted = _store.get_config_json("polling_config", file_fallback=POLLING_CONFIG_FILE) or {}
        default_active_days = getattr(live_settings, 'POLLING_ACTIVE_DAYS', settings.POLLING_ACTIVE_DAYS)
        default_start_hour = getattr(live_settings, 'POLLING_ACTIVE_START_HOUR', settings.POLLING_ACTIVE_START_HOUR)
        default_end_hour = getattr(live_settings, 'POLLING_ACTIVE_END_HOUR', settings.POLLING_ACTIVE_END_HOUR)
        default_enable_subject_dedup = getattr(
            live_settings,
            'ENABLE_SUBJECT_GROUP_DEDUP',
            settings.ENABLE_SUBJECT_GROUP_DEDUP,
        )
        cfg = {
            "active_days": persisted.get("active_days", default_active_days),
            "active_start_hour": persisted.get("active_start_hour", default_start_hour),
            "active_end_hour": persisted.get("active_end_hour", default_end_hour),
            "enable_subject_group_dedup": persisted.get(
                "enable_subject_group_dedup",
                default_enable_subject_dedup,
            ),
            "timezone": getattr(live_settings, 'POLLING_TIMEZONE_STR', POLLING_TIMEZONE_STR),
            # Still expose persisted sender list if present, else settings default
            "sender_of_interest_for_polling": persisted.get("sender_of_interest_for_polling", getattr(live_settings, 'SENDER_LIST_FOR_POLLING', settings.SENDER_LIST_FOR_POLLING)),
            "vacation_start": persisted.get("vacation_start", polling_config.POLLING_VACATION_START_DATE.isoformat() if polling_config.POLLING_VACATION_START_DATE else None),
            "vacation_end": persisted.get("vacation_end", polling_config.POLLING_VACATION_END_DATE.isoformat() if polling_config.POLLING_VACATION_END_DATE else None),
            # Global enable toggle: prefer persisted, fallback helper
            "enable_polling": persisted.get("enable_polling", True),
        }
        return jsonify({"success": True, "config": cfg}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration polling."}), 500


@bp.route("/update_polling_config", methods=["POST"])
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
                val = payload.get('enable_polling')
                if isinstance(val, bool):
                    new_enable_polling = val
                elif isinstance(val, (int, float)):
                    new_enable_polling = bool(val)
                elif isinstance(val, str):
                    s = val.strip().lower()
                    if s in {"1", "true", "yes", "y", "on"}:
                        new_enable_polling = True
                    elif s in {"0", "false", "no", "n", "off"}:
                        new_enable_polling = False
            except Exception:
                new_enable_polling = None

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
            merged['vacation_start'] = new_vac_start.isoformat() if new_vac_start else None
        if 'vacation_end' in payload:
            merged['vacation_end'] = new_vac_end.isoformat() if new_vac_end else None
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
