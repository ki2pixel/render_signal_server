# Link Extraction System

**TL;DR**: On extrait automatiquement les liens Dropbox/FromSmash/SwissTransfer des emails avec déduplication intelligente et filtrage des assets non-pertinents, pour préparer l'offload vers R2 sans polluer les webhooks avec des liens d'aperçu.

---

## Le problème : liens parasites dans les emails fournisseurs

J'ai hérité d'un système qui recevait des emails avec des dizaines de liens : les vrais liens de fichiers plus tous les assets d'aperçu (logos, avatars, images miniatures). Le problème ? Les webhooks recevaient du bruit inutile, et l'offload R2 gaspillait des ressources sur des images non-pertinentes.

---

## La solution : extraction intelligente avec filtrage fournisseur

Pensez à l'extraction de liens comme un tri sélectif dans un centre postal : on identifie tous les colis (liens) des transporteurs supportés, on filtre les prospectus publicitaires (assets d'aperçu), on déduplique les doublons, et on garde seulement les vraies livraisons à traiter.

### ❌ L'ancien monde : extraction brute sans filtrage

```python
# ANTI-PATTERN - tous les liens sans distinction
def extract_all_links(text):
    links = re.findall(r'https?://[^\s<>"\']+', text)
    return [{"url": link} for link in links]  # Inclut logos, avatars, etc.
```

### ✅ Le nouveau monde : extraction ciblée avec intelligence fournisseur

```python
# email_processing/link_extraction.py
def extract_provider_links_from_text(text: str) -> List[ProviderLink]:
    results = []
    seen_urls = set()
    
    for match in URL_PROVIDERS_PATTERN.finditer(text):
        raw_url = html.unescape(match.group(1).strip())
        provider = detect_provider(raw_url)
        
        if not provider or _should_skip_provider_url(provider, raw_url):
            continue  # Filtre assets non-pertinents
        
        if raw_url not in seen_urls:  # Déduplication
            seen_urls.add(raw_url)
            results.append({"provider": provider, "raw_url": raw_url})
    
    return results
```

**La révolution** : Regex ciblé + filtrage fournisseur + déduplication propre.

---

## Architecture de l'extraction

### Regex fournisseur robuste

```python
# email_processing/pattern_matching.py
URL_PROVIDERS_PATTERN = re.compile(
    r'(https?://(?:www\.)?(?:dropbox\.com|fromsmash\.com|swisstransfer\.com)[^\s<>\"]*)',
    re.IGNORECASE,
)
```

**Pattern** : Détecte URLs complètes avec sous-domaines optionnels, insensible à la casse.

### Détection fournisseur par domaine

```python
# utils/text_helpers.py
def detect_provider(url: str) -> Optional[str]:
    url_lower = url.lower()
    if "dropbox.com" in url_lower:
        return "dropbox"
    if "fromsmash.com" in url_lower:
        return "fromsmash" 
    if "swisstransfer.com" in url_lower:
        return "swisstransfer"
    return "unknown"
```

### Filtrage intelligent des assets

```python
def _should_skip_provider_url(provider: str, url: str) -> bool:
    if provider != "dropbox":
        return False  # Seuls les Dropbox ont des assets parasites
    
    # Analyse URL Dropbox pour détecter assets d'aperçu
    parts = urlsplit(url)
    path_lower = parts.path.lower()
    filename = path_lower.split("/")[-1]
    
    # Assets d'aperçu: /scl/fi/.../avatar.png?raw=1
    if (path_lower.startswith("/scl/fi/") and 
        "?raw=1" in url and 
        filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))):
        
        # Logos/avatars à filtrer
        logo_prefixes = ("ms", "logo", "avatar", "profile")
        base_name = filename.rsplit(".", 1)[0]
        
        if base_name in logo_prefixes or any(base_name.startswith(p) for p in logo_prefixes):
            return True  # Skip cet asset
    
    return False  # Garder le lien
```

---

## Fournisseurs supportés et patterns

### Dropbox : liens de partage complexes

| Type de lien | Pattern | Exemple | Conservé? |
|--------------|---------|---------|-----------|
| Fichiers simples | `/s/abc123` | `https://dropbox.com/s/abc123/file.pdf` | ✅ Oui |
| Dossiers partagés | `/scl/fo/abc123` | `https://dropbox.com/scl/fo/abc123/` | ✅ Oui |
| Assets aperçu | `/scl/fi/abc123/logo.png?raw=1` | `https://dropbox.com/scl/fi/.../ms.png?raw=1` | ❌ Non |

### FromSmash : liens de partage directs

| Type de lien | Pattern | Exemple | Conservé? |
|--------------|---------|---------|-----------|
| Partage standard | `/share/...` | `https://fromsmash.com/share/xyz789` | ✅ Oui |
| Tous autres liens | N/A | `https://fromsmash.com/other` | ✅ Oui* |

*FromSmash n'a pas d'assets parasites connus actuellement.

### SwissTransfer : téléchargements sécurisés

| Type de lien | Pattern | Exemple | Conservé? |
|--------------|---------|---------|-----------|
| Téléchargement | `/d/abc-def` | `https://swisstransfer.com/d/abc-def` | ✅ Oui |
| Tous autres liens | N/A | `https://swisstransfer.com/other` | ✅ Oui* |

*SwissTransfer n'a pas d'assets parasites connus actuellement.

---

## Déduplication et normalisation

### Déduplication par URL brute

```python
seen_urls = set()
for match in URL_PROVIDERS_PATTERN.finditer(text):
    raw_url = html.unescape(match.group(1).strip())
    
    # Normalisation: unescape HTML entities
    # Ex: "&amp;" → "&", "&lt;" → "<"
    
    if raw_url not in seen_urls:
        seen_urls.add(raw_url)
        results.append({"provider": provider, "raw_url": raw_url})
```

