# Patterns de Détection Gmail Push

## Overview

Ce document décrit les patterns de détection et les règles de traitement appliqués par l'endpoint Gmail Push (`POST /api/ingress/gmail`) pour classifier et router les emails entrants.

## Architecture des Patterns

### Flux de Traitement

```mermaid
flowchart TD
    A[Email Apps Script] --> B[/api/ingress/gmail]
    B --> C[Validation Payload]
    C --> D[Sender Allowlist]
    D --> E[Pattern Matching]
    E --> F[Routing Rules]
    F --> G[Time Window Check]
    G --> H[Webhook Delivery]
    
    E --> I[Media Solution]
    E --> J[DESABO]
    E --> K[Default]
```

## Patterns Media Solution

### Détection des Fournisseurs

#### Dropbox
- **Pattern principal** : `https://www\.dropbox\.com/(scl/)?[a-zA-Z0-9/_-]+`
- **Variants** :
  - Dossiers partagés : `/scl/fo/` (timeout 120s)
  - Fichiers simples : `/s/` (timeout 30s)
- **Validation** : Magic bytes ZIP pour les dossiers

#### FromSmash
- **Pattern** : `https://fromsmash\.com/[a-zA-Z0-9]+`
- **Timeout** : 30s par défaut
- **Validation** : Taille minimale 1KB

#### SwissTransfer
- **Pattern** : `https://www\.swisstransfer\.com/[a-zA-Z0-9]+`
- **Timeout** : 30s par défaut
- **Validation** : Taille minimale 1KB

### Extraction des Liens

```python
def extract_provider_links_from_text(text: str) -> List[Dict[str, str]]:
    """
    Extrait les liens des fournisseurs supportés du texte.
    Retourne une liste de dictionnaires avec provider, raw_url.
    """
```

### Enrichissement R2

Les liens détectés sont automatiquement enrichis avec R2 si activé :

```python
# Avant enrichissement
{"provider": "dropbox", "raw_url": "https://www.dropbox.com/..."}

# Après enrichissement réussi
{
    "provider": "dropbox", 
    "raw_url": "https://www.dropbox.com/...",
    "r2_url": "https://r2-url...",
    "original_filename": "document.pdf"
}
```

## Patterns DESABO

### Mots-clés d'Urgence

#### Détection Automatique
- **Keywords** : `urgent`, `urgence`
- **Contexte** : Sujet ET corps de l'email
- **Case-insensitive** : `re.search(r'\b(urgent|urgence)\b', text, re.IGNORECASE)`

#### Impact sur le Traitement
- **Urgent** : Respect strict de la fenêtre horaire (pas de bypass)
- **Non urgent** : Bypass autorisé hors fenêtre horaire

### Patterns de Désabonnement

#### Sujets Caractéristiques
- **Confirmation** : "confirmation désabonnement", "votre désabonnement"
- **Information** : "information désabonnement", "mise à jour désabonnement"
- **Urgence** : "désabonnement urgent", "urgence désabonnement"

#### Corps du Message
- **Liens de confirmation** : URLs de désabonnement
- **Références** : Numéros de compte, identifiants client
- **Coordonnées** : Email, téléphone pour contact

## Règles de Routage Dynamique

### Évaluation Séquentielle

```python
def _find_matching_routing_rule(email_data: ParsedEmail) -> Optional[Dict]:
    """
    Évalue les règles dans l'ordre, retourne la première correspondance.
    Support du flag stop_processing pour arrêter l'évaluation.
    """
```

### Conditions Supportées

#### Par Sujet
- **Regex** : `subject.matches("pattern")`
- **Contains** : `subject.contains("keyword")`
- **Starts/Ends** : `subject.starts_with("prefix")`

#### Par Expéditeur
- **Domain** : `sender.domain == "example.com"`
- **Email exact** : `sender.email == "specific@example.com"`

#### Par Contenu
- **Body contains** : `body.contains("keyword")`
- **Has links** : `has_provider_links()`

#### Par Métadonnées
- **Urgence** : `is_urgent == true`
- **Fournisseurs** : `has_provider("dropbox")`

