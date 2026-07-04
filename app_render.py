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
    IngressService,
)

from auth import user as auth_user
from auth import helpers as auth_helpers
from auth.helpers import testapi_authorized as _testapi_authorized

from email_processing import pattern_matching as email_pattern_matching
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
    api_auth_bp,
    api_routing_rules_bp,
    api_ingress_bp,
)
from routes.api_processing import DEFAULT_PROCESSING_PREFS as _DEFAULT_PROCESSING_PREFS
DEFAULT_PROCESSING_PREFS = _DEFAULT_PROCESSING_PREFS




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

        return redis.Redis.from_url(redis_url, decode_responses=True, protocol=2)
    except Exception as e:
        if logger:
            logger.warning("CFG REDIS: failed to initialize redis client: %s", e)
        return None


# Module level service pointers populated during create_app()
_config_service = None
_runtime_flags_service = None
_webhook_service = None
_auth_service = None
_dedup_service = None
_ingress_service = None
login_manager = None

WEBHOOK_URL = settings.WEBHOOK_URL
WEBHOOK_SSL_VERIFY = settings.WEBHOOK_SSL_VERIFY
EXPECTED_API_TOKEN = settings.EXPECTED_API_TOKEN
ENABLE_SUBJECT_GROUP_DEDUP = settings.ENABLE_SUBJECT_GROUP_DEDUP
SENDER_LIST_FOR_POLLING = settings.SENDER_LIST_FOR_POLLING
DISABLE_EMAIL_ID_DEDUP = settings.DISABLE_EMAIL_ID_DEDUP
ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = settings.ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS
TRIGGER_SIGNAL_FILE = settings.TRIGGER_SIGNAL_FILE
RUNTIME_FLAGS_FILE = settings.RUNTIME_FLAGS_FILE

# Diagnostics (process start + heartbeat)
try:
    from datetime import datetime, timezone as _tz
    PROCESS_START_TIME = datetime.now(_tz.utc)
except Exception:
    PROCESS_START_TIME = None

from utils.time_helpers import get_polling_timezone
TZ_FOR_POLLING = get_polling_timezone()

WEBHOOK_LOGS_FILE = Path(__file__).resolve().parent / "debug" / "webhook_logs.json"
WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"
PROCESSING_PREFS_FILE = Path(__file__).resolve().parent / "debug" / "processing_prefs.json"
PROCESSING_PREFS_REDIS_KEY = "r:ss:processing_prefs:v1"

PROCESSED_EMAIL_IDS_REDIS_KEY = settings.PROCESSED_EMAIL_IDS_REDIS_KEY
PROCESSED_SUBJECT_GROUPS_REDIS_KEY = settings.PROCESSED_SUBJECT_GROUPS_REDIS_KEY
SUBJECT_GROUP_REDIS_PREFIX = settings.SUBJECT_GROUP_REDIS_PREFIX
SUBJECT_GROUP_TTL_SECONDS = settings.SUBJECT_GROUP_TTL_SECONDS
EMAIL_ID_INFLIGHT_LOCK_PREFIX = settings.EMAIL_ID_INFLIGHT_LOCK_PREFIX
EMAIL_ID_INFLIGHT_LOCK_TTL_SECONDS = settings.EMAIL_ID_INFLIGHT_LOCK_TTL_SECONDS
SUBJECT_GROUPS_MEMORY = set()
email_config_valid = False


def _log_webhook_config_startup(app_instance: Flask):
    try:
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
            app_instance.logger.info("CFG WEBHOOK_CONFIG: Aucune configuration webhook trouvée (fichier vide ou inexistant)")
            return
        keys_to_log = [
            'webhook_ssl_verify', 'webhook_sending_enabled', 'webhook_time_start',
            'webhook_time_end', 'global_time_start', 'global_time_end'
        ]
        for key in keys_to_log:
            value = config.get(key, 'non défini')
            app_instance.logger.info("CFG WEBHOOK_CONFIG: %s=%s", key, value)
    except Exception as e:
        app_instance.logger.warning("CFG WEBHOOK_CONFIG: Erreur lors de la lecture de la configuration: %s", str(e))