**Règle** : Première occurrence seulement, préserve l'ordre d'apparition.

### Gestion des encodages HTML

```python
# Nettoyage des entités HTML dans les URLs
raw_url = html.unescape(match.group(1).strip())

# Exemples de transformations:
# "https://dropbox.com/s/abc&amp;def" → "https://dropbox.com/s/abc&def"
# "https://fromsmash.com/share&lt;test&gt;" → "https://fromsmash.com/share<test>"
```

---

## Intégration dans le pipeline d'ingestion

### Flux complet : email → extraction → enrichissement → webhook

```python
# routes/api_ingress.py
@bp.route("/gmail", methods=["POST"])
def ingest_gmail():
    # 1. Parsing payload
    payload = request.get_json()
    body = payload.get("body", "")
    
    # 2. Extraction liens fournisseurs
    delivery_links = link_extraction.extract_provider_links_from_text(body)
    
    # 3. Enrichissement R2 si activé
    _maybe_enrich_delivery_links_with_r2(delivery_links, email_id, logger)
    
    # 4. Construction payload webhook avec liens enrichis
    webhook_payload = {
        "microsoft_graph_email_id": email_id,
        "delivery_links": delivery_links,  # Liens extraits + R2
        # ... autres champs
    }
    
    # 5. Envoi webhook
    send_custom_webhook_flow(webhook_payload, ...)
```

### Enrichissement R2 conditionnel

```python
def _maybe_enrich_delivery_links_with_r2(delivery_links, email_id, logger):
    r2_service = R2TransferService.get_instance()
    if not r2_service.is_enabled():
        return  # Pas d'enrichissement si R2 désactivé
    
    for item in delivery_links:
        # Tentative offload vers R2 avec timeout adaptatif
        r2_url, filename = r2_service.request_remote_fetch(
            source_url=item['raw_url'],
            provider=item['provider'], 
            email_id=email_id,
            timeout=120 if 'scl/fo' in item['raw_url'] else 15
        )
        
        if r2_url:
            item['r2_url'] = r2_url
            item['original_filename'] = filename
            # Persistance mapping source→R2...
```

---

## Performance et optimisation

### Métriques d'extraction

- **URLs trouvées** : Nombre total de liens fournisseur détectés
- **URLs filtrées** : Assets non-pertinents écartés
- **Liens uniques** : Après déduplication
- **Temps traitement** : <5ms par email typique

### Optimisations appliquées

```python
# Regex compilé une fois au module level
URL_PROVIDERS_PATTERN = re.compile(...)

# HTML unescape seulement sur les matches
raw_url = html.unescape(match.group(1).strip())

# Déduplication avec set pour O(1) lookups
if raw_url not in seen_urls:
    seen_urls.add(raw_url)
    results.append(item)
```

### Gestion d'erreurs défensive

```python
try:
    raw_url = html.unescape(match.group(1).strip())
except Exception:
    raw_url = match.group(1).strip()  # Fallback sans unescape

try:
    provider = detect_provider(raw_url)
except Exception:
    provider = "unknown"  # Continue sans planter
```

---

## Tests et validation

### Couverture complète d'extraction

```bash
pytest tests/email_processing/test_link_extraction.py -v
# 8 tests couvrant tous les scénarios
```

### Tests représentatifs

```python
def test_dropbox_asset_filtering():
    """Filtre assets aperçu Dropbox mais garde vrais fichiers"""
    email_body = """
    <img src="https://dropbox.com/scl/fi/abc123/logo.png?raw=1">
    <a href="https://dropbox.com/scl/fo/def456/">Dossier partagé</a>
    <a href="https://dropbox.com/s/ghi789/document.pdf">Fichier direct</a>
    """
    
    links = extract_provider_links_from_text(email_body)
    
    # Doit garder seulement les 2 vrais liens de fichiers
    assert len(links) == 2
    assert any("scl/fo/def456" in link["raw_url"] for link in links)
    assert any("s/ghi789/document.pdf" in link["raw_url"] for link in links)

def test_deduplication_preserves_order():
    """Déduplication garde première occurrence"""
    email_body = """
    https://dropbox.com/s/abc123/file.pdf
    https://fromsmash.com/share/xyz789  
    https://dropbox.com/s/abc123/file.pdf (duplicate)
    """
    
    links = extract_provider_links_from_text(email_body)
    
    # Doit avoir 2 liens uniques dans l'ordre d'apparition
    assert len(links) == 2
    assert links[0]["provider"] == "dropbox"
    assert links[1]["provider"] == "fromsmash"
```

---

## Évolutions prévues (Q2 2026)

### Nouveaux fournisseurs

- **WeTransfer** : `wetransfer.com/downloads/...`
- **Mega.nz** : Patterns Mega avec clés de déchiffrement
- **Google Drive** : Liens de partage avec permissions

### Intelligence d'extraction

- **Classification contenu** : Détection type fichier par extension/headers
- **Priorisation liens** : Score de pertinence par contexte
- **Extraction conditionnelle** : Filtres par domaine expéditeur

### Performance avancée

- **Parsing HTML structuré** : Analyse DOM au lieu de regex brut
- **Cache patterns** : Mémorisation des extractions répétitives
- **Extraction parallèle** : Multi-threading pour gros volumes

---

## La Golden Rule : Regex ciblé, filtrage fournisseur, déduplication propre

L'extraction de liens utilise des regex spécifiques aux fournisseurs supportés, filtre intelligemment les assets non-pertinents par heuristiques fournisseur, déduplique les URLs tout en préservant l'ordre, et prépare les données structurées pour l'enrichissement R2.

Liens extraits = bruit filtré = données propres = traitement efficace.
