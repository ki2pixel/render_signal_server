# Safe default for Redis client (can be initialized elsewhere and injected via globals())
redis_client = None

from background.lock import acquire_singleton_lock
from flask import Flask, jsonify, request
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
import os
import subprocess
import threading
import time
from pathlib import Path
import json
import logging
import re
from datetime import datetime, timedelta, timezone
import requests
import urllib3
from urllib.parse import urljoin
import fcntl  # File locking to ensure singleton background poller across processes
from collections import deque  # Rate limiting queue for webhook sends
# Ces imports remplacent les définitions locales des mêmes fonctions
from utils.time_helpers import parse_time_hhmm as _parse_time_hhmm
from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url

# --- Import des configurations extraites dans config/ ---
# Ces imports remplacent les définitions de constantes et variables de configuration
from config import settings
from config import polling_config
from config import webhook_time_window

# --- Import des modules d'authentification extraits dans auth/ ---
from auth import user as auth_user
from auth import helpers as auth_helpers
# Alias pour compatibilité avec le code existant
from auth.helpers import testapi_authorized as _testapi_authorized

from email_processing import imap_client as email_imap_client
from email_processing import pattern_matching as email_pattern_matching
# Import de la constante URL_PROVIDERS_PATTERN depuis pattern_matching
from email_processing import webhook_sender as email_webhook_sender
from email_processing import orchestrator as email_orchestrator
from email_processing import link_extraction as email_link_extraction
from email_processing import payloads as email_payloads
# Webhook logging helpers (avoid naming collision with stdlib 'logging')
from app_logging.webhook_logger import (
    append_webhook_log as _append_webhook_log_helper,
    fetch_webhook_logs as _fetch_webhook_logs_helper,
)
from utils.rate_limit import (
    prune_and_allow_send as _rate_prune_and_allow,
    record_send_event as _rate_record_event,
)
from preferences import processing_prefs as _processing_prefs
from deduplication import redis_client as _dedup
from deduplication.subject_group import generate_subject_group_id as _gen_subject_group_id
from routes import (
    health_bp,
    api_webhooks_bp,
    api_polling_bp,
    api_processing_bp,
    api_processing_legacy_bp,
    api_test_bp,
    dashboard_bp,
    api_logs_bp,
    api_admin_bp,
    api_utility_bp,
    api_config_bp,
    api_make_bp,
)
from routes.api_processing import DEFAULT_PROCESSING_PREFS as _DEFAULT_PROCESSING_PREFS
DEFAULT_PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS
from background.polling_thread import background_email_poller_loop

# --- Test API auth helper (API key) ---
# EXTRAIT VERS auth/helpers.py (Étape 3 du refactoring)
# La fonction _testapi_authorized est maintenant chargée depuis auth/helpers

def append_webhook_log(webhook_id: str, webhook_url: str, webhook_status_code: int, webhook_response: str):
    """Append a webhook log entry to the webhook log file."""
    return _append_webhook_log_helper(webhook_id, webhook_url, webhook_status_code, webhook_response)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    # Logging at module level might not use app's logger config yet.
    # Standard logging can be used if needed here, or rely on app.logger later.


# Note: L'extraction des liens fournisseurs est centralisée dans
# `email_processing/link_extraction.py` et le pattern regex dans
# `email_processing/pattern_matching.py`.


app = Flask(__name__, template_folder='.', static_folder='static')
# NOUVEAU: Une clé secrète est OBLIGATOIRE pour les sessions.
# Pour la production, utilisez une valeur complexe stockée dans les variables d'environnement.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "une-cle-secrete-tres-complexe-pour-le-developpement-a-changer")

# --- Blueprints registration ---
app.register_blueprint(health_bp)
app.register_blueprint(api_webhooks_bp)
app.register_blueprint(api_polling_bp)
app.register_blueprint(api_processing_bp)
app.register_blueprint(api_processing_legacy_bp)  # legacy URLs: /api/get_processing_prefs, /api/update_processing_prefs
app.register_blueprint(api_test_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_logs_bp)  # legacy URL: /api/webhook_logs
app.register_blueprint(api_admin_bp)
app.register_blueprint(api_utility_bp)
app.register_blueprint(api_config_bp)
app.register_blueprint(api_make_bp)

