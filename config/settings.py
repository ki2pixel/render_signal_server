"""
config.settings
~~~~~~~~~~~~~~~

Configuration centralisée pour render_signal_server.
Contient toutes les constantes de référence et les variables d'environnement.

Ce module doit être importé au démarrage de l'application et fournit
un point unique pour accéder à toutes les configurations.
"""

import os
from pathlib import Path
from utils.validators import env_bool, normalize_make_webhook_url


# =============================================================================
# CONSTANTES DE RÉFÉRENCE (Defaults pour développement/fallback)
# =============================================================================

# --- Authentification Dashboard ---
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"

# --- Tokens API ---
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4gl3limu9cYkFw27u8dY"

# --- Configuration IMAP ---
REF_EMAIL_ADDRESS = "kidpixel@inbox.lt"
REF_EMAIL_PASSWORD = "YvP3Zw66Xx"  # Special IMAP/SMTP password for inbox.lt
REF_IMAP_SERVER = "mail.inbox.lt"
REF_IMAP_PORT = 993
REF_IMAP_USE_SSL = True

# --- URLs Webhooks ---
REF_WEBHOOK_URL = "https://webhook.kidpixel.fr/index.php"
# Deprecated: legacy Make.com webhook defaults removed; unified flow now uses WEBHOOK_URL only.
REF_MAKECOM_API_KEY = "12e8b61d-a78e-47f5-9f87-359af19f46cb"

# --- Configuration Polling Email ---
REF_SENDER_OF_INTEREST_FOR_POLLING = "achats@media-solution.fr,camille.moine.pro@gmail.com,a.peault@media-solution.fr,v.lorent@media-solution.fr,technique@media-solution.fr,t.deslus@media-solution.fr"
REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4"  # Lundi-Vendredi
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30


# =============================================================================
# VARIABLES D'ENVIRONNEMENT (Configuration Runtime)
# =============================================================================

# --- Authentification Dashboard ---
TRIGGER_PAGE_USER = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD = os.environ.get("TRIGGER_PAGE_PASSWORD", REF_TRIGGER_PAGE_PASSWORD)

# --- Configuration IMAP ---
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", REF_EMAIL_ADDRESS)
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", REF_EMAIL_PASSWORD)
IMAP_SERVER = os.environ.get("IMAP_SERVER", REF_IMAP_SERVER)
IMAP_PORT = int(os.environ.get("IMAP_PORT", REF_IMAP_PORT))
IMAP_USE_SSL = env_bool("IMAP_USE_SSL", REF_IMAP_USE_SSL)

# --- Tokens API ---
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN", REF_PROCESS_API_TOKEN)

# --- Configuration Webhooks ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", REF_WEBHOOK_URL)
# Deprecated: these legacy Make.com webhooks are no longer used by the application.
# They are intentionally set to empty strings to avoid accidental use.
RECADRAGE_MAKE_WEBHOOK_URL = ""
AUTOREPONDEUR_MAKE_WEBHOOK_URL = ""
MAKECOM_API_KEY = os.environ.get("MAKECOM_API_KEY", REF_MAKECOM_API_KEY)
WEBHOOK_SSL_VERIFY = env_bool("WEBHOOK_SSL_VERIFY", default=True)

# --- Webhooks de Présence ---
PRESENCE_FLAG = env_bool("PRESENCE", False)
PRESENCE_TRUE_MAKE_WEBHOOK_URL = normalize_make_webhook_url(os.environ.get("PRESENCE_TRUE_MAKE_WEBHOOK_URL"))
PRESENCE_FALSE_MAKE_WEBHOOK_URL = normalize_make_webhook_url(os.environ.get("PRESENCE_FALSE_MAKE_WEBHOOK_URL"))

# --- Configuration Polling Email ---
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get(
    "SENDER_OF_INTEREST_FOR_POLLING", 
    REF_SENDER_OF_INTEREST_FOR_POLLING
)
SENDER_LIST_FOR_POLLING = [
    e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') 
    if e.strip()
] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []

# --- Timezone et Heures de Polling ---
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR))

# --- Jours Actifs de Polling (0=Lundi, 6=Dimanche) ---
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS)
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [
            int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') 
            if d.strip().isdigit() and 0 <= int(d.strip()) <= 6
        ]
    except ValueError:
        # Fallback: Lundi-Vendredi
        POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
