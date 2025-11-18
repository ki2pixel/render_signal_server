# Safe default for Redis client (can be initialized elsewhere and injected via globals())
redis_client = None

from background.lock import acquire_singleton_lock
from flask import Flask, jsonify, request
from flask_login import login_required
from flask_cors import CORS
import os
import threading
import time
from pathlib import Path
import json
import logging
from datetime import datetime, timedelta, timezone
import urllib3
import signal
from collections import deque  # Rate limiting queue for webhook sends
# Ces imports remplacent les définitions locales des mêmes fonctions
from utils.time_helpers import parse_time_hhmm as _parse_time_hhmm
from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url

# --- Import des configurations extraites dans config/ ---
# Ces imports remplacent les définitions de constantes et variables de configuration
from config import settings
from config import polling_config
from config.polling_config import PollingConfigService
from config import webhook_time_window
from config.app_config_store import get_config_json as _config_get

# --- Import des services (Phase 2 - Architecture orientée services) ---
from services import (
    ConfigService,
    RuntimeFlagsService,
    WebhookConfigService,
    AuthService,
    DeduplicationService,
)

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

# =============================================================================
# SERVICES INITIALIZATION (Phase 2 - Architecture Orientée Services)
# =============================================================================
# Les services encapsulent la logique métier et fournissent des interfaces
# cohérentes pour accéder aux fonctionnalités de l'application.
#
# L'ordre d'initialisation est important car certains services dépendent d'autres:
# 1. ConfigService (aucune dépendance)
# 2. RuntimeFlagsService, WebhookConfigService (dépendent indirectement de config)
# 3. AuthService (dépend de ConfigService)
# 4. PollingConfigService (déjà créé plus bas)
# 5. DeduplicationService (dépend de ConfigService et PollingConfigService)

# 1. Configuration Service
_config_service = ConfigService()

# 2. Runtime Flags Service (Singleton - sera initialisé plus bas après settings)
# _runtime_flags_service = RuntimeFlagsService.get_instance(...)

# 3. Webhook Config Service (Singleton - sera initialisé plus bas)
# _webhook_service = WebhookConfigService.get_instance(...)

# 4. Auth Service  
_auth_service = AuthService(_config_service)

# Note: _polling_service et _dedup_service seront initialisés plus bas
# après la configuration complète du logging et Redis

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

# --- Authentification: Initialisation Flask-Login (via AuthService) ---
# Le décorateur @login_required est utilisé sur plusieurs routes (ex: '/').
# AuthService encapsule Flask-Login et fournit une interface unifiée pour
# l'authentification dashboard et API.
login_manager = _auth_service.init_flask_login(app, login_view='dashboard.login')

# Backward compatibility: Keep auth_user initialization for any legacy code
# TODO: Deprecate in favor of AuthService.init_flask_login once all consumers updated
auth_user.init_login_manager(app, login_view='dashboard.login')

# --- Configuration centralisée (alias locaux vers config.settings) ---
WEBHOOK_URL = settings.WEBHOOK_URL
MAKECOM_API_KEY = settings.MAKECOM_API_KEY
WEBHOOK_SSL_VERIFY = settings.WEBHOOK_SSL_VERIFY

# IMAP / Email config
EMAIL_ADDRESS = settings.EMAIL_ADDRESS
EMAIL_PASSWORD = settings.EMAIL_PASSWORD
IMAP_SERVER = settings.IMAP_SERVER
IMAP_PORT = settings.IMAP_PORT
IMAP_USE_SSL = settings.IMAP_USE_SSL

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


# --- Diagnostics (process start + heartbeat) ---
try:
    from datetime import datetime, timezone as _tz
    PROCESS_START_TIME = datetime.now(_tz.utc)
except Exception:
    PROCESS_START_TIME = None