# --- CORS (for test tools calling from another origin) ---
# Allowlist origins, comma-separated in env CORS_ALLOWED_ORIGINS (e.g., "https://webhook.kidpixel.fr,https://example.com")
_cors_origins = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    CORS(
        app,
        resources={
            r"/api/test/*": {
                "origins": _cors_origins,
                "supports_credentials": False,
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "X-API-Key"],
                "max_age": 600,
            }
        },
    )

    # Preflight requests are handled by Flask-CORS configuration on the api_test blueprint

# --- Authentification: Initialisation Flask-Login ---
# Le décorateur @login_required est utilisé sur plusieurs routes (ex: '/').
# Il est donc essentiel d'initialiser LoginManager et de fournir un user_loader.
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'dashboard.login'
auth_user.init_login_manager(app, login_view='dashboard.login')

# --- Configuration centralisée (alias locaux vers config.settings) ---
WEBHOOK_URL = settings.WEBHOOK_URL
RECADRAGE_MAKE_WEBHOOK_URL = settings.RECADRAGE_MAKE_WEBHOOK_URL
AUTOREPONDEUR_MAKE_WEBHOOK_URL = settings.AUTOREPONDEUR_MAKE_WEBHOOK_URL
MAKECOM_API_KEY = settings.MAKECOM_API_KEY
WEBHOOK_SSL_VERIFY = settings.WEBHOOK_SSL_VERIFY

# IMAP / Email config
EMAIL_ADDRESS = settings.EMAIL_ADDRESS
EMAIL_PASSWORD = settings.EMAIL_PASSWORD
IMAP_SERVER = settings.IMAP_SERVER
IMAP_PORT = settings.IMAP_PORT
IMAP_USE_SSL = settings.IMAP_USE_SSL

SENDER_LIST_FOR_POLLING = settings.SENDER_LIST_FOR_POLLING
POLLING_TIMEZONE_STR = settings.POLLING_TIMEZONE_STR
POLLING_ACTIVE_START_HOUR = settings.POLLING_ACTIVE_START_HOUR
POLLING_ACTIVE_END_HOUR = settings.POLLING_ACTIVE_END_HOUR
POLLING_ACTIVE_DAYS = settings.POLLING_ACTIVE_DAYS
EMAIL_POLLING_INTERVAL_SECONDS = settings.EMAIL_POLLING_INTERVAL_SECONDS
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = settings.POLLING_INACTIVE_CHECK_INTERVAL_SECONDS

EXPECTED_API_TOKEN = settings.EXPECTED_API_TOKEN

PRESENCE_FLAG = settings.PRESENCE_FLAG
PRESENCE_TRUE_MAKE_WEBHOOK_URL = settings.PRESENCE_TRUE_MAKE_WEBHOOK_URL
PRESENCE_FALSE_MAKE_WEBHOOK_URL = settings.PRESENCE_FALSE_MAKE_WEBHOOK_URL

ENABLE_SUBJECT_GROUP_DEDUP = settings.ENABLE_SUBJECT_GROUP_DEDUP

# Runtime flags and files
DISABLE_EMAIL_ID_DEDUP = settings.DISABLE_EMAIL_ID_DEDUP
ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS
POLLING_CONFIG_FILE = settings.POLLING_CONFIG_FILE
TRIGGER_SIGNAL_FILE = settings.TRIGGER_SIGNAL_FILE
RUNTIME_FLAGS_FILE = settings.RUNTIME_FLAGS_FILE

# --- Configuration du Logging ---
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
if not REDIS_AVAILABLE:
    logging.warning(
        "CFG REDIS (module level): 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")