### Actions Possibles

#### Webhook Personnalisé
- **URL** : `webhook_url: "https://custom.webhook.com"`
- **Headers** : `headers: {"Authorization": "Bearer token"}`
- **Stop processing** : `stop_processing: true`

## Fenêtres Horaires

### Configuration

```python
# Variables d'environnement
WEBHOOK_TIME_START="12:00"
WEBHOOK_TIME_END="18:00"

# Configuration globale
global_webhook_time_window = {
    "start": "09:00",
    "end": "17:00",
    "timezone": "Europe/Paris"
}
```

### Règles par Type

#### Media Solution
- **Hors fenêtre** : Skip + marquage traité
- **Dans fenêtre** : Traitement normal + webhook

#### DESABO Urgent
- **Hors fenêtre** : Skip (pas de bypass)
- **Dans fenêtre** : Traitement normal + webhook

#### DESABO Non Urgent
- **Hors fenêtre** : Bypass + envoi immédiat
- **Dans fenêtre** : Traitement normal + webhook

## Validation et Sécurité

### Sender Allowlist

```python
GMAIL_SENDER_ALLOWLIST = [
    "notification@service.com",
    "noreply@provider.com",
    # ... autres expéditeurs autorisés
]
```

### Validation Payload

#### Champs Obligatoires
```json
{
    "subject": "string",
    "sender": "string",
    "body": "string",
    "date": "ISO8601"
}
```

#### Validation Format
- **Email sender** : Regex RFC 5322
- **Date** : Format ISO8601 avec timezone
- **Taille maximale** : 10MB par email

### Authentification

#### Bearer Token
```python
def verify_api_key_from_request(request) -> bool:
    """
    Vérifie le header Authorization: Bearer <PROCESS_API_TOKEN>
    """
```

## Logging Structuré

### Messages Clés

```python
# Succès
"GMAIL_PUSH: Successfully processed email from {sender}"

# Skip règles
"GMAIL_PUSH: Skipped email - sender not in allowlist: {sender}"
"GMAIL_PUSH: Skipped email - outside time window: {sender}"

# Erreurs
"GMAIL_PUSH: Invalid payload - missing required field: {field}"
"GMAIL_PUSH: Pattern matching error: {error}"
```

### Niveaux de Log
- **INFO** : Traitement normal, succès
- **WARNING** : Skip volontaire (allowlist, time window)
- **ERROR** : Erreur de validation, traitement échoué

## Tests et Validation

### Tests Unitaires

#### Pattern Matching
```python
def test_extract_dropbox_links():
    text = "Voici le lien : https://www.dropbox.com/s/abc123/document.pdf"
    links = extract_provider_links_from_text(text)
    assert len(links) == 1
    assert links[0]["provider"] == "dropbox"
```

#### DESABO Detection
```python
def test_desabo_urgent_detection():
    subject = "URGENT - Désabonnement requis"
    assert is_urgent_desabo(subject, "") == True
```

### Tests d'Intégration

#### End-to-End Gmail Push
```python
def test_gmail_push_flow():
    payload = {
        "subject": "Nouveau document partagé",
        "sender": "notification@dropbox.com",
        "body": "Lien: https://www.dropbox.com/s/abc123/file.pdf",
        "date": "2026-02-04T10:30:00Z"
    }
    response = client.post("/api/ingress/gmail", 
                          json=payload,
                          headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
```

## Performance

### Timeout par Fournisseur
- **Dropbox /scl/fo/** : 120s
- **Autres fournisseurs** : 30s
- **Gmail Push global** : 60s

### Optimisations
- **Regex compilées** : `re.compile()` au démarrage
- **Cache patterns** : Mise en cache des résultats de parsing
- **Async R2** : Offload R2 non bloquant

## Monitoring

### Métriques
- **Taux de détection** par fournisseur
- **Temps moyen de traitement**
- **Erreurs par type**
- **Volume par pattern**

### Alertes
- **Taux d'échec** > 5%
- **Timeout** > 30s
- **Payload invalide** > 10%

---

*Dernière mise à jour : 2026-02-04*