if not POLLING_ACTIVE_DAYS:
    POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]

# --- Intervalle de Polling ---
EMAIL_POLLING_INTERVAL_SECONDS = int(
    os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS)
)
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(
    os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600)
)

# --- Contrôle des tâches de fond (poller IMAP) ---
# Doit être activé explicitement en production pour démarrer le thread de polling.
ENABLE_BACKGROUND_TASKS = env_bool("ENABLE_BACKGROUND_TASKS", False)
BG_POLLER_LOCK_FILE = os.environ.get(
    "BG_POLLER_LOCK_FILE", "/tmp/render_signal_server_email_poller.lock"
)

# --- Feature Flags ---
ENABLE_SUBJECT_GROUP_DEDUP = env_bool("ENABLE_SUBJECT_GROUP_DEDUP", True)
DISABLE_EMAIL_ID_DEDUP = env_bool("DISABLE_EMAIL_ID_DEDUP", False)
# Autoriser l'envoi du webhook custom même sans liens détectés (contrôlé par l'UI)
ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS = env_bool("ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False)

# --- Chemins des Fichiers de Configuration/Debug ---
BASE_DIR = Path(__file__).resolve().parent.parent  # Racine du projet
DEBUG_DIR = BASE_DIR / "debug"
WEBHOOK_CONFIG_FILE = DEBUG_DIR / "webhook_config.json"
WEBHOOK_LOGS_FILE = DEBUG_DIR / "webhook_logs.json"
PROCESSING_PREFS_FILE = DEBUG_DIR / "processing_prefs.json"
TIME_WINDOW_OVERRIDE_FILE = DEBUG_DIR / "webhook_time_window.json"
# Fichier de configuration du polling (persisté par l'UI)
POLLING_CONFIG_FILE = DEBUG_DIR / "polling_config.json"
# Fichier des flags runtime (persistés pour survivre aux redémarrages)
RUNTIME_FLAGS_FILE = DEBUG_DIR / "runtime_flags.json"
# Signal local consommé par /api/check_trigger
SIGNAL_DIR = BASE_DIR / "signal_data_app_render"
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"

# --- Clés Redis ---
WEBHOOK_LOGS_REDIS_KEY = "r:ss:webhook_logs:v1"

# Deduplication keys (subject groups and per-email) for Redis
# Used by app_render and deduplication module (Step 7A wiring)
PROCESSED_EMAIL_IDS_REDIS_KEY = os.environ.get("PROCESSED_EMAIL_IDS_REDIS_KEY", "r:ss:processed_email_ids:v1")
PROCESSED_SUBJECT_GROUPS_REDIS_KEY = os.environ.get(
    "PROCESSED_SUBJECT_GROUPS_REDIS_KEY", "r:ss:processed_subject_groups:v1"
)
# Prefix for TTL-based subject group keys; final key = SUBJECT_GROUP_REDIS_PREFIX + <scoped_group_id>
SUBJECT_GROUP_REDIS_PREFIX = os.environ.get("SUBJECT_GROUP_REDIS_PREFIX", "r:ss:subject_group_ttl:")

# --- Durée de déduplication des sujets (en secondes) ---
# Si > 0, utilise un TTL Redis pour la déduplication au lieu d'un hash mensuel
SUBJECT_GROUP_TTL_SECONDS = int(os.environ.get("SUBJECT_GROUP_TTL_SECONDS", 0))


# =============================================================================
# FONCTIONS HELPER POUR LOGGING (Utilisées au démarrage de l'app)
# =============================================================================

def log_configuration(logger):
    """
    Log toutes les configurations importantes au démarrage de l'application.
    
    Args:
        logger: Instance de logger Flask (app.logger)
    """
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
        logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...')")
    
    logger.info(f"CFG DEDUP: ENABLE_SUBJECT_GROUP_DEDUP={ENABLE_SUBJECT_GROUP_DEDUP}")
    logger.info(f"CFG DEDUP: DISABLE_EMAIL_ID_DEDUP={DISABLE_EMAIL_ID_DEDUP}")
    
    # Visibilité opérationnelle du poller IMAP
    logger.info(f"CFG BG: ENABLE_BACKGROUND_TASKS={ENABLE_BACKGROUND_TASKS}")
    logger.info(f"CFG BG: BG_POLLER_LOCK_FILE={BG_POLLER_LOCK_FILE}")