# --- Configuration (log centralisé) ---
settings.log_configuration(app.logger)
if not WEBHOOK_SSL_VERIFY:
    # Suppress SSL warnings only if verification is explicitly disabled
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app.logger.warning("CFG WEBHOOK: SSL verification DISABLED for webhook calls (development/legacy). Use valid certificates in production.")
    
# --- Timezone pour le polling (centralisé) ---
TZ_FOR_POLLING = polling_config.initialize_polling_timezone(app.logger)

if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else:
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...')")

# --- Configuration des Webhooks de Présence ---
# Présence: déjà fournie par settings (alias ci-dessus)

# --- Email server config validation flag ---
email_config_valid = bool(EMAIL_ADDRESS and EMAIL_PASSWORD and IMAP_SERVER)

# --- Webhook time window initialization (env -> then optional UI override from disk) ---
try:
    webhook_time_window.initialize_webhook_time_window(
        start_str=os.environ.get("WEBHOOKS_TIME_START", ""),
        end_str=os.environ.get("WEBHOOKS_TIME_END", ""),
    )
    # Try to load persisted overrides if any (UI can override env)
    webhook_time_window.reload_time_window_from_disk()
except Exception:
    pass

# --- Polling config overrides (optional UI overrides from disk) ---
try:
    _poll_cfg_path = settings.POLLING_CONFIG_FILE
    # TEMP DIAG: log path and existence for polling_config.json
    try:
        app.logger.info(
            f"CFG POLL(file): path={_poll_cfg_path}; exists={_poll_cfg_path.exists()}"
        )
    except Exception:
        pass
    if _poll_cfg_path.exists():
        with open(_poll_cfg_path, "r", encoding="utf-8") as _f:
            _pc = json.load(_f) or {}
        # TEMP DIAG: show relevant keys loaded
        try:
            app.logger.info(
                "CFG POLL(loaded): keys=%s; snippet={active_days=%s,start=%s,end=%s,enable_polling=%s}",
                list(_pc.keys()),
                _pc.get("active_days"),
                _pc.get("active_start_hour"),
                _pc.get("active_end_hour"),
                _pc.get("enable_polling"),
            )
        except Exception:
            pass
        # Apply if present
        if isinstance(_pc.get("active_days"), list) and _pc.get("active_days"):
            settings.POLLING_ACTIVE_DAYS = [int(d) for d in _pc["active_days"] if isinstance(d, (int, str))]
        if "active_start_hour" in _pc:
            try:
                v = int(_pc["active_start_hour"]) ;
                if 0 <= v <= 23:
                    settings.POLLING_ACTIVE_START_HOUR = v
            except Exception:
                pass
        if "active_end_hour" in _pc:
            try:
                v = int(_pc["active_end_hour"]) ;
                if 0 <= v <= 23:
                    settings.POLLING_ACTIVE_END_HOUR = v
            except Exception:
                pass
        if "enable_subject_group_dedup" in _pc:
            try:
                settings.ENABLE_SUBJECT_GROUP_DEDUP = bool(_pc["enable_subject_group_dedup"])
            except Exception:
                pass
        if isinstance(_pc.get("sender_of_interest_for_polling"), list):
            try:
                settings.SENDER_LIST_FOR_POLLING = [str(e).strip().lower() for e in _pc["sender_of_interest_for_polling"] if str(e).strip()]
            except Exception:
                pass
        # Vacation dates
        if "vacation_start" in _pc:
            try:
                vs = _pc.get("vacation_start")
                polling_config.POLLING_VACATION_START_DATE = None if not vs else datetime.fromisoformat(str(vs)).date()
            except Exception:
                polling_config.POLLING_VACATION_START_DATE = None
        if "vacation_end" in _pc:
            try:
                ve = _pc.get("vacation_end")
                polling_config.POLLING_VACATION_END_DATE = None if not ve else datetime.fromisoformat(str(ve)).date()
            except Exception:
                polling_config.POLLING_VACATION_END_DATE = None
        # Log effective schedule after overrides
        try:
            app.logger.info(
                f"CFG POLL(override): days={settings.POLLING_ACTIVE_DAYS}; start={settings.POLLING_ACTIVE_START_HOUR}; end={settings.POLLING_ACTIVE_END_HOUR}; dedup_monthly_scope={settings.ENABLE_SUBJECT_GROUP_DEDUP}"
            )
        except Exception:
            pass
        # IMPORTANT: refresh module-level aliases so the polling thread uses updated values
        try:
            POLLING_ACTIVE_DAYS = settings.POLLING_ACTIVE_DAYS
            POLLING_ACTIVE_START_HOUR = settings.POLLING_ACTIVE_START_HOUR
            POLLING_ACTIVE_END_HOUR = settings.POLLING_ACTIVE_END_HOUR
            SENDER_LIST_FOR_POLLING = settings.SENDER_LIST_FOR_POLLING
            ENABLE_SUBJECT_GROUP_DEDUP = settings.ENABLE_SUBJECT_GROUP_DEDUP
            app.logger.info(
                f"CFG POLL(effective): days={POLLING_ACTIVE_DAYS}; start={POLLING_ACTIVE_START_HOUR}; end={POLLING_ACTIVE_END_HOUR}; senders={len(SENDER_LIST_FOR_POLLING)}; dedup_monthly_scope={ENABLE_SUBJECT_GROUP_DEDUP}"
            )
        except Exception:
            pass
