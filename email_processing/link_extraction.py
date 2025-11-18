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

from typing import List
from typing_extensions import TypedDict

from email_processing.pattern_matching import URL_PROVIDERS_PATTERN
from utils.text_helpers import detect_provider as _detect_provider


class ProviderLink(TypedDict):
    """Structure d'un lien de fournisseur extrait d'un email."""
    provider: str
    raw_url: str


def extract_provider_links_from_text(text: str) -> List[ProviderLink]:
    """Extrait toutes les URLs supportées présentes dans un texte.

    Les URLs sont dédupliquées tout en préservant l'ordre d'apparition.
    Normalisation appliquée: strip() des URLs avant déduplication.

    Args:
        text: Chaîne source (plain + HTML brut possible)

    Returns:
        Liste de dicts {"provider": str, "raw_url": str}
    """
    results: List[ProviderLink] = []
    if not text:
        return results

    seen_urls = set()
    for m in URL_PROVIDERS_PATTERN.finditer(text):
        raw = m.group(1).strip()
        if not raw:
            continue
        
        provider = _detect_provider(raw)
        if not provider:
            continue
            
        # Déduplication: garder la première occurrence de chaque URL
        if raw not in seen_urls:
            seen_urls.add(raw)
            results.append({"provider": provider, "raw_url": raw})
    
    return results
