# Pattern Matching Engine

**TL;DR**: On détecte automatiquement les emails Média Solution (avec extraction horaire complexe) et DESABO (désabonnement journées/tarifs) pour router vers les bonnes webhooks, avec règles métier strictes et tolérance aux variations de format.

---

## Le problème : la détection manuelle qui ratait des emails importants

J'ai hérité d'un système où les emails "importants" (Média Solution, DESABO) étaient détectés par du code dur dans l'orchestrateur. Le problème ? Chaque variation de format (accents, majuscules, espaces) pouvait faire rater une détection, et l'extraction des horaires était un cauchemar de regex.

---

## La solution : moteur de pattern matching robuste avec extraction intelligente

Pensez au pattern matching comme un scanner de sécurité avec deux modes : le mode "fournisseur de contenu" (Média Solution) qui extrait les horaires de livraison, et le mode "désabonnement" (DESABO) qui détecte les urgences tarifaires. Le système normalise les textes, applique des regex tolérantes, et gère les cas limites.

### ❌ L'ancien monde : détection codée en dur, fragile aux variations

```python
# ANTI-PATTERN - code dur dans orchestrator
def detect_patterns(subject, body):
    if "Média Solution" in subject and "dropbox.com" in body:
        # Extraction horaire manuelle...
        return "recadrage"
    elif "désabonnement" in subject and "journée" in body:
        return "desabo"
    return None
```

### ✅ Le nouveau monde : pattern matching normalisé et extensible

```python
# email_processing/pattern_matching.py
def check_media_solution_pattern(subject, email_content, tz, logger):
    # Normalisation robuste sans accents
    norm_subject = normalize_text(subject)
    
    # Conditions métier précises
    has_provider_url = URL_PROVIDERS_PATTERN.search(email_content)
    has_subject_keywords = all(token in norm_subject for token in [
        "media solution", "missions recadrage", "lot"
    ])
    
    if has_provider_url and has_subject_keywords:
        delivery_time = extract_delivery_time(email_content, tz)
        return {"matches": True, "delivery_time": delivery_time}
    return {"matches": False}
```

**La révolution** : normalisation → règles métier claires → extraction intelligente.

---

## Patterns métier supportés

### Média Solution : livraison de contenu avec horaires

**Détection** : Sujet + URL fournisseur + extraction horaire complexe.

#### Conditions de matching

```python
# Conditions minimales (ET logique)
condition1 = bool(URL_PROVIDERS_PATTERN.search(body_text)) or (
    "dropbox.com/scl/fo" in body_text or
    "fromsmash.com/" in body_text or  
    "swisstransfer.com/d/" in body_text
)

condition2 = ("Média Solution - Missions Recadrage - Lot" in subject) or all(
    token in normalize_text(subject) for token in [
        "media solution", "missions recadrage", "lot"
    ]
)
```

#### Fournisseurs supportés

| Fournisseur | Pattern URL | Timeout R2 |
|-------------|-------------|------------|
| Dropbox | `https://www.dropbox.com/scl/fo/...` | 120s (dossiers) |
| FromSmash | `https://fromsmash.com/...` | 30s |
| SwissTransfer | `https://swisstransfer.com/d/...` | 15s |

#### Extraction horaire : 4 niveaux de priorité

```python
# 1. URGENCE : override tout horaire existant
if "urgence" in normalize_text(subject):
    delivery_time = (now + 1h).strftime("%Hh%M")
    return f"{delivery_time}"  # ex: "14h35"

# 2. Date + heure complète
# Pattern: "à faire pour le D/M/YYYY à HhMM" ou "à faire pour le D/M/YYYY à H:MM"
matches = re.findall(r"faire pour le (\d{1,2})/(\d{1,2})/(\d{4}) à (\d{1,2})[h:](\d{0,2})")
if matches:
    return f"le {d:02d}/{m:02d}/{y} à {h:02d}h{m:02d}"

# 3. Heure seule (même journée)
# Pattern: "à faire pour HhMM" ou "à faire pour H:MM"
matches = re.findall(r"faire pour (\d{1,2})[h:](\d{0,2})")
if matches:
    return f"{h:02d}h{m:02d}"

# 4. Fallback permissif (dernière chance)
matches = re.findall(r"\b(\d{1,2})[h:](\d{0,2})\b")
if matches:
    return f"{h:02d}h{m:02d}"
```

### DESABO : désabonnement journées/tarifs

**Détection** : Mots-clés requis + absence de mots interdits + lien Dropbox optionnel.