except Exception:
    # Non-blocking if file missing or invalid
    pass

# --- Dedup constants mapping (from central settings) ---
PROCESSED_EMAIL_IDS_REDIS_KEY = settings.PROCESSED_EMAIL_IDS_REDIS_KEY
PROCESSED_SUBJECT_GROUPS_REDIS_KEY = settings.PROCESSED_SUBJECT_GROUPS_REDIS_KEY
SUBJECT_GROUP_REDIS_PREFIX = settings.SUBJECT_GROUP_REDIS_PREFIX
SUBJECT_GROUP_TTL_SECONDS = settings.SUBJECT_GROUP_TTL_SECONDS
# In-memory fallback store for subject groups (process-local only)
SUBJECT_GROUPS_MEMORY = set()

# --- Fonctions Utilitaires IMAP ---
def create_imap_connection():
    """Wrapper vers email_processing.imap_client.create_imap_connection."""
    return email_imap_client.create_imap_connection(app.logger)


def close_imap_connection(mail):
    """Wrapper vers email_processing.imap_client.close_imap_connection."""
    return email_imap_client.close_imap_connection(app.logger, mail)


def generate_email_id(msg_data):
    """Wrapper vers email_processing.imap_client.generate_email_id."""
    return email_imap_client.generate_email_id(msg_data)


def extract_sender_email(from_header):
    """Wrapper vers email_processing.imap_client.extract_sender_email."""
    return email_imap_client.extract_sender_email(from_header)


def decode_email_header(header_value):
    """Wrapper vers email_processing.imap_client.decode_email_header_value."""
    return email_imap_client.decode_email_header_value(header_value)


def mark_email_as_read_imap(mail, email_num):
    """Wrapper vers email_processing.imap_client.mark_email_as_read_imap."""
    return email_imap_client.mark_email_as_read_imap(app.logger, mail, email_num)


def check_media_solution_pattern(subject, email_content):
    """Compatibility wrapper delegating to email_processing.pattern_matching.

    The canonical implementation lives in `email_processing/pattern_matching.py`.
    Tests and legacy code call this function from app_render; we forward the call
    and inject `TZ_FOR_POLLING` and `app.logger` as required by the new signature.
    """
    try:
        return email_pattern_matching.check_media_solution_pattern(
            subject=subject,
            email_content=email_content,
            tz_for_polling=TZ_FOR_POLLING,
            logger=app.logger,
        )
    except Exception as e:
        try:
            app.logger.error(f"MEDIA_PATTERN_WRAPPER: Exception: {e}")
        except Exception:
            pass
        return {"matches": False, "delivery_time": None}


