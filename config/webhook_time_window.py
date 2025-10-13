"""
config.webhook_time_window
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gestion de la fenêtre horaire pour l'envoi des webhooks.
Permet de définir une plage horaire pendant laquelle les webhooks sont envoyés,
avec support pour les overrides persistés via fichier JSON.
"""

import json
from datetime import datetime, time as datetime_time
from pathlib import Path
from typing import Optional, Tuple

from utils.time_helpers import parse_time_hhmm, is_within_time_window_local
from config.settings import TIME_WINDOW_OVERRIDE_FILE


# =============================================================================
# VARIABLES GLOBALES - FENÊTRE HORAIRE DES WEBHOOKS
# =============================================================================

# Fenêtre horaire par défaut (depuis variables d'environnement)
WEBHOOKS_TIME_START_STR = ""
WEBHOOKS_TIME_END_STR = ""
WEBHOOKS_TIME_START = None  # datetime.time or None
WEBHOOKS_TIME_END = None    # datetime.time or None


def initialize_webhook_time_window(start_str: str = "", end_str: str = ""):
    """
    Initialise la fenêtre horaire des webhooks depuis les variables d'environnement.
    
    Args:
        start_str: Heure de début au format "HHhMM" ou "HH:MM" (vide = pas de contrainte)
        end_str: Heure de fin au format "HHhMM" ou "HH:MM" (vide = pas de contrainte)
    """
    global WEBHOOKS_TIME_START_STR, WEBHOOKS_TIME_END_STR
    global WEBHOOKS_TIME_START, WEBHOOKS_TIME_END
    
    WEBHOOKS_TIME_START_STR = start_str
    WEBHOOKS_TIME_END_STR = end_str
    WEBHOOKS_TIME_START = parse_time_hhmm(start_str)
    WEBHOOKS_TIME_END = parse_time_hhmm(end_str)


def reload_time_window_from_disk() -> None:
    """
    Recharge les valeurs de fenêtre horaire depuis un fichier JSON si présent.
    Permet des overrides dynamiques sans redémarrage de l'application.
    """
    global WEBHOOKS_TIME_START_STR, WEBHOOKS_TIME_END_STR
    global WEBHOOKS_TIME_START, WEBHOOKS_TIME_END
    
    try:
        if TIME_WINDOW_OVERRIDE_FILE.exists():
            with open(TIME_WINDOW_OVERRIDE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            s = (data.get('start') or '').strip()
            e = (data.get('end') or '').strip()
            if s or e:
                ps = parse_time_hhmm(s) if s else None
                pe = parse_time_hhmm(e) if e else None
                if (ps is None and s) or (pe is None and e):
                    # invalid content on disk; ignore
                    return
                WEBHOOKS_TIME_START_STR = s
                WEBHOOKS_TIME_END_STR = e
                WEBHOOKS_TIME_START = ps
                WEBHOOKS_TIME_END = pe
    except Exception:
        # lecture échouée: ne pas bloquer la logique
        pass


def check_within_time_window(now_dt: datetime) -> bool:
    """
    Vérifie si un datetime donné est dans la fenêtre horaire des webhooks.
    Recharge automatiquement les overrides depuis le disque pour prendre en compte
    les modifications récentes.
    
    Args:
        now_dt: Datetime à vérifier (avec timezone)
    
    Returns:
        True si dans la fenêtre horaire ou si aucune contrainte, False sinon
    """
    # Toujours tenter de recharger depuis disque pour prendre en compte un override récent
    reload_time_window_from_disk()
    
    return is_within_time_window_local(now_dt, WEBHOOKS_TIME_START, WEBHOOKS_TIME_END)


def update_time_window(str_start: Optional[str], str_end: Optional[str]) -> Tuple[bool, str]:
    """
    Met à jour la fenêtre horaire des webhooks en mémoire et la persiste sur disque.
    
    Args:
        str_start: Heure de début au format "HHhMM" ou "HH:MM" (ou vide pour désactiver)
        str_end: Heure de fin au format "HHhMM" ou "HH:MM" (ou vide pour désactiver)
    
    Returns:
        Tuple (success: bool, message: str)
    """
    global WEBHOOKS_TIME_START_STR, WEBHOOKS_TIME_END_STR
    global WEBHOOKS_TIME_START, WEBHOOKS_TIME_END
    
    s = (str_start or "").strip()
    e = (str_end or "").strip()
    
    # Allow clearing by sending empty values
    if not s and not e:
        WEBHOOKS_TIME_START_STR = ""
        WEBHOOKS_TIME_END_STR = ""
        WEBHOOKS_TIME_START = None
        WEBHOOKS_TIME_END = None
        try:
            # Écrire un override vide pour signaler la désactivation
            TIME_WINDOW_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TIME_WINDOW_OVERRIDE_FILE, 'w', encoding='utf-8') as f:
                json.dump({"start": "", "end": ""}, f)
        except Exception:
            pass
        return True, "Time window cleared (no constraints)."
    
    # Both must be provided for enforcement
    if not s or not e:
        return False, "Both WEBHOOKS_TIME_START and WEBHOOKS_TIME_END must be provided (or both empty to clear)."
    
    ps = parse_time_hhmm(s)
    pe = parse_time_hhmm(e)
    if ps is None or pe is None:
        return False, "Invalid time format. Use HHhMM or HH:MM (e.g., 11h30, 17:45)."
    
    WEBHOOKS_TIME_START_STR = s
    WEBHOOKS_TIME_END_STR = e
    WEBHOOKS_TIME_START = ps
    WEBHOOKS_TIME_END = pe
    
    # Persister l'override pour redémarrages/rechargements
    try:
        TIME_WINDOW_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TIME_WINDOW_OVERRIDE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"start": s, "end": e}, f)
    except Exception:
        pass
    
    return True, "Time window updated."


def get_time_window_info() -> dict:
    """
    Retourne les informations actuelles sur la fenêtre horaire des webhooks.
    
    Returns:
        Dict avec les clés 'start', 'end', 'active'
    """
    reload_time_window_from_disk()
    
    return {
        "start": WEBHOOKS_TIME_START_STR,
        "end": WEBHOOKS_TIME_END_STR,
        "active": bool(WEBHOOKS_TIME_START and WEBHOOKS_TIME_END)
    }