#### Mots-clés requis (ET logique)

```python
DESABO_REQUIRED_KEYWORDS = ["journee", "tarifs habituels", "desabonn"]
```

#### Mots-clés interdits (invalident le match)

```python
DESABO_FORBIDDEN_KEYWORDS = [
    "annulation", "facturation", "facture", 
    "moment", "reference client", "total ht"
]
```

#### Règles de détection

```python
# Normalisation sans accents, minuscules
norm_body = normalize_no_accents_lower_trim(email_content)
norm_subject = normalize_no_accents_lower_trim(subject)

# Conditions
has_required = (
    "journee" in norm_body and 
    "tarifs habituels" in norm_body and
    ("desabonn" in norm_body or "desabonn" in norm_subject)
)

has_forbidden = any(term in norm_body for term in DESABO_FORBIDDEN_KEYWORDS)
has_dropbox_request = "https://www.dropbox.com/request/" in email_content.lower()

# Règle relaxée : (required) AND (NOT forbidden) AND (desabo OR dropbox_request)
matches = has_required and not has_forbidden

# Urgence si "urgent" ou "urgence" dans sujet/corps
is_urgent = "urgent" in norm_subject or "urgence" in norm_subject or \
           "urgent" in norm_body or "urgence" in norm_body
```

---

## Exemples concrets de matching

### Média Solution - Succès

| Email | Matches? | Delivery Time | Raison |
|-------|----------|---------------|--------|
| Sujet: "Média Solution - Missions Recadrage - Lot 123"<br>Body: "... https://www.dropbox.com/scl/fo/abc123 ..." | ✅ | Extraite du corps | Pattern complet + URL |
| Sujet: "media solution missions recadrage lot 456"<br>Body: "... fromsmash.com/share/..." | ✅ | Extraite du corps | Keywords normalisés + URL |
| Sujet: "URGENCE Média Solution Lot 789"<br>Body: "... dropbox.com ..." | ✅ | `now+1h` | Urgence détectée, override horaire |

### Média Solution - Échec

| Email | Matches? | Raison |
|-------|----------|--------|
| Sujet: "Média Solution"<br>Body: "Pas d'URL" | ❌ | Manque URL fournisseur |
| Sujet: "Lot 123"<br>Body: "dropbox.com/scl/fo/..." | ❌ | Manque keywords sujet |
| Sujet: "Media Solution Recadrage"<br>Body: "dropbox.com" | ❌ | "missions" manquant |

### DESABO - Succès

| Email | Matches? | Urgent? | Raison |
|-------|----------|---------|--------|
| Body: "... désabonner journée tarifs habituels ... https://dropbox.com/request/..." | ✅ | Non | Required + Dropbox request |
| Sujet: "URGENT désabonnement"<br>Body: "... journée tarifs habituels ..." | ✅ | Oui | Required + urgence sujet |
| Body: "... désabonnement journée tarifs habituels ..." | ✅ | Non | Required complet |

### DESABO - Échec

| Email | Matches? | Raison |
|-------|----------|--------|
| Body: "... désabonner tarifs habituels ..." | ❌ | "journée" manquant |
| Body: "... désabonnement journée tarifs habituels facture ..." | ❌ | Mot interdit "facture" |
| Body: "... journée tarifs habituels ..." | ❌ | "désabonn" manquant |

---

## Robustesse et tolérance

### Normalisation texte : gestion des variations

```python
def normalize_text(text: str) -> str:
    """Supprime accents, met en minuscule, robuste aux variations."""
    nfkd = unicodedata.normalize('NFD', text)
    no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
    return no_accents.lower()

# Exemples de robustesse
"Équipe" → "equipe"
"MÉDIA" → "media" 
"Désabonner" → "desabonner"
```

### Regex tolérantes : gestion des formats variables

```python
# Heures flexibles : accepte "9h", "09h", "9:00", "09:05"
pattern_time = r"(\d{1,2})[h:](\d{0,2})"

# Dates flexibles : accepte "3/9/2025" ou "03/09/2025" 
pattern_date = r"(\d{1,2})/(\d{1,2})/(\d{4})"

# URLs : case-insensitive, sous-domaines optionnels
URL_PROVIDERS_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:dropbox|fromsmash|swisstransfer)\.com[^\s<>"\']*',
    re.IGNORECASE
)
```

### Gestion d'erreurs : jamais de crash

