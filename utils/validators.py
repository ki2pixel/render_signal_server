"""
utils.validators
~~~~~~~~~~~~~~~~

Fonctions de validation et normalisation des données de configuration.
Utilisées pour valider les variables d'environnement et les inputs utilisateur.

Usage:
    from utils.validators import env_bool, normalize_make_webhook_url
    
    is_active = env_bool("ENABLE_FEATURE", default=False)
    webhook_url = normalize_make_webhook_url("token@hook.eu2.make.com")
"""

import os
from typing import Optional


def env_bool(value_or_name: Optional[str], default: bool = False) -> bool:
    """
    Lit une variable d'environnement et la convertit en booléen.
    
    Valeurs considérées comme True: "1", "true", "yes", "y", "on" (insensible à la casse)
    Si la variable n'existe pas, retourne la valeur par défaut.
    
    Args:
        value_or_name: Soit une valeur littérale ("true", "1", etc.), soit un nom de variable d'environnement
        default: Valeur par défaut si la variable n'existe pas ou valeur invalide
        
    Returns:
        Booléen correspondant à la valeur de la variable
        
    Examples:
        >>> os.environ["ENABLE_FEATURE"] = "true"
        >>> env_bool("ENABLE_FEATURE")
        True
        >>> env_bool("NON_EXISTENT", default=False)
        False
    """
    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}

    if value_or_name is None:
        return default

    s = str(value_or_name).strip()
    lower = s.lower()

    # Chaîne vide → utilise le défaut
    if lower == "":
        return default

    # Si la valeur fournie est un littéral connu, retourner directement
    if lower in truthy:
        return True
    if lower in falsy:
        return False

    # Sinon, interpréter comme un nom de variable d'environnement
    if isinstance(value_or_name, str):
        env_val = os.environ.get(value_or_name)
        if env_val is None:
            return default
        return str(env_val).strip().lower() in truthy

    return default


def normalize_make_webhook_url(value: Optional[str]) -> Optional[str]:
    """
    Normalise une URL de webhook Make.com en format HTTPS complet.
    
    Formats d'entrée acceptés:
    1. URL complète: "https://hook.eu2.make.com/<token>"
    2. Format email/alias: "<token>@hook.eu2.make.com"
    3. Token seul: "<token>" (sans slashes ni @)
    
    Args:
        value: Valeur à normaliser (URL, alias, ou token)
        
    Returns:
        URL HTTPS normalisée ou None si invalide/vide
        
    Examples:
        >>> normalize_make_webhook_url("https://hook.eu2.make.com/abc123")
        "https://hook.eu2.make.com/abc123"
        >>> normalize_make_webhook_url("abc123@hook.eu2.make.com")
        "https://hook.eu2.make.com/abc123"
        >>> normalize_make_webhook_url("abc123")
        "https://hook.eu2.make.com/abc123"
        >>> normalize_make_webhook_url(None)
        None
    """
    if not value:
        return None
    
    v = value.strip()
    if not v:
        return None
    
    # Si déjà une URL complète, retourner telle quelle
    if v.startswith("http://") or v.startswith("https://"):
        return v
    
    # Format alias: token@hook.eu2.make.com
    if "@hook.eu2.make.com" in v:
        token = v.split("@", 1)[0].strip()
        if token:
            return f"https://hook.eu2.make.com/{token}"
    
    # Si c'est juste un token (pas de slash, espace, ni @)
    if "/" not in v and " " not in v and "@" not in v:
        return f"https://hook.eu2.make.com/{v}"
    
    # Format non reconnu
    return None