def send_makecom_webhook(subject, delivery_time, sender_email, email_id, override_webhook_url: str | None = None, extra_payload: dict | None = None):
    """Délègue l'envoi du webhook Make.com au module email_processing.webhook_sender.

    Signature conservée pour compatibilité. Injecte `app.logger` et `_append_webhook_log`
    comme hook de journalisation dashboard.
    """
    return email_webhook_sender.send_makecom_webhook(
        subject=subject,
        delivery_time=delivery_time,
        sender_email=sender_email,
        email_id=email_id,
        override_webhook_url=override_webhook_url,
        extra_payload=extra_payload,
        logger=app.logger,
        log_hook=_append_webhook_log,
    )


# --- Fonctions de Déduplication avec Redis ---
def is_email_id_processed_redis(email_id):
    """Back-compat wrapper: delegate to dedup module; returns False on errors or no Redis."""
    rc = globals().get("redis_client")
    return _dedup.is_email_id_processed(
        rc,
        email_id=email_id,
        logger=app.logger,
        processed_ids_key=PROCESSED_EMAIL_IDS_REDIS_KEY,
    )


def mark_email_id_as_processed_redis(email_id):
    """Back-compat wrapper: delegate to dedup module; returns False without Redis."""
    rc = globals().get("redis_client")
    return _dedup.mark_email_id_processed(
        rc,
        email_id=email_id,
        logger=app.logger,
        processed_ids_key=PROCESSED_EMAIL_IDS_REDIS_KEY,
    )


# Helpers de texte dupliqués supprimés (utiliser ceux de utils.text_helpers via alias importés)


def generate_subject_group_id(subject: str) -> str:
    """Wrapper vers deduplication.subject_group.generate_subject_group_id."""
    return _gen_subject_group_id(subject)


def is_subject_group_processed(group_id: str) -> bool:
    """Check subject-group dedup via Redis or memory using the centralized helper."""
    rc = globals().get("redis_client")
    return _dedup.is_subject_group_processed(
        rc,
        group_id=group_id,
        logger=app.logger,
        ttl_seconds=SUBJECT_GROUP_TTL_SECONDS,
        ttl_prefix=SUBJECT_GROUP_REDIS_PREFIX,
        groups_key=PROCESSED_SUBJECT_GROUPS_REDIS_KEY,
        enable_monthly_scope=ENABLE_SUBJECT_GROUP_DEDUP,
        tz=TZ_FOR_POLLING,
        memory_set=SUBJECT_GROUPS_MEMORY,
    )


def mark_subject_group_processed(group_id: str) -> bool:
    """Mark subject-group as processed using centralized helper (Redis or memory)."""
    rc = globals().get("redis_client")
    return _dedup.mark_subject_group_processed(
        rc,
        group_id=group_id,
        logger=app.logger,
        ttl_seconds=SUBJECT_GROUP_TTL_SECONDS,
        ttl_prefix=SUBJECT_GROUP_REDIS_PREFIX,
        groups_key=PROCESSED_SUBJECT_GROUPS_REDIS_KEY,
        enable_monthly_scope=ENABLE_SUBJECT_GROUP_DEDUP,
        tz=TZ_FOR_POLLING,
        memory_set=SUBJECT_GROUPS_MEMORY,
    )


# --- Fonctions de Polling des Emails IMAP ---


def check_new_emails_and_trigger_webhook():
    """Thin delegate to orchestrator entry-point (Step 4E-final)."""
    return email_orchestrator.check_new_emails_and_trigger_webhook()

