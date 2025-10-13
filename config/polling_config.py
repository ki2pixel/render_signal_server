"""
config.polling_config
~~~~~~~~~~~~~~~~~~~~~

Configuration et helpers pour le polling IMAP.
Gère le timezone, la fenêtre horaire, et les paramètres de vacances.
"""

from datetime import timezone, datetime, date
from config.settings import POLLING_TIMEZONE_STR, POLLING_CONFIG_FILE
import json

# Tentative d'import de ZoneInfo (Python 3.9+)
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


# =============================================================================
# TIMEZONE POUR LE POLLING
# =============================================================================

TZ_FOR_POLLING = None

def initialize_polling_timezone(logger):
    """
    Initialise le timezone pour le polling IMAP.
    
    Args:
        logger: Instance de logger Flask (app.logger)
    
    Returns:
        ZoneInfo ou timezone.utc
    """
    global TZ_FOR_POLLING
    
    if POLLING_TIMEZONE_STR.upper() != "UTC":
        if ZoneInfo:
            try:
                TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
                logger.info(f"CFG POLL: Using timezone '{POLLING_TIMEZONE_STR}' for polling schedule.")
            except Exception as e:
                logger.warning(f"CFG POLL: Error loading TZ '{POLLING_TIMEZONE_STR}': {e}. Using UTC.")
                TZ_FOR_POLLING = timezone.utc
        else:
            logger.warning(f"CFG POLL: 'zoneinfo' module not available. Using UTC. '{POLLING_TIMEZONE_STR}' ignored.")
            TZ_FOR_POLLING = timezone.utc
    else:
        TZ_FOR_POLLING = timezone.utc
    
    if TZ_FOR_POLLING is None or TZ_FOR_POLLING == timezone.utc:
        logger.info(f"CFG POLL: Using timezone 'UTC' for polling schedule (default or fallback).")
    
    return TZ_FOR_POLLING


# =============================================================================
# GESTION DES VACANCES (VACATION MODE)
# =============================================================================

POLLING_VACATION_START_DATE = None
POLLING_VACATION_END_DATE = None

def set_vacation_period(start_date: date | None, end_date: date | None, logger):
    """
    Définit une période de vacances pendant laquelle le polling est désactivé.
    
    Args:
        start_date: Date de début (incluse) ou None pour désactiver
        end_date: Date de fin (incluse) ou None pour désactiver
        logger: Instance de logger Flask
    """
    global POLLING_VACATION_START_DATE, POLLING_VACATION_END_DATE
    
    POLLING_VACATION_START_DATE = start_date
    POLLING_VACATION_END_DATE = end_date
    
    if start_date and end_date:
        logger.info(f"CFG POLL: Vacation mode enabled from {start_date} to {end_date}")
    else:
        logger.info("CFG POLL: Vacation mode disabled")


def is_in_vacation_period(check_date: date = None) -> bool:
    """
    Vérifie si une date donnée est dans la période de vacances.
    
    Args:
        check_date: Date à vérifier (utilise aujourd'hui si None)
    
    Returns:
        True si dans la période de vacances, False sinon
    """
    if not check_date:
        check_date = datetime.now(TZ_FOR_POLLING if TZ_FOR_POLLING else timezone.utc).date()
    
    if not (POLLING_VACATION_START_DATE and POLLING_VACATION_END_DATE):
        return False
    
    return POLLING_VACATION_START_DATE <= check_date <= POLLING_VACATION_END_DATE


# =============================================================================
# HELPERS POUR VALIDATION DES JOURS ET HEURES
# =============================================================================

def is_polling_active(now_dt: datetime, active_days: list[int], 
                     start_hour: int, end_hour: int) -> bool:
    """
    Vérifie si le polling est actif pour un datetime donné.
    
    Args:
        now_dt: Datetime à vérifier (avec timezone)
        active_days: Liste des jours actifs (0=Lundi, 6=Dimanche)
        start_hour: Heure de début (0-23)
        end_hour: Heure de fin (0-23)
    
    Returns:
        True si le polling est actif, False sinon
    """
    # Vérifier les vacances
    if is_in_vacation_period(now_dt.date()):
        return False
    
    # Vérifier le jour de la semaine
    is_active_day = now_dt.weekday() in active_days
    
    # Vérifier l'heure
    is_active_time = start_hour <= now_dt.hour < end_hour
    
    return is_active_day and is_active_time


# =============================================================================
# GLOBAL ENABLE (BOOT-TIME POLLER SWITCH)
# =============================================================================

def get_enable_polling(default: bool = True) -> bool:
    """Return whether polling is globally enabled from the persisted polling config.

    Why: UI may disable polling at the configuration level (in addition to the
    environment flag ENABLE_BACKGROUND_TASKS). This helper centralizes reading
    of the persisted switch stored alongside other polling parameters in
    POLLING_CONFIG_FILE.

    Notes:
    - If the file or the key is missing/invalid, we fall back to `default=True`
      to preserve the existing behavior (polling enabled unless explicitly
      disabled via UI).
    """
    try:
        if not POLLING_CONFIG_FILE.exists():
            return bool(default)
        with open(POLLING_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        val = data.get("enable_polling")
        # Accept truthy/falsy representations robustly
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            s = val.strip().lower()
            if s in {"1", "true", "yes", "y", "on"}:
                return True
            if s in {"0", "false", "no", "n", "off"}:
                return False
        return bool(default)
    except Exception:
        return bool(default)
