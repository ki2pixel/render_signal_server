"""
utils.text_helpers
~~~~~~~~~~~~~~~~~~

Fonctions utilitaires pour le traitement et la normalisation de texte.
Utilisées pour le parsing des emails, la déduplication par sujet,
et l'extraction d'informations.

Usage:
    from utils.text_helpers import normalize_no_accents_lower_trim
    
    normalized = normalize_no_accents_lower_trim("Média Solution - Lot 42")
    # => "media solution - lot 42"
"""

import hashlib
import re
import unicodedata
from typing import Optional


def normalize_no_accents_lower_trim(s: str) -> str:
    """
    Normalise une chaîne en retirant les accents, en minusculant,
    en collapsant les espaces multiples et en trimant.
    
    Utilisé pour comparer des sujets d'emails de manière robuste
    (insensible à la casse, aux accents, et aux espaces).
    
    Args:
        s: Chaîne à normaliser
        
    Returns:
        Chaîne normalisée (minuscule, sans accents, espaces normalisés)
        
    Examples:
        >>> normalize_no_accents_lower_trim("  Média  Solution  ")
        "media solution"
        >>> normalize_no_accents_lower_trim("Été 2024")
        "ete 2024"
    """
    if not s:
        return ""
    # Décomposition NFD pour séparer les caractères de base des diacritiques
    nfkd = unicodedata.normalize('NFD', s)
    # Filtrer les caractères combinatoires (accents)
    no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
    lowered = no_accents.lower()
    # Collapser les espaces multiples (y compris espaces unicode)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def strip_leading_reply_prefixes(subject: Optional[str]) -> str:
    """
    Retire les préfixes de réponse/transfert en début de sujet.
    
    Préfixes supportés (insensibles à la casse): re:, fw:, fwd:, rv:, tr:, confirmation:
    La suppression est répétée jusqu'à ce qu'aucun préfixe ne reste. L'entrée n'a PAS
    besoin d'être pré-normalisée; la casse et les accents du reste du sujet sont préservés.
    
    Args:
        subject: Sujet (peut être None)
        
    Returns:
        Sujet sans préfixes de réponse/transfert (chaîne vide si entrée falsy)
        
    Examples:
        >>> strip_leading_reply_prefixes("Re: Fw: Test Subject")
        "Test Subject"
        >>> strip_leading_reply_prefixes("confirmation : Lot 42")
        "Lot 42"
    """
    if not subject:
        return ""
    s = subject
    # Préfixes courants à retirer, insensibles à la casse
    pattern = re.compile(r"^(?:(?:re|fw|fwd|rv|tr)\s*:\s*|confirmation\s*:\s*)", re.IGNORECASE)
    while True:
        new_s = pattern.sub("", s, count=1)
        if new_s == s:
            break
        s = new_s
    return s.strip()


def detect_provider(url: str) -> Optional[str]:
    """
    Détecte le fournisseur de partage de fichiers à partir d'une URL.
    
    Fournisseurs supportés:
    - dropbox
    - fromsmash
    - swisstransfer
    
    Args:
        url: URL à analyser
        
    Returns:
        Nom du fournisseur en minuscules ou None si non reconnu
        
    Examples:
        >>> detect_provider("https://www.dropbox.com/scl/fo/abc123")
        "dropbox"
        >>> detect_provider("https://fromsmash.com/xyz789")
        "fromsmash"
        >>> detect_provider("https://www.swisstransfer.com/d/abc-def")
        "swisstransfer"
        >>> detect_provider("https://example.com")
        None
    """
    if not url:
        return "unknown"
    url_lower = url.lower()
    if "dropbox.com" in url_lower:
        return "dropbox"
    if "fromsmash.com" in url_lower:
        return "fromsmash"
    if "swisstransfer.com" in url_lower:
        return "swisstransfer"
    return "unknown"


def mask_sensitive_data(text: str, type: str = "email") -> str:
    if not text:
        if type == "content":
            return "Content length: 0 chars"
        return ""

    value = str(text).strip()
    t = (type or "").strip().lower()

    if t == "email":
        if "@" not in value:
            return "***"
        local, sep, domain = value.partition("@")
        if not sep or not local or not domain:
            return "***"
        return f"{local[0]}***@{domain}"

    if t == "subject":
        words = re.findall(r"\S+", value)
        prefix = " ".join(words[:3]).strip()
        short_hash = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:6]
        if not prefix:
            prefix = "(empty)"
        return f"{prefix}... [{short_hash}]"

    if t == "content":
        return f"Content length: {len(value)} chars"

    return "[redacted]"