```python
def safe_pattern_check(subject, body, logger):
    try:
        # Toute la logique de matching
        return check_patterns(subject, body)
    except Exception as e:
        logger.error(f"PATTERN_CHECK: Exception during matching: {e}")
        return {"matches": False}  # Safe default
```

---

## Intégration dans l'orchestrateur

### Flux de décision : pattern → routing

```python
# email_processing/orchestrator.py (MÉTHODE LEGACY IMAP)
def check_new_emails_and_trigger_webhook(email_data):
    # 1. Pattern matching
    ms_result = pattern_matching.check_media_solution_pattern(
        email_data['subject'], email_data['body'], tz, logger
    )
    if ms_result['matches']:
        detector = "recadrage"
        delivery_time = ms_result['delivery_time']
    
    desabo_result = pattern_matching.check_desabo_conditions(
        email_data['subject'], email_data['body'], logger
    )
    if desabo_result['matches']:
        detector = "desabonnement_journee_tarifs"
        is_urgent = desabo_result['is_urgent']
    
    # 2. Routing basé sur le pattern détecté
    if detector:
        return route_by_detector(detector, delivery_time, is_urgent, email_data)
    
    # 3. Fallback routing normal
    return route_by_default(email_data)
```

### ✅ Méthode actuelle : Gmail Push Integration

```python
# routes/api_ingress.py (MÉTHODE ACTUELLE GMAIL PUSH)
@bp.route("/gmail", methods=["POST"])
def ingest_gmail():
    # Pattern matching dans le flux Gmail Push
    pattern_result = pattern_matching.check_media_solution_pattern(payload['subject'], payload['body'])
    is_desabo = pattern_matching.check_desabo_pattern(payload['subject'], payload['body'])
    
    # Routing et webhook dans le même appel
    return send_custom_webhook_flow(payload)
```

**Note** : `check_new_emails_and_trigger_webhook` est la méthode legacy IMAP. Pour la méthode actuelle Gmail Push, voir [docs/ingestion/gmail-push.md](../ingestion/gmail-push.md).

### Enrichissement payload webhook

```python
# Ajout des métadonnées extraites
payload_for_webhook = {
    "detector": detector,  # "recadrage" ou "desabonnement_journee_tarifs"
    "delivery_time": delivery_time,  # ex: "le 03/09/2025 à 14h30"
    "sender_email": sender_email,
    # ... autres champs
}

if detector == "desabonnement_journee_tarifs":
    payload_for_webhook["is_urgent"] = is_urgent
```

---

## Tests et validation

### Couverture des scénarios critiques

```bash
pytest tests/email_processing/test_pattern_matching.py -v
# 12 tests couvrant tous les patterns et edge cases
```

### Tests représentatifs

```python
def test_media_solution_urgence_override():
    """URGENCE doit overrider tout horaire existant"""
    subject = "URGENCE Média Solution Lot 123"
    body = "À faire pour 15h30 https://dropbox.com/scl/fo/abc"
    
    result = check_media_solution_pattern(subject, body, tz, logger)
    
    # Doit matcher ET ignorer l'horaire du corps
    assert result["matches"] == True
    assert result["delivery_time"] == "14h35"  # now + 1h (exemple)

def test_desabo_forbidden_keywords():
    """Mots interdits doivent invalider le match"""
    body = "désabonnement journée tarifs habituels facture"
    
    result = check_desabo_conditions("test", body, logger)
    
    # "facture" présent = pas de match
    assert result["matches"] == False
```

---

## Évolutions prévues (Q2 2026)

### Nouveaux patterns fournisseur

- **WeTransfer** : `wetransfer.com/downloads/`
- **Mega.nz** : Patterns de liens Mega
- **Google Drive** : Liens de partage

### Extraction temporelle améliorée

- **Jours de semaine** : "à faire pour lundi 14h"
- **Expressions relatives** : "dans 2 heures", "demain matin"
- **Timezones multiples** : Conversion automatique

### Pattern learning

- **Machine learning** : Apprentissage des patterns clients
- **Feedback loop** : Validation utilisateur des détections
- **Pattern personnalisés** : Règles spécifiques client

---

## La Golden Rule : Normalisation puis règles métier strictes

Les patterns sont détectés après normalisation robuste (sans accents, case-insensitive), avec règles métier claires (mots requis/interdits), et extraction temporelle priorisée (urgence → date+heure → heure seule → fallback). Chaque détection enrichit le payload webhook avec les métadonnées extraites, permettant un routing intelligent sans jamais casser sur les variations de format.

Pattern match = routing automatique = traitement métier adapté.
