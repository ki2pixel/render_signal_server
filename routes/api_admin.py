from __future__ import annotations

import io
import os
import subprocess
import threading
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from typing import Iterable, List, Tuple

import requests
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from services import ConfigService
from email_processing import orchestrator as email_orchestrator
from app_logging.webhook_logger import append_webhook_log as _append_webhook_log
from migrate_configs_to_redis import main as migrate_configs_main
from scripts.check_config_store import KEY_CHOICES as CONFIG_STORE_KEYS
from scripts.check_config_store import inspect_configs

bp = Blueprint("api_admin", __name__, url_prefix="/api")

_config_service = ConfigService()
ALLOWED_CONFIG_KEYS = CONFIG_STORE_KEYS


def _invoke_config_migration(selected_keys: Iterable[str]) -> Tuple[int, str]:
    argv: List[str] = ["--require-redis", "--verify"]
    for key in selected_keys:
        argv.extend(["--only", key])

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        exit_code = migrate_configs_main(argv)

    combined_output = "\n".join(
        segment
        for segment in (stdout_buffer.getvalue().strip(), stderr_buffer.getvalue().strip())
        if segment
    )
    return exit_code, combined_output


def _run_config_store_verification(selected_keys: Iterable[str], raw: bool = False) -> Tuple[int, list[dict]]:
    keys = tuple(selected_keys) or ALLOWED_CONFIG_KEYS
    exit_code, results = inspect_configs(keys, raw=raw)
    return exit_code, results


@bp.route("/restart_server", methods=["POST"])
@login_required
def restart_server():
    try:
        restart_cmd = os.environ.get("RESTART_CMD", "sudo systemctl restart render-signal-server")
        # Journaliser explicitement la demande de redémarrage pour traçabilité
        try:
            current_app.logger.info(
                "ADMIN: Server restart requested by '%s' with command: %s",
                getattr(current_user, "id", "unknown"),
                restart_cmd,
            )
        except Exception:
            pass

        # Exécuter la commande en arrière-plan pour ne pas bloquer la requête HTTP
        subprocess.Popen(
            ["/bin/bash", "-lc", f"sleep 1; {restart_cmd}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        try:
            current_app.logger.info("ADMIN: Restart command scheduled (background).")
        except Exception:
            pass
        return jsonify({"success": True, "message": "Redémarrage planifié. L'application sera indisponible quelques secondes."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route("/migrate_configs_to_redis", methods=["POST"])
@login_required
def migrate_configs_to_redis_endpoint():
    """Migrer les configurations critiques vers Redis directement depuis le dashboard."""
    try:
        payload = request.get_json(silent=True) or {}
        requested_keys = payload.get("keys")

        if requested_keys is None:
            selected_keys = ALLOWED_CONFIG_KEYS
        elif isinstance(requested_keys, list) and all(isinstance(k, str) for k in requested_keys):
            invalid = [k for k in requested_keys if k not in ALLOWED_CONFIG_KEYS]
            if invalid:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Clés invalides: {', '.join(invalid)}",
                            "allowed_keys": ALLOWED_CONFIG_KEYS,
                        }
                    ),
                    400,
                )
            # Conserver l'ordre fourni par l'utilisateur (mais éviter doublons)
            seen = set()
            selected_keys = tuple(k for k in requested_keys if not (k in seen or seen.add(k)))
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Le champ 'keys' doit être une liste de chaînes.",
                        "allowed_keys": ALLOWED_CONFIG_KEYS,
                    }
                ),
                400,
            )

        exit_code, output = _invoke_config_migration(selected_keys)
        success = exit_code == 0
        status_code = 200 if success else 502

        try:
            current_app.logger.info(
                "ADMIN: Config migration requested by '%s' (keys=%s, exit=%s)",
                getattr(current_user, "id", "unknown"),
                list(selected_keys),
                exit_code,
            )
        except Exception:
            pass

        return (
            jsonify(
                {
                    "success": success,
                    "exit_code": exit_code,
                    "keys": list(selected_keys),
                    "log": output,
                }
            ),
            status_code,
        )
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500


@bp.route("/verify_config_store", methods=["POST"])
@login_required
def verify_config_store():
    """Vérifie les configurations persistées (Redis + fallback) directement depuis le dashboard."""
    try:
        payload = request.get_json(silent=True) or {}
        requested_keys = payload.get("keys")
        raw = bool(payload.get("raw"))

        if requested_keys is None:
            selected_keys = ALLOWED_CONFIG_KEYS
        elif isinstance(requested_keys, list) and all(isinstance(k, str) for k in requested_keys):
            invalid = [k for k in requested_keys if k not in ALLOWED_CONFIG_KEYS]
            if invalid:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": f"Clés invalides: {', '.join(invalid)}",
                            "allowed_keys": ALLOWED_CONFIG_KEYS,
                        }
                    ),
                    400,
                )
            seen = set()
            selected_keys = tuple(k for k in requested_keys if not (k in seen or seen.add(k)))
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Le champ 'keys' doit être une liste de chaînes.",
                        "allowed_keys": ALLOWED_CONFIG_KEYS,
                    }
                ),
                400,
            )

        exit_code, results = _run_config_store_verification(selected_keys, raw=raw)
        success = exit_code == 0
        status_code = 200 if success else 502

        try:
            current_app.logger.info(
                "ADMIN: Config store verification requested by '%s' (keys=%s, exit=%s)",
                getattr(current_user, "id", "unknown"),
                list(selected_keys),
                exit_code,
            )
        except Exception:
            pass

        return (
            jsonify(
                {
                    "success": success,
                    "exit_code": exit_code,
                    "keys": list(selected_keys),
                    "results": results,
                }
            ),
            status_code,
        )
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500


