"""
utils.time_helpers
~~~~~~~~~~~~~~~~~~

Fonctions utilitaires pour le parsing et la validation des formats de temps.
Utilisées pour gérer les fenêtres horaires des webhooks et du polling IMAP.

Usage:
    from utils.time_helpers import parse_time_hhmm
    
    time_obj = parse_time_hhmm("13h30")
    # => datetime.time(13, 30)
"""

import re
from datetime import datetime, time as datetime_time
from typing import Optional


def parse_time_hhmm(s: str) -> Optional[datetime_time]:
    """
    Parse une chaîne au format 'HHhMM' ou 'HH:MM' en objet datetime.time.
    
    Formats acceptés:
    - "13h30", "9h00", "09h05"
    - "13:30", "9:00", "09:05"
    
    Args:
        s: Chaîne représentant l'heure au format HHhMM ou HH:MM
        
    Returns:
        datetime.time ou None si le format est invalide
        
    Examples:
        >>> parse_time_hhmm("13h30")
        datetime.time(13, 30)
        >>> parse_time_hhmm("9:00")
        datetime.time(9, 0)
        >>> parse_time_hhmm("invalid")
        None
    """
    if not s:
        return None
    try:
        s = s.strip().lower().replace("h", ":")
        m = re.match(r"^(\d{1,2}):(\d{2})$", s)
        if not m:
            return None
        hh = int(m.group(1))
        mm = int(m.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        return datetime_time(hh, mm)
    except Exception:
        return None


def is_within_time_window_local(
    now_dt: datetime,
    window_start: Optional[datetime_time],
    window_end: Optional[datetime_time]
) -> bool:
    """
    Vérifie si un datetime donné se trouve dans une fenêtre horaire.
    
    Gère correctement les fenêtres qui traversent minuit (ex: 22h00 - 02h00).
    Si les bornes ne sont pas définies, retourne toujours True (pas de contrainte).
    
    Args:
        now_dt: Datetime à vérifier
        window_start: Heure de début de fenêtre (datetime.time)
        window_end: Heure de fin de fenêtre (datetime.time)
        
    Returns:
        True si now_dt est dans la fenêtre, False sinon
        
    Examples:
        >>> from datetime import datetime, time
        >>> dt = datetime(2025, 1, 10, 14, 30)  # 14h30
        >>> is_within_time_window_local(dt, time(9, 0), time(18, 0))
        True
        >>> is_within_time_window_local(dt, time(22, 0), time(2, 0))  # Wrap midnight
        False
    """
    if not (window_start and window_end):
        return True
    
    now_t = now_dt.time()
    start = window_start
    end = window_end
    
    if start <= end:
        # Fenêtre normale (ex: 9h00 - 18h00)
        return start <= now_t < end
    else:
        # Fenêtre traversant minuit (ex: 22h00 - 02h00)
        return (now_t >= start) or (now_t < end)
