redis_client = None

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
from collections import deque
from utils.time_helpers import parse_time_hhmm as _parse_time_hhmm
from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url

from config import settings
from config import webhook_time_window
from config.app_config_store import get_config_json as _config_get
from config.app_config_store import set_config_json as _config_set

# Expose Gmail Push allowlist to ingress endpoint
GMAIL_SENDER_ALLOWLIST = settings.GMAIL_SENDER_ALLOWLIST

from services import (
    ConfigService,
    RuntimeFlagsService,
    WebhookConfigService,
    AuthService,
    DeduplicationService,
)

from auth import user as auth_user
from auth import helpers as auth_helpers
from auth.helpers import testapi_authorized as _testapi_authorized

from email_processing import pattern_matching as email_pattern_matching
from email_processing import webhook_sender as email_webhook_sender
from email_processing import orchestrator as email_orchestrator
from email_processing import link_extraction as email_link_extraction
from email_processing import payloads as email_payloads
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
    api_processing_bp,
    api_processing_legacy_bp,
    api_test_bp,
    dashboard_bp,
    api_logs_bp,
    api_admin_bp,
    api_utility_bp,
    api_config_bp,
    api_make_bp,
    api_auth_bp,
    api_routing_rules_bp,
    api_ingress_bp,
)
from routes.api_processing import DEFAULT_PROCESSING_PREFS as _DEFAULT_PROCESSING_PREFS
DEFAULT_PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS


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


def _init_redis_client(logger: logging.Logger | None = None):
    if not REDIS_AVAILABLE:
        return None
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis

        return redis.Redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        if logger:
            logger.warning("CFG REDIS: failed to initialize redis client: %s", e)
        return None


app = Flask(__name__, template_folder='.', static_folder='static')
app.secret_key = settings.FLASK_SECRET_KEY

_config_service = ConfigService()

_runtime_flags_service = None

_webhook_service = None

_auth_service = AuthService(_config_service)


app.register_blueprint(health_bp)
app.register_blueprint(api_webhooks_bp)
app.register_blueprint(api_processing_bp)
app.register_blueprint(api_processing_legacy_bp)
app.register_blueprint(api_test_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_logs_bp)
app.register_blueprint(api_admin_bp)
app.register_blueprint(api_utility_bp)
app.register_blueprint(api_config_bp)
app.register_blueprint(api_make_bp)
app.register_blueprint(api_auth_bp)
app.register_blueprint(api_routing_rules_bp)
app.register_blueprint(api_ingress_bp)

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

login_manager = _auth_service.init_flask_login(app, login_view='dashboard.login')

auth_user.init_login_manager(app, login_view='dashboard.login')

WEBHOOK_URL = settings.WEBHOOK_URL
MAKECOM_API_KEY = settings.MAKECOM_API_KEY
WEBHOOK_SSL_VERIFY = settings.WEBHOOK_SSL_VERIFY

EXPECTED_API_TOKEN = settings.EXPECTED_API_TOKEN

ENABLE_SUBJECT_GROUP_DEDUP = settings.ENABLE_SUBJECT_GROUP_DEDUP
SENDER_LIST_FOR_POLLING = settings.SENDER_LIST_FOR_POLLING

# Runtime flags and files
DISABLE_EMAIL_ID_DEDUP = settings.DISABLE_EMAIL_ID_DEDUP
ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS
TRIGGER_SIGNAL_FILE = settings.TRIGGER_SIGNAL_FILE
RUNTIME_FLAGS_FILE = settings.RUNTIME_FLAGS_FILE

# Configuration du logging
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
if not REDIS_AVAILABLE:
    logging.warning(
        "CFG REDIS (module level): 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")

redis_client = _init_redis_client(app.logger)


# Diagnostics (process start + heartbeat)
try:
    from datetime import datetime, timezone as _tz
    PROCESS_START_TIME = datetime.now(_tz.utc)
except Exception:
    PROCESS_START_TIME = None

# Process signal handlers (observability)
def _handle_sigterm(signum, frame):  # pragma: no cover - environment dependent
    try:
        app.logger.info("PROCESS: SIGTERM received; shutting down gracefully (platform restart/deploy).")
    except Exception:
        pass

try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except Exception:
    # Some environments may not allow setting signal handlers (e.g., Windows)
    pass


# Configuration (log centralisé)
settings.log_configuration(app.logger)
if not WEBHOOK_SSL_VERIFY:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app.logger.warning("CFG WEBHOOK: SSL verification DISABLED for webhook calls (development/legacy). Use valid certificates in production.")

TZ_FOR_POLLING = timezone.utc
try:
    tz_name = getattr(settings, "POLLING_TIMEZONE_STR", "UTC")
    if isinstance(tz_name, str) and tz_name.strip() and tz_name.strip().upper() != "UTC":
        if ZoneInfo is not None:
            TZ_FOR_POLLING = ZoneInfo(tz_name.strip())
except Exception:
    TZ_FOR_POLLING = timezone.utc