def background_email_poller():
    """Delegate polling loop to background.polling_thread with injected deps."""
    def _is_ready_to_poll() -> bool:
        return all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL])

    def _run_cycle() -> int:
        return email_orchestrator.check_new_emails_and_trigger_webhook()

    def _is_in_vacation(now_dt: datetime) -> bool:
        try:
            # Use polling_config helper if available; fallback to no vacation
            return polling_config.is_in_vacation_period(now_dt.date())
        except Exception:
            return False

    background_email_poller_loop(
        logger=app.logger,
        tz_for_polling=TZ_FOR_POLLING,
        get_active_days=lambda: POLLING_ACTIVE_DAYS,
        get_active_start_hour=lambda: POLLING_ACTIVE_START_HOUR,
        get_active_end_hour=lambda: POLLING_ACTIVE_END_HOUR,
        inactive_sleep_seconds=POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
        active_sleep_seconds=EMAIL_POLLING_INTERVAL_SECONDS,
        is_in_vacation=_is_in_vacation,
        is_ready_to_poll=_is_ready_to_poll,
        run_poll_cycle=_run_cycle,
        max_consecutive_errors=5,
    )


# --- Make Scenarios Vacation Watcher ---
def make_scenarios_vacation_watcher():
    """Background watcher that enforces Make scenarios ON/OFF according to
    - UI global toggle enable_polling (persisted via /api/update_polling_config)
    - Vacation window in polling_config (POLLING_VACATION_START/END)

    Logic:
    - If enable_polling is False => ensure scenarios are OFF
    - If enable_polling is True and in vacation => ensure scenarios are OFF
    - If enable_polling is True and not in vacation => ensure scenarios are ON

    To minimize API calls, apply only on state changes.
    """
    last_applied = None  # None|True|False meaning desired state last set
    interval = max(60, int(POLLING_INACTIVE_CHECK_INTERVAL_SECONDS))
    while True:
        try:
            enable_ui = polling_config.get_enable_polling(True)
            in_vac = False
            try:
                in_vac = polling_config.is_in_vacation_period()
            except Exception:
                in_vac = False
            desired = bool(enable_ui and not in_vac)
            if last_applied is None or desired != last_applied:
                try:
                    from routes.api_make import toggle_all_scenarios  # local import to avoid cycles
                    res = toggle_all_scenarios(desired, logger=app.logger)
                    app.logger.info(
                        "MAKE_WATCHER: applied desired=%s (enable_ui=%s, in_vacation=%s) results_keys=%s",
                        desired, enable_ui, in_vac, list(res.keys()) if isinstance(res, dict) else 'n/a'
                    )
                except Exception as e:
                    app.logger.error(f"MAKE_WATCHER: toggle_all_scenarios failed: {e}")
                last_applied = desired
        except Exception as e:
            try:
                app.logger.error(f"MAKE_WATCHER: loop error: {e}")
            except Exception:
                pass
        time.sleep(interval)


# --- Start Background Tasks (Email Poller) ---
try:
    # Log effective config before starting background tasks
    try:
        app.logger.info(
            f"CFG BG: enable_polling(UI)={polling_config.get_enable_polling(True)}; ENABLE_BACKGROUND_TASKS(env)={getattr(settings, 'ENABLE_BACKGROUND_TASKS', False)}"
        )
    except Exception:
        pass
    # Start background poller only if both the environment flag and the persisted
    # UI-controlled switch are enabled. This avoids unexpected background work
    # when the operator intentionally disabled polling from the dashboard.
    if getattr(settings, "ENABLE_BACKGROUND_TASKS", False) and polling_config.get_enable_polling(True):
        lock_path = getattr(settings, "BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock")
        try:
            if acquire_singleton_lock(lock_path):
                app.logger.info(
                    f"BG_POLLER: Singleton lock acquired on {lock_path}. Starting background thread."
                )
                _bg_email_poller_thread = threading.Thread(
                    target=background_email_poller, daemon=True
                )
                _bg_email_poller_thread.start()
            else:
                app.logger.info(
                    f"BG_POLLER: Singleton lock NOT acquired on {lock_path}. Background thread will not start."
                )
        except Exception as e:
            app.logger.error(
                f"BG_POLLER: Failed to start background thread: {e}", exc_info=True
            )
    else:
        # Clarify which condition prevented starting the poller
        if not getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
            app.logger.info(
                "BG_POLLER: ENABLE_BACKGROUND_TASKS is false. Background poller not started."
            )
        elif not polling_config.get_enable_polling(True):
            app.logger.info(
                "BG_POLLER: UI 'enable_polling' flag is false. Background poller not started."
            )