@bp.route("/deploy_application", methods=["POST"])
@login_required
def deploy_application():
    """Déclenche un déploiement applicatif côté serveur.

    La commande est définie via la variable d'environnement DEPLOY_CMD.
    Par défaut, on effectue un reload-or-restart du service applicatif et un reload de Nginx.
    L'exécution est asynchrone (arrière-plan) pour ne pas bloquer la requête HTTP.
    """
    try:
        # 1) Si un Deploy Hook Render est configuré, l'utiliser en priorité (plus simple)
        render_config = _config_service.get_render_config()
        hook_url = render_config.get("deploy_hook_url")
        if hook_url:
            try:
                # Validation basique de l'URL (éviter appels arbitraires)
                if not hook_url.startswith("https://api.render.com/deploy/"):
                    return jsonify({"success": False, "message": "RENDER_DEPLOY_HOOK_URL invalide (préfixe inattendu)."}), 400

                # Masquer la clé dans les logs
                masked = hook_url
                try:
                    if "?key=" in masked:
                        masked = masked.split("?key=")[0] + "?key=***"
                except Exception:
                    masked = "<masked>"

                current_app.logger.info(
                    "ADMIN: Deploy via Render Deploy Hook requested by '%s' (url=%s)",
                    getattr(current_user, "id", "unknown"),
                    masked,
                )
            except Exception:
                pass

            try:
                resp = requests.get(hook_url, timeout=15)
                ok_status = resp.status_code in (200, 201, 202, 204)
                if ok_status:
                    current_app.logger.info(
                        "ADMIN: Deploy hook accepted (http=%s)", resp.status_code
                    )
                    return jsonify({
                        "success": True,
                        "message": "Déploiement Render déclenché via Deploy Hook. Consultez le dashboard Render.",
                    }), 200
                else:
                    # Continuer vers la méthode API si disponible, sinon fallback local
                    current_app.logger.warning(
                        "ADMIN: Deploy hook returned non-success http=%s; will try alternative method.",
                        resp.status_code,
                    )
            except Exception as e:
                current_app.logger.warning("ADMIN: Deploy hook call failed: %s", e)

        # 2) Sinon, si variables Render API sont définies, utiliser l'API Render
        # Phase 5: Utilisation de ConfigService
        if render_config["api_key"] and render_config["service_id"]:
            try:
                current_app.logger.info(
                    "ADMIN: Deploy via Render API requested by '%s' (service_id=%s, clearCache=%s)",
                    getattr(current_user, "id", "unknown"),
                    render_config["service_id"],
                    render_config["clear_cache"],
                )
            except Exception:
                pass

            url = f"https://api.render.com/v1/services/{render_config['service_id']}/deploys"
            headers = {
                "Authorization": f"Bearer {render_config['api_key']}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {"clearCache": render_config["clear_cache"]}
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            ok_status = resp.status_code in (200, 201, 202)
            data = {}
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:400]}

            if ok_status:
                deploy_id = data.get("id") or data.get("deployId")
                status = data.get("status") or "queued"
                try:
                    current_app.logger.info(
                        "ADMIN: Render deploy accepted (id=%s, status=%s, http=%s)",
                        deploy_id,
                        status,
                        resp.status_code,
                    )
                except Exception:
                    pass
                return jsonify({
                    "success": True,
                    "message": "Déploiement Render lancé (voir dashboard Render).",
                    "deploy_id": deploy_id,
                    "status": status,
                }), 200
            else:
                msg = data.get("message") or data.get("error") or f"HTTP {resp.status_code}"
                return jsonify({"success": False, "message": f"Render API error: {msg}"}), 502

        # 3) Fallback: commande système locale (DEPLOY_CMD)
        default_cmd = (
            "sudo systemctl reload-or-restart render-signal-server; "
            "sudo nginx -s reload || sudo systemctl reload nginx"
        )
        deploy_cmd = os.environ.get("DEPLOY_CMD", default_cmd)

        try:
            current_app.logger.info(
                "ADMIN: Deploy (fallback cmd) requested by '%s' with command: %s",
                getattr(current_user, "id", "unknown"),
                deploy_cmd,
            )
        except Exception:
            pass

        subprocess.Popen(
            ["/bin/bash", "-lc", f"sleep 1; {deploy_cmd}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        try:
            current_app.logger.info("ADMIN: Deploy command scheduled (background).")
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": "Déploiement planifié (fallback local). L'application peut être indisponible pendant quelques secondes."
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Obsolete presence test endpoint removed


@bp.route("/check_emails_and_download", methods=["POST"])
@login_required
def check_emails_and_download():
    try:
        current_app.logger.info(f"API_EMAIL_CHECK: Déclenchement manuel par '{current_user.id}'.")

        # Validate minimal email config and required runtime settings
        # Phase 5: Utilisation de ConfigService
        if not _config_service.is_email_config_valid():
            return jsonify({"status": "error", "message": "Config serveur email incomplète (email/IMAP)."}), 503
        if not _config_service.has_webhook_url():
            return jsonify({"status": "error", "message": "Config serveur email incomplète (webhook URL)."}), 503

        def run_task():
            try:
                with current_app.app_context():
                    email_orchestrator.check_new_emails_and_trigger_webhook()
            except Exception as e:
                try:
                    current_app.logger.error(f"API_EMAIL_CHECK: Exception background task: {e}")
                except Exception:
                    pass

        threading.Thread(target=run_task, daemon=True).start()
        return jsonify({"status": "success", "message": "Vérification en arrière-plan lancée."}), 202
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

