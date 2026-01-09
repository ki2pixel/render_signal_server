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

import html
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

    def _should_skip_provider_url(provider: str, url: str) -> bool:
        if provider != "dropbox":
            return False
        if not url:
            return False

        # Dropbox peut inclure dans certains emails des assets de preview (ex: avatar/logo).
        # Cas observé: .../scl/fi/.../MS.png?...&raw=1
        try:
            parsed = html.unescape(url)
        except Exception:
            parsed = url

        try:
            from urllib.parse import urlsplit, parse_qs

            parts = urlsplit(parsed)
            host = (parts.hostname or "").lower()
            path = (parts.path or "")
            path_lower = path.lower()
            if not host.endswith("dropbox.com"):
                return False

            filename = path_lower.split("/")[-1]
            if not filename:
                return False

            qs = parse_qs(parts.query or "")
            raw_values = qs.get("raw", [])
            has_raw_one = any(str(v).strip() == "1" for v in raw_values)

            if path_lower.startswith("/scl/fi/") and has_raw_one:
                is_image = filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                if not is_image:
                    return False

                # Heuristique volontairement restrictive pour éviter de filtrer des livrables.
                logo_like_prefixes = ("ms", "logo", "avatar", "profile")
                base = filename.rsplit(".", 1)[0]
                if base in logo_like_prefixes or any(base.startswith(p) for p in logo_like_prefixes):
                    return True

            return False
        except Exception:
            return False

    seen_urls = set()
    for m in URL_PROVIDERS_PATTERN.finditer(text):
        raw = m.group(1).strip()
        try:
            raw = html.unescape(raw)
        except Exception:
            pass
        if not raw:
            continue
        
        provider = _detect_provider(raw)
        if not provider:
            continue

        if _should_skip_provider_url(provider, raw):
            continue
            
        # Déduplication: garder la première occurrence de chaque URL
        if raw not in seen_urls:
            seen_urls.add(raw)
            results.append({"provider": provider, "raw_url": raw})
    
    return results