def create_app(config_class=None) -> Flask:
    """Application Factory to create and configure the Flask application."""
    app = Flask(__name__, template_folder='.', static_folder='static')
    app.secret_key = settings.FLASK_SECRET_KEY

    # 1. CORS Setup
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

    # 2. Register Blueprints
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
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(api_routing_rules_bp)
    app.register_blueprint(api_ingress_bp)

    # 3. Context Processor
    @app.context_processor
    def inject_bundler_helpers():
        import json
        from flask import url_for
        dist_path = os.path.join(app.root_path, "static", "dist")
        use_bundle = os.path.exists(dist_path)
        bundled_js = ""
        bundled_css = []
        if use_bundle:
            manifest_paths = [
                os.path.join(dist_path, ".vite", "manifest.json"),
                os.path.join(dist_path, "manifest.json")
            ]
            manifest = None
            for path in manifest_paths:
                if os.path.exists(path):
                    try:
                        with open(path, "r") as f:
                            manifest = json.load(f)
                        break
                    except Exception as e:
                        app.logger.warning(f"Impossible de charger le manifest Vite à {path}: {e}")
            if manifest:
                try:
                    js_entry = "static/dashboard.js"
                    if js_entry in manifest:
                        bundled_js = url_for("static", filename=f"dist/{manifest[js_entry]['file']}")
                    css_entry = "static/css/dashboard-bundle.css"
                    if css_entry in manifest:
                        bundled_css.append(url_for("static", filename=f"dist/{manifest[css_entry]['file']}"))
                except Exception as e:
                    app.logger.warning(f"Erreur lors de l'extraction des assets du manifest: {e}")
            if not bundled_js:
                if os.path.exists(os.path.join(dist_path, "js", "dashboard.js")):
                    bundled_js = url_for("static", filename="dist/js/dashboard.js")
                if os.path.exists(os.path.join(dist_path, "css", "dashboard-bundle.css")):
                    bundled_css.append(url_for("static", filename="dist/css/dashboard-bundle.css"))
        return {"use_bundle": use_bundle, "bundled_js": bundled_js, "bundled_css": bundled_css}

    # 4. Logging configuration
    log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')

    # 5. Redis Client
    global redis_client
    redis_client = _init_redis_client(app.logger)

    # 6. Service instances
    global _config_service, _runtime_flags_service, _webhook_service, _auth_service, _dedup_service, _ingress_service, login_manager, email_config_valid
    _config_service = ConfigService()
    _auth_service = AuthService(_config_service)
    login_manager = _auth_service.init_flask_login(app, login_view='dashboard.login')
    auth_user.init_login_manager(app, login_view='dashboard.login')

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

    email_config_valid = _config_service.is_email_config_valid()

    try:
        webhook_time_window.initialize_webhook_time_window(
            start_str=(os.environ.get("WEBHOOKS_TIME_START") or os.environ.get("WEBHOOK_TIME_START") or ""),
            end_str=(os.environ.get("WEBHOOKS_TIME_END") or os.environ.get("WEBHOOK_TIME_END") or ""),
        )
        webhook_time_window.reload_time_window_from_disk()
    except Exception:
        pass

    try:
        _dedup_service = DeduplicationService.get_instance(
            redis_client=redis_client,
            logger=app.logger,
            config_service=_config_service,
        )
        app.logger.info(f"SVC: DeduplicationService initialized {_dedup_service}")
    except Exception as e:
        app.logger.error(f"SVC: Failed to initialize DeduplicationService: {e}")
        _dedup_service = None

    try:
        _ingress_service = IngressService.get_instance(
            config_service=_config_service,
        )
        app.logger.info("SVC: IngressService initialized")
    except Exception as e:
        app.logger.error(f"SVC: Failed to initialize IngressService: {e}")
        _ingress_service = None

    # Log Startup Configurations
    settings.log_configuration(app.logger)
    if not WEBHOOK_SSL_VERIFY:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        app.logger.warning("CFG WEBHOOK: SSL verification DISABLED for webhook calls (development/legacy). Use valid certificates in production.")

    _log_webhook_config_startup(app)

    try:
        app.logger.info(
            "CFG CUSTOM_WEBHOOK: WEBHOOK_URL configured=%s value=%s",
            bool(WEBHOOK_URL),
            (WEBHOOK_URL[:80] if WEBHOOK_URL else ""),
        )
    except Exception:
        pass

    return app


# Maintain backward compatibility with Gunicorn gunicorn app_render:app
app = create_app()

# Process signal handlers (observability)
def _handle_sigterm(signum, frame):  # pragma: no cover - environment dependent
    try:
        app.logger.info("PROCESS: SIGTERM received; shutting down gracefully (platform restart/deploy).")
    except Exception:
        pass

try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except Exception:
    pass
