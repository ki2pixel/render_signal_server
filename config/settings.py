"""
Centralized configuration for render_signal_server.
Contains all reference constants and environment variables.
"""

import os
from pathlib import Path
from utils.validators import env_bool


REF_TRIGGER_PAGE_USER = "admin"
REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4"
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30


# --- Environment Variables ---
def _get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


FLASK_SECRET_KEY = _get_required_env("FLASK_SECRET_KEY")

TRIGGER_PAGE_USER = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD = _get_required_env("TRIGGER_PAGE_PASSWORD")

EMAIL_ADDRESS = _get_required_env("EMAIL_ADDRESS")
EMAIL_PASSWORD = _get_required_env("EMAIL_PASSWORD")
IMAP_SERVER = _get_required_env("IMAP_SERVER")
IMAP_PORT = int(os.environ.get("IMAP_PORT", 993))
IMAP_USE_SSL = env_bool("IMAP_USE_SSL", True)

EXPECTED_API_TOKEN = _get_required_env("PROCESS_API_TOKEN")

WEBHOOK_URL = _get_required_env("WEBHOOK_URL")
MAKECOM_API_KEY = _get_required_env("MAKECOM_API_KEY")
WEBHOOK_SSL_VERIFY = env_bool("WEBHOOK_SSL_VERIFY", default=True)

# --- Render API Configuration ---
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "")
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID", "")
_CLEAR_DEFAULT = "do_not_clear"
RENDER_DEPLOY_CLEAR_CACHE = os.environ.get("RENDER_DEPLOY_CLEAR_CACHE", _CLEAR_DEFAULT)
if RENDER_DEPLOY_CLEAR_CACHE not in ("clear", "do_not_clear"):
    RENDER_DEPLOY_CLEAR_CACHE = _CLEAR_DEFAULT

RENDER_DEPLOY_HOOK_URL = os.environ.get("RENDER_DEPLOY_HOOK_URL", "")


SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get(
    "SENDER_OF_INTEREST_FOR_POLLING",
    "",
)
SENDER_LIST_FOR_POLLING = [
    e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') 
    if e.strip()
] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []

POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR))

POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS)
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [
            int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') 
            if d.strip().isdigit() and 0 <= int(d.strip()) <= 6
        ]
    except ValueError:
        POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
if not POLLING_ACTIVE_DAYS:
    POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]

EMAIL_POLLING_INTERVAL_SECONDS = int(
    os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS)
)
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(
    os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600)
)

ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", False)
BG_POLLER_LOCK_FILE = os.environ.get(
    "BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock"
)

ENABLE_SUBJECT_GROUP_DEDUP = env_bool("ENABLE_SUBJECT_GROUP_DEDUP", True)
DISABLE_EMAIL_ID_DEDUP = env_bool("DISABLE_EMAIL_ID_DEDUP", False)
ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = env_bool("ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False)

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG_DIR = BASE_DIR / "debug"
WEBHOOK_CONFIG_FILE = DEBUG_DIR / "webhook_config.json"
WEBHOOK_LOGS_FILE = DEBUG_DIR / "webhook_logs.json"
PROCESSING_PREFS_FILE = DEBUG_DIR / "processing_prefs.json"
TIME_WINDOW_OVERRIDE_FILE = DEBUG_DIR / "webhook_time_window.json"
POLLING_CONFIG_FILE = DEBUG_DIR / "polling_config.json"
RUNTIME_FLAGS_FILE = DEBUG_DIR / "runtime_flags.json"
SIGNAL_DIR = BASE_DIR / "signal_data_app_render"
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
_MAGIC_LINK_FILE_DEFAULT = DEBUG_DIR / "magic_links.json"
MAGIC_LINK_TOKENS_FILE = Path(os.environ.get("MAGIC_LINK_TOKENS_FILE", str(_MAGIC_LINK_FILE_DEFAULT)))

R2_FETCH_ENABLED = env_bool("R2_FETCH_ENABLED", False)
R2_FETCH_ENDPOINT = os.environ.get("R2_FETCH_ENDPOINT", "")
R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
WEBHOOK_LINKS_FILE = os.environ.get(
    "WEBHOOK_LINKS_FILE",
    str(BASE_DIR / "deployment" / "data" / "webhook_links.json")
)
R2_LINKS_MAX_ENTRIES = int(os.environ.get("R2_LINKS_MAX_ENTRIES", 1000))

# Magic link TTL (seconds)
MAGIC_LINK_TTL_SECONDS = int(os.environ.get("MAGIC_LINK_TTL_SECONDS", 900))

WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"

PROCESSED_EMAIL_IDS_REDIS_KEY = os.environ.get("PROCESSED_EMAIL_IDS_REDIS_KEY", "r:ss:processed_email_ids:v1")
PROCESSED_SUBJECT_GROUPS_REDIS_KEY = os.environ.get(
    "PROCESSED_SUBJECT_GROUPS_REDIS_KEY", "r:ss:processed_subject_groups:v1"
)
SUBJECT_GROUP_REDIS_PREFIX = os.environ.get("SUBJECT_GROUP_REDIS_PREFIX", "r:ss:subject_group_ttl:")

SUBJECT_GROUP_TTL_SECONDS = int(os.environ.get("SUBJECT_GROUP_TTL_SECONDS", 0))


def log_configuration(logger):
    logger.info(f"CFG WEBHOOK: Custom webhook URL configured to: {WEBHOOK_URL}")
    logger.info(f"CFG WEBHOOK: SSL verification = {WEBHOOK_SSL_VERIFY}")
    
    if SENDER_LIST_FOR_POLLING:
        logger.info(
            f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}"
        )
    else:
        logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling likely ineffective.")
    
    if not EXPECTED_API_TOKEN:
        logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
    else:
        logger.info("CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured.")
    
    logger.info(f"CFG DEDUP: ENABLE_SUBJECT_GROUP_DEDUP={ENABLE_SUBJECT_GROUP_DEDUP}")
    logger.info(f"CFG DEDUP: DISABLE_EMAIL_ID_DEDUP={DISABLE_EMAIL_ID_DEDUP}")
    
    logger.info(f"CFG BG: ENABLE_BACKGROUND_TASKS={ENABLE_BACKGROUND_TASKS}")
    logger.info(f"CFG BG: BG_POLLER_LOCK_FILE={BG_POLLER_LOCK_FILE}")
