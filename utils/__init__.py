"""
utils
~~~~~

Module utilitaire regroupant les helpers réutilisables du projet.
Contient des fonctions pures sans effets de bord pour le traitement
du temps, du texte et la validation des données.
"""

from .time_helpers import parse_time_hhmm, is_within_time_window_local
from .text_helpers import (
    normalize_no_accents_lower_trim,
    strip_leading_reply_prefixes,
    detect_provider,
)
from .validators import env_bool, normalize_make_webhook_url

__all__ = [
    # Time helpers
    "parse_time_hhmm",
    "is_within_time_window_local",
    # Text helpers
    "normalize_no_accents_lower_trim",
    "strip_leading_reply_prefixes",
    "detect_provider",
    # Validators
    "env_bool",
    "normalize_make_webhook_url",
]