except Exception:
    # Defensive: never block app startup because of background thread wiring
    pass

# --- Start Make Scenarios Vacation Watcher ---
try:
    if getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
        _make_watcher_thread = threading.Thread(target=make_scenarios_vacation_watcher, daemon=True)
        _make_watcher_thread.start()
        try:
            app.logger.info("MAKE_WATCHER: background thread started (vacation-aware ON/OFF)")
        except Exception:
            pass
    else:
        try:
            app.logger.info("MAKE_WATCHER: not started because ENABLE_BACKGROUND_TASKS is false")
        except Exception:
            pass
except Exception as e:
    try:
        app.logger.error(f"MAKE_WATCHER: failed to start thread: {e}")
    except Exception:
        pass

# Routes /login, /logout et '/' déplacées vers routes/dashboard.py


# Toggle polling handled in routes/api_polling.py
WEBHOOK_LOGS_FILE = Path(__file__).resolve().parent / "debug" / "webhook_logs.json"
WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"  # Redis list, each item is JSON string

# --- Processing Preferences (Filters, Reliability, Rate limiting) --- (restored)
PROCESSING_PREFS_FILE = Path(__file__).resolve().parent / "debug" / "processing_prefs.json"
PROCESSING_PREFS_REDIS_KEY = "r:ss:processing_prefs:v1"

# Defaults (can be overridden via API)

# Initialize processing prefs at import time
try:
    PROCESSING_PREFS  # noqa: F401
except NameError:
    PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS.copy()


def _load_processing_prefs() -> dict:
    """Charge les préférences via module preferences (Redis si dispo, sinon fichier)."""
    rc = globals().get("redis_client")
    return _processing_prefs.load_processing_prefs(
        redis_client=rc,
        file_path=PROCESSING_PREFS_FILE,
        defaults=_DEFAULT_PROCESSING_PREFS,
        logger=app.logger,
        redis_key=PROCESSING_PREFS_REDIS_KEY,
    )


def _save_processing_prefs(prefs: dict) -> bool:
    """Sauvegarde via module preferences (Redis prioritaire, sinon fichier)."""
    rc = globals().get("redis_client")
    return _processing_prefs.save_processing_prefs(
        prefs,
        redis_client=rc,
        file_path=PROCESSING_PREFS_FILE,
        logger=app.logger,
        redis_key=PROCESSING_PREFS_REDIS_KEY,
    )

# Initialize with persisted values
PROCESSING_PREFS = _load_processing_prefs()

# Rate limiting state (timestamps in epoch seconds of successful/attempted sends)
WEBHOOK_SEND_EVENTS = deque()

def _rate_limit_allow_send() -> bool:
    try:
        limit = int(PROCESSING_PREFS.get("rate_limit_per_hour") or 0)
    except Exception:
        limit = 0
    return _rate_prune_and_allow(WEBHOOK_SEND_EVENTS, limit)


def _record_send_event():
    _rate_record_event(WEBHOOK_SEND_EVENTS)


def _validate_processing_prefs(payload: dict) -> tuple[bool, str, dict]:
    """Valide via module preferences en partant des valeurs courantes comme base."""
    base = dict(PROCESSING_PREFS)
    ok, msg, out = _processing_prefs.validate_processing_prefs(payload, base)
    return ok, msg, out


def _append_webhook_log(log_entry: dict):
    """Ajoute une entrée de log webhook (Redis si dispo, sinon fichier JSON).
    Délègue à app_logging.webhook_logger pour centraliser la logique. Conserve au plus 500 entrées."""
    try:
        rc = globals().get("redis_client")
    except Exception:
        rc = None
    _append_webhook_log_helper(
        log_entry,
        redis_client=rc,
        logger=app.logger,
        file_path=WEBHOOK_LOGS_FILE,
        redis_list_key=WEBHOOK_LOGS_REDIS_KEY,
        max_entries=500,
    )