def _heartbeat_loop():
    interval = 60
    while True:
        try:
            bg = globals().get("_bg_email_poller_thread")
            mk = globals().get("_make_watcher_thread")
            bg_alive = bool(bg and bg.is_alive())
            mk_alive = bool(mk and mk.is_alive())
            app.logger.info("HEARTBEAT: alive (bg_poller=%s, make_watcher=%s)", bg_alive, mk_alive)
        except Exception:
            pass
        time.sleep(interval)

try:
    # Heartbeat thread respects DISABLE_BACKGROUND_TASKS
    disable_bg_hb = os.environ.get("DISABLE_BACKGROUND_TASKS", "").strip().lower() in ["1", "true", "yes"]
    if getattr(settings, "ENABLE_BACKGROUND_TASKS", False) and not disable_bg_hb:
        _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        _heartbeat_thread.start()
except Exception:
    pass

# --- Process Signal Handlers (observability) ---
def _handle_sigterm(signum, frame):  # pragma: no cover - environment dependent
    try:
        app.logger.info("PROCESS: SIGTERM received; shutting down gracefully (platform restart/deploy).")
    except Exception:
        # app may not be fully initialized; avoid raising during shutdown
        pass

try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except Exception:
    # Some environments may not allow setting signal handlers (e.g., Windows)
    pass


# --- Configuration (log centralisé) ---
settings.log_configuration(app.logger)
if not WEBHOOK_SSL_VERIFY:
    # Suppress SSL warnings only if verification is explicitly disabled
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app.logger.warning("CFG WEBHOOK: SSL verification DISABLED for webhook calls (development/legacy). Use valid certificates in production.")
    
# --- Timezone pour le polling (centralisé) ---
TZ_FOR_POLLING = polling_config.initialize_polling_timezone(app.logger)

# --- Polling Config Service (accès centralisé à la configuration) ---
_polling_service = PollingConfigService(settings)

# =============================================================================
# SERVICES INITIALIZATION - Suite (après logging configuré)
# =============================================================================

