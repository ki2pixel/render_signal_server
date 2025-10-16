from __future__ import annotations

import os
import subprocess
import threading
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from config.settings import (
    PRESENCE_TRUE_MAKE_WEBHOOK_URL,
    PRESENCE_FALSE_MAKE_WEBHOOK_URL,
    EMAIL_ADDRESS,
    EMAIL_PASSWORD,
    IMAP_SERVER,
    SENDER_LIST_FOR_POLLING,
    WEBHOOK_URL,
    RENDER_API_KEY,
    RENDER_SERVICE_ID,
    RENDER_DEPLOY_CLEAR_CACHE,
    RENDER_DEPLOY_HOOK_URL,
)
from email_processing import webhook_sender as email_webhook_sender
from email_processing import orchestrator as email_orchestrator
from app_logging.webhook_logger import append_webhook_log as _append_webhook_log

bp = Blueprint("api_admin", __name__, url_prefix="/api")


@bp.route("/restart_server", methods=["POST"])  # POST /api/restart_server
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


@bp.route("/deploy_application", methods=["POST"])  # POST /api/deploy_application
@login_required
def deploy_application():
    """Déclenche un déploiement applicatif côté serveur.

    La commande est définie via la variable d'environnement DEPLOY_CMD.
    Par défaut, on effectue un reload-or-restart du service applicatif et un reload de Nginx.
    L'exécution est asynchrone (arrière-plan) pour ne pas bloquer la requête HTTP.
    """
    try:
        # 1) Si un Deploy Hook Render est configuré, l'utiliser en priorité (plus simple)
        if RENDER_DEPLOY_HOOK_URL:
            try:
                # Validation basique de l'URL (éviter appels arbitraires)
                if not RENDER_DEPLOY_HOOK_URL.startswith("https://api.render.com/deploy/"):
                    return jsonify({"success": False, "message": "RENDER_DEPLOY_HOOK_URL invalide (préfixe inattendu)."}), 400

                # Masquer la clé dans les logs
                masked = RENDER_DEPLOY_HOOK_URL
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
                resp = requests.get(RENDER_DEPLOY_HOOK_URL, timeout=15)
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
        if RENDER_API_KEY and RENDER_SERVICE_ID:
            try:
                current_app.logger.info(
                    "ADMIN: Deploy via Render API requested by '%s' (service_id=%s, clearCache=%s)",
                    getattr(current_user, "id", "unknown"),
                    RENDER_SERVICE_ID,
                    RENDER_DEPLOY_CLEAR_CACHE,
                )
            except Exception:
                pass

            url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
            headers = {
                "Authorization": f"Bearer {RENDER_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {"clearCache": RENDER_DEPLOY_CLEAR_CACHE}
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


@bp.route("/test_presence_webhook", methods=["POST"])  # POST /api/test_presence_webhook
@login_required
def test_presence_webhook():
    try:
        presence_raw = None
        if request.is_json:
            body = request.get_json(silent=True) or {}
            presence_raw = body.get("presence")
        if presence_raw is None:
            presence_raw = request.form.get("presence") or request.args.get("presence")

        if presence_raw is None:
            return jsonify({"success": False, "message": "Paramètre 'presence' requis (true|false)."}), 400

        presence_str = str(presence_raw).strip().lower()
        if presence_str not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            return jsonify({"success": False, "message": "Valeur 'presence' invalide. Utilisez true|false."}), 400

        presence_bool = presence_str in ("true", "1", "yes", "on")
        target_url = PRESENCE_TRUE_MAKE_WEBHOOK_URL if presence_bool else PRESENCE_FALSE_MAKE_WEBHOOK_URL
        if not target_url:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "URL de webhook de présence non configurée (PRESENCE_TRUE_MAKE_WEBHOOK_URL / PRESENCE_FALSE_MAKE_WEBHOOK_URL)",
                    }
                ),
                400,
            )

        test_subject = "[TEST] Présence Samedi - Déclenchement manuel"
        test_sender_email = "test@render-signal-server.local"
        test_email_id = f"manual-{int(datetime.now().timestamp())}"

        ok = email_webhook_sender.send_makecom_webhook(
            subject=test_subject,
            delivery_time=None,
            sender_email=test_sender_email,
            email_id=test_email_id,
            override_webhook_url=target_url,
            extra_payload={"presence": presence_bool, "detector": "manual_test"},
            logger=current_app.logger,
            log_hook=_append_webhook_log,
        )
        if ok:
            return jsonify({"success": True, "presence": presence_bool, "used_url": target_url}), 200
        else:
            return jsonify({"success": False, "message": "Échec d'envoi du webhook vers Make."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route("/check_emails_and_download", methods=["POST"])  # POST /api/check_emails_and_download
@login_required
def check_emails_and_download():
    try:
        current_app.logger.info(f"API_EMAIL_CHECK: Déclenchement manuel par '{current_user.id}'.")

        # Validate minimal email config and required runtime settings
        email_config_valid = bool(EMAIL_ADDRESS and EMAIL_PASSWORD and IMAP_SERVER)
        if not all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
            return jsonify({"status": "error", "message": "Config serveur email incomplète."}), 503

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
