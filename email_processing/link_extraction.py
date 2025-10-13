"""
email_processing.link_extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extraction des liens de fournisseurs (Dropbox, FromSmash, SwissTransfer)
depuis un texte d'email.

Cette extraction réutilise le regex `URL_PROVIDERS_PATTERN` défini dans
`email_processing.pattern_matching` et le helper `detect_provider()` de
`utils.text_helpers`.
"""
from __future__ import annotations

from typing import List, Dict

from email_processing.pattern_matching import URL_PROVIDERS_PATTERN
from utils.text_helpers import detect_provider as _detect_provider


def extract_provider_links_from_text(text: str) -> List[Dict]:
    """Extrait toutes les URLs supportées présentes dans un texte.

    Args:
        text: Chaîne source (plain + HTML brut possible)

    Returns:
        Liste de dicts {"provider": str, "raw_url": str}
    """
    results: List[Dict] = []
    if not text:
        return results

    for m in URL_PROVIDERS_PATTERN.finditer(text):
        raw = m.group(1)
        provider = _detect_provider(raw)
        if provider:
            results.append({"provider": provider, "raw_url": raw})
    return results