# 5. Runtime Flags Service (Singleton)
try:
    _runtime_flags_service = RuntimeFlagsService.get_instance(
        file_path=settings.RUNTIME_FLAGS_FILE,
        defaults={
            "disable_email_id_dedup": bool(settings.DISABLE_EMAIL_ID_DEDUP),
            "allow_custom_webhook_without_links": bool(settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
        }
    )
    app.logger.info(f"SVC: RuntimeFlagsService initialized (cache_ttl={_runtime_flags_service.get_cache_ttl()}s)")
except Exception as e:
    app.logger.error(f"SVC: Failed to initialize RuntimeFlagsService: {e}")
    _runtime_flags_service = None

# 6. Webhook Config Service (Singleton)
try:
    # WebhookConfigService peut utiliser l'external store pour synchronisation
    from config import app_config_store
    _webhook_service = WebhookConfigService.get_instance(
        file_path=Path(__file__).parent / "debug" / "webhook_config.json",
        external_store=app_config_store
    )
    app.logger.info(f"SVC: WebhookConfigService initialized (has_url={_webhook_service.has_webhook_url()})")
except Exception as e:
    app.logger.error(f"SVC: Failed to initialize WebhookConfigService: {e}")
    _webhook_service = None

# Note: DeduplicationService sera initialisé plus bas après Redis

if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else:
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...')")

# --- Configuration des Webhooks de Présence ---
# Présence: déjà fournie par settings (alias ci-dessus)

# --- Email server config validation flag (maintenant via ConfigService) ---
email_config_valid = _config_service.is_email_config_valid()

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

# --- Polling config overrides (optional UI overrides from external store with file fallback) ---
try:
    _poll_cfg_path = settings.POLLING_CONFIG_FILE
    # TEMP DIAG: log path and existence for polling_config.json
    try:
        app.logger.info(
            f"CFG POLL(file): path={_poll_cfg_path}; exists={_poll_cfg_path.exists()}"
        )
    except Exception:
        pass
    _pc = {}
    try:
        # Fetch from external store with file fallback
        _pc = _config_get("polling_config", file_fallback=_poll_cfg_path) or {}
    except Exception:
        _pc = {}
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
        app.logger.info(
            f"CFG POLL(effective): days={settings.POLLING_ACTIVE_DAYS}; start={settings.POLLING_ACTIVE_START_HOUR}; end={settings.POLLING_ACTIVE_END_HOUR}; senders={len(settings.SENDER_LIST_FOR_POLLING)}; dedup_monthly_scope={settings.ENABLE_SUBJECT_GROUP_DEDUP}"
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

# 7. Deduplication Service (avec Redis ou fallback mémoire)
try:
    _dedup_service = DeduplicationService(
        redis_client=redis_client,  # None = fallback mémoire automatique
        logger=app.logger,
        config_service=_config_service,
        polling_config_service=_polling_service,
    )
    app.logger.info(f"SVC: DeduplicationService initialized {_dedup_service}")
except Exception as e:
    app.logger.error(f"SVC: Failed to initialize DeduplicationService: {e}")
    _dedup_service = None

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

def background_email_poller() -> None:
    """Delegate polling loop to background.polling_thread with injected deps."""
    def _is_ready_to_poll() -> bool:
        return all([email_config_valid, _polling_service.get_sender_list(), WEBHOOK_URL])

    def _run_cycle() -> int:
        return email_orchestrator.check_new_emails_and_trigger_webhook()

    def _is_in_vacation(now_dt: datetime) -> bool:
        try:
            return _polling_service.is_in_vacation(now_dt)
        except Exception:
            return False

    background_email_poller_loop(
        logger=app.logger,
        tz_for_polling=_polling_service.get_tz(),
        get_active_days=_polling_service.get_active_days,
        get_active_start_hour=_polling_service.get_active_start_hour,
        get_active_end_hour=_polling_service.get_active_end_hour,
        inactive_sleep_seconds=_polling_service.get_inactive_check_interval_s(),
        active_sleep_seconds=_polling_service.get_email_poll_interval_s(),
        is_in_vacation=_is_in_vacation,
        is_ready_to_poll=_is_ready_to_poll,
        run_poll_cycle=_run_cycle,
        max_consecutive_errors=5,
    )


# --- Make Scenarios Vacation Watcher ---
def make_scenarios_vacation_watcher() -> None:
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
    interval = max(60, _polling_service.get_inactive_check_interval_s())
    while True:
        try:
            enable_ui = _polling_service.get_enable_polling(True)
            in_vac = False
            try:
                in_vac = _polling_service.is_in_vacation(None)
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


def _start_daemon_thread(target, name: str) -> threading.Thread | None:
    """Helper pour démarrer un thread daemon de manière standardisée.
    
    Args:
        target: Fonction callable à exécuter dans le thread
        name: Nom descriptif du thread pour les logs
    
    Returns:
        Instance du thread créé, ou None si échec
    """
    try:
        thread = threading.Thread(target=target, daemon=True, name=name)
        thread.start()
        app.logger.info(f"THREAD: {name} started successfully")
        return thread
    except Exception as e:
        app.logger.error(f"THREAD: Failed to start {name}: {e}", exc_info=True)
        return None


# --- Start Background Tasks (Email Poller) ---
try:
    # Check legacy disable flag (priority override)
    disable_bg = os.environ.get("DISABLE_BACKGROUND_TASKS", "").strip().lower() in ["1", "true", "yes"]
    enable_bg = getattr(settings, "ENABLE_BACKGROUND_TASKS", False) and not disable_bg
    
    # Log effective config before starting background tasks
    try:
        app.logger.info(
            f"CFG BG: enable_polling(UI)={_polling_service.get_enable_polling(True)}; ENABLE_BACKGROUND_TASKS(env)={getattr(settings, 'ENABLE_BACKGROUND_TASKS', False)}; DISABLE_BACKGROUND_TASKS={disable_bg}"
        )
    except Exception:
        pass
    # Start background poller only if both the environment flag and the persisted
    # UI-controlled switch are enabled. This avoids unexpected background work
    # when the operator intentionally disabled polling from the dashboard.
    if enable_bg and _polling_service.get_enable_polling(True):
        lock_path = getattr(settings, "BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock")
        try:
            if acquire_singleton_lock(lock_path):
                app.logger.info(
                    f"BG_POLLER: Singleton lock acquired on {lock_path}. Starting background thread."
                )
                _bg_email_poller_thread = _start_daemon_thread(background_email_poller, "EmailPoller")
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
        if disable_bg:
            app.logger.info(
                "BG_POLLER: DISABLE_BACKGROUND_TASKS is set. Background poller not started."
            )
        elif not getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
            app.logger.info(
                "BG_POLLER: ENABLE_BACKGROUND_TASKS is false. Background poller not started."
            )
        elif not _polling_service.get_enable_polling(True):
            app.logger.info(
                "BG_POLLER: UI 'enable_polling' flag is false. Background poller not started."
            )
except Exception:
    # Defensive: never block app startup because of background thread wiring
    pass

# --- Start Make Scenarios Vacation Watcher ---
try:
    if enable_bg and bool(settings.MAKECOM_API_KEY):
        _make_watcher_thread = _start_daemon_thread(make_scenarios_vacation_watcher, "MakeVacationWatcher")
        if _make_watcher_thread:
            app.logger.info("MAKE_WATCHER: vacation-aware ON/OFF watcher active")
    else:
        if disable_bg:
            app.logger.info("MAKE_WATCHER: not started because DISABLE_BACKGROUND_TASKS is set")
        elif not getattr(settings, "ENABLE_BACKGROUND_TASKS", False):
            app.logger.info("MAKE_WATCHER: not started because ENABLE_BACKGROUND_TASKS is false")
        elif not bool(settings.MAKECOM_API_KEY):
            app.logger.info("MAKE_WATCHER: not started because MAKECOM_API_KEY is not configured (avoiding 401 noise)")
except Exception as e:
    app.logger.error(f"MAKE_WATCHER: failed to start thread: {e}")

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

def _log_webhook_config_startup():
    """Log la configuration webhook chargée depuis le service ou fichier de configuration."""
    try:
        # Préférer le service si disponible, sinon fallback sur chargement direct
        config = None
        if _webhook_service is not None:
            try:
                config = _webhook_service.get_all_config()
            except Exception:
                pass
        
        if config is None:
            from routes.api_webhooks import _load_webhook_config
            config = _load_webhook_config()
        
        if not config:
            app.logger.info("CFG WEBHOOK_CONFIG: Aucune configuration webhook trouvée (fichier vide ou inexistant)")
            return
            
        # Liste des clés à logger avec des valeurs par défaut si absentes
        keys_to_log = [
            'presence_flag',
            'webhook_ssl_verify',
            'webhook_sending_enabled',
            'webhook_time_start',
            'webhook_time_end',
            'global_time_start',
            'global_time_end'
        ]
        
        # Log chaque valeur individuellement pour une meilleure lisibilité
        for key in keys_to_log:
            value = config.get(key, 'non défini')
            app.logger.info("CFG WEBHOOK_CONFIG: %s=%s", key, value)
            
    except Exception as e:
        app.logger.warning("CFG WEBHOOK_CONFIG: Erreur lors de la lecture de la configuration: %s", str(e))

# Log de la configuration webhook au démarrage
_log_webhook_config_startup()

# Diagnostics: log effective custom webhook + mirroring configuration
try:
    app.logger.info(
        "CFG CUSTOM_WEBHOOK: WEBHOOK_URL configured=%s value=%s",
        bool(WEBHOOK_URL),
        (WEBHOOK_URL[:80] if WEBHOOK_URL else ""),
    )
    app.logger.info(
        "CFG PROCESSING_PREFS: mirror_media_to_custom=%s webhook_timeout_sec=%s",
        bool(PROCESSING_PREFS.get("mirror_media_to_custom")),
        PROCESSING_PREFS.get("webhook_timeout_sec"),
    )
except Exception:
    pass

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

