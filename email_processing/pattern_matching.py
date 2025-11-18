"""
email_processing.pattern_matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Détection de patterns dans les emails pour trigger des webhooks spécifiques.
Gère les patterns Média Solution et DESABO.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict

from utils.text_helpers import normalize_no_accents_lower_trim


# =============================================================================
# CONSTANTES - PATTERNS URL PROVIDERS
# =============================================================================

# Compiled regex pattern pour détecter les URLs de fournisseurs supportés:
# - Dropbox folder links
# - FromSmash share links
# - SwissTransfer download links
URL_PROVIDERS_PATTERN = re.compile(
    r'(https?://(?:www\.)?(?:dropbox\.com|fromsmash\.com|swisstransfer\.com)[^\s<>\"]*)',
    re.IGNORECASE,
)

# =============================================================================
# CONSTANTES - DESABO PATTERN
# =============================================================================

# Mots-clés requis pour la détection DESABO (présents dans le corps normalisé)
DESABO_REQUIRED_KEYWORDS = ["journee", "tarifs habituels", "desabonn"]

# Mots-clés interdits qui invalident la détection DESABO
DESABO_FORBIDDEN_KEYWORDS = [
    "annulation",
    "facturation",
    "facture",
    "moment",
    "reference client",
    "total ht",
]


# =============================================================================
# PATTERN MÉDIA SOLUTION
# =============================================================================

def check_media_solution_pattern(subject, email_content, tz_for_polling, logger) -> Dict[str, Any]:
    """
    Vérifie si l'email correspond au pattern Média Solution spécifique et extrait la fenêtre de livraison.

    Conditions minimales:
    1. Contenu contient: "https://www.dropbox.com/scl/fo"
    2. Sujet contient: "Média Solution - Missions Recadrage - Lot"

    Détails d'extraction pour delivery_time:
    - Pattern A (heure seule): "à faire pour" suivi d'une heure (variantes supportées):
      * 11h51, 9h, 09h, 9:00, 09:5, 9h5 -> normalisé en "HHhMM"
    - Pattern B (date + heure): "à faire pour le D/M/YYYY à HhMM?" ou "à faire pour le D/M/YYYY à H:MM"
      * exemples: "le 03/09/2025 à 09h00", "le 3/9/2025 à 9h", "le 3/9/2025 à 9:05"
      * normalisé en "le dd/mm/YYYY à HHhMM"
    - Cas URGENCE: si le sujet contient "URGENCE", on ignore tout horaire présent dans le corps
      et on met l'heure locale actuelle + 1h au format "HHhMM" (ex: "13h35").

    Args:
        subject: Sujet de l'email
        email_content: Contenu/corps de l'email
        tz_for_polling: Timezone pour le calcul des heures (depuis config.polling_config)
        logger: Logger Flask (app.logger)

    Returns:
        dict avec 'matches' (bool) et 'delivery_time' (str ou None)
    """
    result = {'matches': False, 'delivery_time': None}

    if not subject or not email_content:
        return result

    # Helpers de normalisation de texte (sans accents, en minuscule) pour des regex robustes
    def normalize_text(s: str) -> str:
        if not s:
            return ""
        # Supprime les accents et met en minuscule pour une comparaison robuste
        nfkd = unicodedata.normalize('NFD', s)
        no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
        return no_accents.lower()

    norm_subject = normalize_text(subject)

    # Conditions principales
    # 1) Présence d'au moins un lien de fournisseur supporté (Dropbox, FromSmash, SwissTransfer)
    body_text = email_content or ""
    condition1 = bool(URL_PROVIDERS_PATTERN.search(body_text)) or (
        ("dropbox.com/scl/fo" in body_text)
        or ("fromsmash.com/" in body_text.lower())
        or ("swisstransfer.com/d/" in body_text.lower())
    )
    # 2) Sujet conforme
    #    Tolérant: on accepte la chaîne exacte (avec accents) OU la présence des mots-clés dans le sujet normalisé
    keywords_ok = all(token in norm_subject for token in [
        "media solution", "missions recadrage", "lot"
    ])
    condition2 = ("Média Solution - Missions Recadrage - Lot" in (subject or "")) or keywords_ok

    # Si conditions principales non remplies, on sort
    if not (condition1 and condition2):
        logger.debug(
            f"PATTERN_CHECK: Delivery URL present (dropbox/fromsmash/swisstransfer): {condition1}, Subject pattern: {condition2}"
        )
        return result

    # --- Helpers de normalisation ---
    def normalize_hhmm(hh_str: str, mm_str: str | None) -> str:
        """Normalise heures/minutes en "HHhMM". Minutes par défaut à 00."""
        try:
            hh = int(hh_str)
        except Exception:
            hh = 0
        if not mm_str:
            mm = 0
        else:
            try:
                mm = int(mm_str)
            except Exception:
                mm = 0
        return f"{hh:02d}h{mm:02d}"

    def normalize_date(d_str: str, m_str: str, y_str: str) -> str:
        """Normalise D/M/YYYY en dd/mm/YYYY (zero-pad jour/mois)."""
        try:
            d = int(d_str)
            m = int(m_str)
            y = int(y_str)
        except Exception:
            return f"{d_str}/{m_str}/{y_str}"
        return f"{d:02d}/{m:02d}/{y:04d}"

    # --- Extraction de delivery_time ---
    delivery_time_str = None

    # 1) URGENCE: si le sujet contient "URGENCE", on ignore tout horaire présent dans le corps
    if re.search(r"\burgence\b", norm_subject or ""):
        try:
            now_local = datetime.now(tz_for_polling)
            one_hour_later = now_local + timedelta(hours=1)
            delivery_time_str = f"{one_hour_later.hour:02d}h{one_hour_later.minute:02d}"
            logger.info(f"PATTERN_MATCH: URGENCE detected, overriding delivery_time with now+1h: {delivery_time_str}")
        except Exception as e_time:
            logger.error(f"PATTERN_CHECK: Failed to compute URGENCE override time: {e_time}")
    else:
        # 2) Pattern B: Date + Heure (variantes)
        #    Variante "h" -> minutes optionnelles
        pattern_date_time_h = r"(?:à|a)\s+faire\s+pour\s+le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(?:(?:à|a)\s+)?(\d{1,2})h(\d{0,2})"
        m_dth = re.search(pattern_date_time_h, email_content or "", re.IGNORECASE)
        if m_dth:
            d, m, y, hh, mm = m_dth.group(1), m_dth.group(2), m_dth.group(3), m_dth.group(4), m_dth.group(5)
            date_norm = normalize_date(d, m, y)
            time_norm = normalize_hhmm(hh, mm if mm else None)
            delivery_time_str = f"le {date_norm} à {time_norm}"
            logger.info(f"PATTERN_MATCH: Found date+time (h) delivery window: {delivery_time_str}")
        else:
            #    Variante ":" -> minutes obligatoires
            pattern_date_time_colon = r"(?:à|a)\s+faire\s+pour\s+le\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+(?:à|a)\s+(?:(?:à|a)\s+)?(\d{1,2}):(\d{2})"
            m_dtc = re.search(pattern_date_time_colon, email_content or "", re.IGNORECASE)
            if m_dtc:
                d, m, y, hh, mm = m_dtc.group(1), m_dtc.group(2), m_dtc.group(3), m_dtc.group(4), m_dtc.group(5)
                date_norm = normalize_date(d, m, y)
                time_norm = normalize_hhmm(hh, mm)
                delivery_time_str = f"le {date_norm} à {time_norm}"
                logger.info(f"PATTERN_MATCH: Found date+time (colon) delivery window: {delivery_time_str}")

        # 3) Pattern A: Heure seule (variantes)
        if not delivery_time_str:
            # Variante "h" (minutes optionnelles), avec éventuel "à" superflu
            pattern_time_h = r"(?:à|a)\s+faire\s+pour\s+(?:(?:à|a)\s+)?(\d{1,2})h(\d{0,2})"
            m_th = re.search(pattern_time_h, email_content or "", re.IGNORECASE)
            if m_th:
                hh, mm = m_th.group(1), m_th.group(2)
                delivery_time_str = normalize_hhmm(hh, mm if mm else None)
                logger.info(f"PATTERN_MATCH: Found time-only (h) delivery window: {delivery_time_str}")
            else:
                # Variante ":" (minutes obligatoires)
                pattern_time_colon = r"(?:à|a)\s+faire\s+pour\s+(?:(?:à|a)\s+)?(\d{1,2}):(\d{2})"
                m_tc = re.search(pattern_time_colon, email_content or "", re.IGNORECASE)
                if m_tc:
                    hh, mm = m_tc.group(1), m_tc.group(2)
                    delivery_time_str = normalize_hhmm(hh, mm)
                    logger.info(f"PATTERN_MATCH: Found time-only (colon) delivery window: {delivery_time_str}")

        # 4) Fallback permissif: si toujours rien trouvé, tenter une heure isolée (sécurité: restreint aux formats attendus)
        if not delivery_time_str:
            m_fallback_h = re.search(r"\b(\d{1,2})h(\d{0,2})\b", email_content or "", re.IGNORECASE)
            if m_fallback_h:
                hh, mm = m_fallback_h.group(1), m_fallback_h.group(2)
                delivery_time_str = normalize_hhmm(hh, mm if mm else None)
                logger.info(f"PATTERN_MATCH: Fallback time (h) detected: {delivery_time_str}")
            else:
                m_fallback_colon = re.search(r"\b(\d{1,2}):(\d{2})\b", email_content or "")
                if m_fallback_colon:
                    hh, mm = m_fallback_colon.group(1), m_fallback_colon.group(2)
                    delivery_time_str = normalize_hhmm(hh, mm)
                    logger.info(f"PATTERN_MATCH: Fallback time (colon) detected: {delivery_time_str}")

    if delivery_time_str:
        result['delivery_time'] = delivery_time_str
        result['matches'] = True
        logger.info(
            f"PATTERN_MATCH: Email matches Média Solution pattern. Delivery time: {result['delivery_time']}"
        )
    else:
        logger.debug("PATTERN_CHECK: Base conditions met but no delivery_time pattern matched")

    return result


def check_desabo_conditions(subject: str, email_content: str, logger) -> Dict[str, Any]:
    """Vérifie les conditions du pattern DESABO.

    Ce helper externalise la logique de détection « Se désabonner / journée / tarifs habituels »
    actuellement intégrée dans `check_new_emails_and_trigger_webhook()` de `app_render.py`.

    Critères:
    - required_terms tous présents dans le corps normalisé sans accents
    - forbidden_terms absents
    - présence d'une URL Dropbox de type "/request/"

    Args:
        subject: Sujet de l'email (non utilisé pour la détection de base, conservé pour évolutions)
        email_content: Contenu de l'email (texte combiné recommandé: plain + HTML brut)
        logger: Logger pour traces de debug

    Returns:
        dict: { 'matches': bool, 'has_dropbox_request': bool, 'is_urgent': bool }
    """
    result = {"matches": False, "has_dropbox_request": False, "is_urgent": False}

    try:
        norm_body = normalize_no_accents_lower_trim(email_content or "")
        norm_subject = normalize_no_accents_lower_trim(subject or "")

        # 1) Détection du lien Dropbox Request dans le contenu d'entrée (DOIT être calculé en premier)
        has_dropbox_request = "https://www.dropbox.com/request/" in (email_content or "").lower()
        result["has_dropbox_request"] = has_dropbox_request

        # 2) Règles de détection: mots-clés dans le corps + mention de désabonnement
        has_journee = "journee" in norm_body
        has_tarifs = "tarifs habituels" in norm_body
        has_desabo = ("desabonn" in norm_body) or ("desabonn" in norm_subject)
        
        # 3) Détection URGENCE: mot-clé dans le sujet ou le corps normalisés
        is_urgent = ("urgent" in norm_subject) or ("urgence" in norm_subject) or ("urgent" in norm_body) or ("urgence" in norm_body)
        result["is_urgent"] = bool(is_urgent)

        # 4) Règle relaxée: allow match if (journee AND tarifs) AND (explicit desabo OR dropbox request link present)
        has_required = (has_journee and has_tarifs) and (has_desabo or has_dropbox_request)
        has_forbidden = any(term in norm_body for term in DESABO_FORBIDDEN_KEYWORDS)

        # Logs de diagnostic concis (ne doivent jamais lever)
        try:
            # Construction des listes de diagnostic avec les constantes du module
            required_for_diagnostic = ["journee", "tarifs habituels"]
            missing_required = [t for t in required_for_diagnostic if t not in norm_body]
            present_forbidden = [t for t in DESABO_FORBIDDEN_KEYWORDS if t in norm_body]
            logger.debug(
                "DESABO_HELPER_DEBUG: required_ok=%s, forbidden_present=%s, dropbox_request=%s, urgent=%s, missing_required=%s, present_forbidden=%s",
                has_required,
                has_forbidden,
                has_dropbox_request,
                is_urgent,
                missing_required,
                present_forbidden,
            )
        except Exception:
            pass

        # Match if required conditions satisfied and no forbidden terms
        result["matches"] = bool(has_required and (not has_forbidden))
        return result
    except Exception as e:
        try:
            logger.error("DESABO_HELPER: Exception during detection: %s", e)
        except Exception:
            pass
        return result