# =============================================================================
# SERVICES INITIALIZATION
# =============================================================================

# 5. Runtime Flags Service (Singleton)
try:
    from config import app_config_store

    _runtime_flags_service = RuntimeFlagsService.get_instance(
        file_path=settings.RUNTIME_FLAGS_FILE,
        defaults={
            "disable_email_id_dedup": bool(settings.DISABLE_EMAIL_ID_DEDUP),
            "allow_custom_webhook_without_links": bool(settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
            "gmail_ingress_enabled": True,
        },
        external_store=app_config_store,
    )
    app.logger.info(f"SVC: RuntimeFlagsService initialized (cache_ttl={_runtime_flags_service.get_cache_ttl()}s)")
except Exception as e:
    app.logger.error(f"SVC: Failed to initialize RuntimeFlagsService: {e}")
    _runtime_flags_service = None

# 6. Webhook Config Service (Singleton)
try:
    from config import app_config_store
    _webhook_service = WebhookConfigService.get_instance(
        file_path=Path(__file__).parent / "debug" / "webhook_config.json",
        external_store=app_config_store
    )
    app.logger.info(f"SVC: WebhookConfigService initialized (has_url={_webhook_service.has_webhook_url()})")
except Exception as e:
    app.logger.error(f"SVC: Failed to initialize WebhookConfigService: {e}")
    _webhook_service = None


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
        start_str=(
            os.environ.get("WEBHOOKS_TIME_START")
            or os.environ.get("WEBHOOK_TIME_START")
            or ""
        ),
        end_str=(
            os.environ.get("WEBHOOKS_TIME_END")
            or os.environ.get("WEBHOOK_TIME_END")
            or ""
        ),
    )
    webhook_time_window.reload_time_window_from_disk()
except Exception:
    pass

# --- Dedup constants mapping (from central settings) ---
PROCESSED_EMAIL_IDS_REDIS_KEY = settings.PROCESSED_EMAIL_IDS_REDIS_KEY
PROCESSED_SUBJECT_GROUPS_REDIS_KEY = settings.PROCESSED_SUBJECT_GROUPS_REDIS_KEY
SUBJECT_GROUP_REDIS_PREFIX = settings.SUBJECT_GROUP_REDIS_PREFIX
SUBJECT_GROUP_TTL_SECONDS = settings.SUBJECT_GROUP_TTL_SECONDS

# Memory fallback set for subject groups when Redis is not available
SUBJECT_GROUPS_MEMORY = set()

# 7. Deduplication Service (avec Redis ou fallback mémoire)
try:
    _dedup_service = DeduplicationService(
        redis_client=redis_client,  # None = fallback mémoire automatique
        logger=app.logger,
        config_service=_config_service,
    )
    app.logger.info(f"SVC: DeduplicationService initialized {_dedup_service}")
except Exception as e:
    app.logger.error(f"SVC: Failed to initialize DeduplicationService: {e}")
    _dedup_service = None


def check_media_solution_pattern(subject, email_content):
    """Compatibility wrapper delegating to email_processing.pattern_matching.

    Maintains backward compatibility while centralizing pattern detection.
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

    Maintient la compatibilité tout en centralisant la logique d'envoi.
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
        enable_monthly_scope=bool(ENABLE_SUBJECT_GROUP_DEDUP),
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
        enable_monthly_scope=bool(ENABLE_SUBJECT_GROUP_DEDUP),
        tz=TZ_FOR_POLLING,
        memory_set=SUBJECT_GROUPS_MEMORY,
    )



WEBHOOK_LOGS_FILE = Path(__file__).resolve().parent / "debug" / "webhook_logs.json"
WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"  # Redis list, each item is JSON string

# --- Processing Preferences (Filters, Reliability, Rate limiting) ---
PROCESSING_PREFS_FILE = Path(__file__).resolve().parent / "debug" / "processing_prefs.json"
PROCESSING_PREFS_REDIS_KEY = "r:ss:processing_prefs:v1"


try:
    PROCESSING_PREFS  # noqa: F401
except NameError:
    PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS.copy()


def _load_processing_prefs() -> dict:
    """Charge les préférences via app_config_store (Redis-first, fallback fichier)."""
    try:
        data = _config_get("processing_prefs", file_fallback=PROCESSING_PREFS_FILE) or {}
    except Exception:
        data = {}

    if isinstance(data, dict):
        return {**_DEFAULT_PROCESSING_PREFS, **data}
    return _DEFAULT_PROCESSING_PREFS.copy()


def _save_processing_prefs(prefs: dict) -> bool:
    """Sauvegarde via app_config_store (Redis-first, fallback fichier)."""
    try:
        return bool(_config_set("processing_prefs", prefs, file_fallback=PROCESSING_PREFS_FILE))
    except Exception:
        return False

PROCESSING_PREFS = _load_processing_prefs()

def _log_webhook_config_startup():
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

_log_webhook_config_startup()

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

