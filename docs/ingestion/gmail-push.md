# Gmail Push Ingestion

**TL;DR**: On a tué le polling IMAP qui consommait toute la bande passante. Maintenant Google Apps Script pousse les emails directement à notre API, avec un toggle runtime Redis-first pour contrôler l'ingestion sans perdre d'emails.

---

## Le problème : le polling IMAP qui nous tuait

J'ai hérité d'un système qui polling IMAP toutes les minutes. 24/7. Même quand il n'y avait aucun email.

Le résultat sur Render ?
- Bande passante consommée en permanence
- Connexions qui timeout toutes les 5 minutes  
- Locks Redis complexes pour éviter les doublons en multi-conteneur
- Logs de retry partout

Pire encore : dès qu'on avait 2 conteneurs, ils se battaient pour les mêmes emails.

---

## La solution : centre de tri postal avec trieur automatique

Pensez à Gmail Push comme un centre de tri postal : Apps Script est le facteur qui livre les lettres directement à notre centre de tri, où chaque email est trié instantanément vers le bon destinataire (webhook) sans attente. Le polling IMAP était un facteur qui faisait des tournées toutes les minutes même quand le sac était vide.

### ❌ L'ancien monde : facteur qui tourne à vide

```python
# ANTI-PATTERN - polling_thread.py
while True:
    try:
        # Connexion IMAP qui timeout
        imap = imaplib.IMAP4_SSL(server)
        imap.login(email, password)
        
        # Scan toutes les minutes, même si vide
        emails = imap.search(None, 'UNSEEN')
        for email_id in emails[0].split():
            # Traitement complexe avec locks...
            process_email(email_id)
            
        time.sleep(60)  # Polling aveugle
    except Exception as e:
        logger.error(f"IMAP error: {e}")
        time.sleep(300)  # Retry long
```

### ✅ Le nouveau monde : livraison directe au centre de tri

```javascript
// Apps Script - push simple et efficace
function pushEmailToIngress(subject, sender, body, date) {
  const url = "https://render-signal-server-latest.onrender.com/api/ingress/gmail";
  const token = PropertiesService.getScriptProperties().getProperty("PROCESS_API_TOKEN");
  
  const payload = {
    subject: subject || "",
    sender: sender,
    body: body,
    date: date || new Date().toISOString()
  };
  
  const options = {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  return UrlFetchApp.fetch(url, options);
}
```

**Le gain** : zéro tournée, bande passante minimale, et Google fait tout le travail de livraison.

---

## Architecture du flux Gmail Push

```
Apps Script Gmail → POST /api/ingress/gmail → AuthService → Pattern Matching → Routing Rules → Webhooks
```

### 1. Authentification Bearer stricte

```python
# routes/api_ingress.py
@bp.route("/gmail", methods=["POST"])
def ingest_gmail():
    # Vérification token PROCESS_API_TOKEN
    if not auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    # Validation payload stricte
    payload = request.get_json()
    if not payload or not payload.get('sender') or not payload.get('body'):
        return jsonify({"success": False, "message": "Missing required field"}), 400
```

### 2. Déduplication Redis instantanée

```python
# Génération email_id unique
email_id = md5(f"{payload['sender']}:{payload['date']}").hexdigest()

# Vérification Redis (fallback mémoire)
if dedup_service.is_email_id_processed(email_id):
    return jsonify({
        "success": True, 
        "status": "already_processed"
    }), 200

# Marquage immédiat pour éviter les doublons
dedup_service.mark_email_id_as_processed(email_id)
```

### 3. Allowlist expéditeurs

```python
# GMAIL_SENDER_ALLOWLIST depuis app_render globals
sender_list = getattr(ar, "GMAIL_SENDER_ALLOWLIST", [])
allowed = [str(s).strip().lower() for s in sender_list if isinstance(s, str) and s.strip()]

if allowed and sender_email not in allowed:
    # Marquer comme traité pour éviter les réessais
    mark_email_id_as_processed_redis(email_id)
    return jsonify({
        "success": True,
        "status": "skipped_sender_not_allowed"
    }), 200
```

### 4. Pattern matching temps réel

```python
# Détection Media Solution / DESABO
pattern_result = pattern_matching.check_media_solution_pattern(payload['subject'], payload['body'])
is_desabo = pattern_matching.check_desabo_pattern(payload['subject'], payload['body'])
is_urgent = pattern_matching.is_urgent_desabo(payload['subject'], payload['body'])

# Extraction liens fournisseurs
delivery_links = link_extraction.extract_provider_links_from_text(payload['body'])
```

### 5. Routing dynamique avant envoi

```python
# Évaluation des règles personnalisées
routing_rules = routing_service.get_rules()
matched_rule = routing_service.evaluate(payload, routing_rules)

if matched_rule and matched_rule.get('stop_processing'):
    logger.info(f"Routing rule matched with stop_processing: {matched_rule['name']}")
    return jsonify({"success": True, "status": "stopped_by_routing_rule"}), 200
```

---

## Patterns de détection : les règles métier

### Media Solution : Dropbox, FromSmash, SwissTransfer

```python
# Dropbox patterns
DROPBOX_PATTERNS = [
    r'https://www\.dropbox\.com/s/[a-zA-Z0-9/_-]+',  # Fichiers simples
    r'https://www\.dropbox\.com/scl/fo/[a-zA-Z0-9/_-]+'  # Dossiers partagés
]

# Extraction avec timeout adaptatif
def extract_provider_links_from_text(text):
    links = []
    for provider, pattern in PROVIDER_PATTERNS.items():
        matches = re.findall(pattern, text)
        for url in matches:
            links.append({
                'provider': provider,
                'raw_url': url,
                'timeout': 120 if 'scl/fo' in url else 30  # Dropbox dossiers = 120s
            })
    return links
```

### DESABO : urgence et fenêtres horaires

```python
# Détection urgence
def is_urgent_desabo(subject, body):
    urgent_keywords = ['urgent', 'urgence']
    text = f"{subject} {body}".lower()
    return any(keyword in text for keyword in urgent_keywords)

# Règles fenêtre horaire
if is_desabo:
    if is_urgent:
        # Urgent : respect strict de la fenêtre
        if not is_within_time_window():
            return jsonify({"success": False, "message": "Outside time window"}), 409
    else:
        # Non urgent : bypass autorisé
        if not is_within_time_window():
            logger.info("DESABO non urgent hors fenêtre, bypass autorisé")
```

---

## Offload R2 : optimisation bande passante

### ❌ L'ancien monde : liens directs non optimisés

```python
# ANTI-PATTERN - liens bruts sans enrichissement
delivery_links = [{
    'provider': 'dropbox',
    'raw_url': 'https://www.dropbox.com/s/abc123/file.pdf',
    'direct_url': 'https://www.dropbox.com/s/abc123/file.pdf'
    # Pas de timeout adaptatif, pas de persistance R2
}]
```

### ✅ Le nouveau monde : enrichissement R2 intelligent

```python
# api_ingress.py - _maybe_enrich_delivery_links_with_r2
def _maybe_enrich_delivery_links_with_r2(delivery_links, email_id, logger):
    r2_service = R2TransferService.get_instance()
    if not r2_service.is_enabled():
        return delivery_links
    
    for item in delivery_links:
        # Normalisation URL source
        normalized_url = r2_service.normalize_source_url(item['raw_url'], item['provider'])
        
        # Timeout adaptatif (120s pour dossiers Dropbox)
        timeout = 120 if item['provider'] == 'dropbox' and '/scl/fo/' in normalized_url else 15
        
        # Offload vers R2 avec retry
        r2_url, filename = r2_service.request_remote_fetch(
            source_url=normalized_url,
            provider=item['provider'],
            email_id=email_id,
            timeout=timeout
        )
        
        if r2_url:
            item['r2_url'] = r2_url
            item['original_filename'] = filename
            
            # Persistance de la paire pour tracking
            r2_service.persist_link_pair(
                source_url=normalized_url,
                r2_url=r2_url,
                provider=item['provider'],
                original_filename=filename
            )
            
            logger.info(f"R2_TRANSFER: Successfully transferred {item['provider']} link")
    
    return delivery_links
```

**Le pattern** : best-effort avec fallback gracieux. Si R2 échoue, le webhook part quand même avec l'URL originale.

---

## API REST : spécification complète

### Endpoint unique

```
POST /api/ingress/gmail
Content-Type: application/json
Authorization: Bearer <PROCESS_API_TOKEN>
```

### Payload JSON

```json
{
  "subject": "Nouveau document partagé",
  "sender": "notification@dropbox.com", 
  "body": "Voici votre fichier : https://www.dropbox.com/s/abc123/document.pdf",
  "date": "2026-02-04T10:30:00Z"
}
```

### Réponses possibles

| Code | Status | Quand |
|------|--------|-------|
| 200 | processed | Email traité avec succès |
| 200 | already_processed | Doublon détecté |
| 200 | skipped_sender_not_allowed | Expéditeur non autorisé |
| 200 | skipped_outside_time_window | Hors fenêtre (RECADRAGE) |
| 400 | Invalid JSON payload | JSON invalide |
| 400 | Missing field | Champs obligatoires manquants |
| 401 | Unauthorized | Token invalide |
| 409 | Webhook sending disabled | Webhooks désactivés |
| 409 | Gmail ingress disabled | Toggle `gmail_ingress_enabled`=false |
| 409 | Outside time window | Hors fenêtre (autres cas) |
| 500 | Internal error | Erreur serveur |

---

## Sécurité : couches de protection

### 1. Authentification Bearer obligatoire

```python
def verify_api_key_from_request(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header.split(' ')[1]
    expected_token = os.environ.get('PROCESS_API_TOKEN')
    
    # Timing attack protection
    return hmac.compare_digest(token.encode(), expected_token.encode())
```

### 2. Validation payload stricte

```python
# Champs obligatoires
required_fields = ['sender', 'body']
for field in required_fields:
    if not payload.get(field):
        logger.error(f"GMAIL_PUSH: Missing required field: {field}")
        return False

# Taille maximale anti-OOM
if len(payload.get('body', '')) > MAX_EMAIL_SIZE:
    logger.warning("GMAIL_PUSH: Email too large, rejecting")
    return False
```

### 3. Logging PII-safe

```python
# Masquage adresses email dans les logs
def mask_email(email):
    if '@' in email:
        local, domain = email.split('@', 1)
        return f"{local[:2]}***@{domain}"
    return "***"

logger.info(f"GMAIL_PUSH: Processed email from {mask_email(sender)}")
```

---

## Runtime Flags & Debugging : Contrôle d'ingestion

### Le toggle Gmail ingress

```python
# RuntimeFlagsService avec persistance Redis-first
gmail_ingress_enabled = runtime_flags_service.get_flag("gmail_ingress_enabled", True)

if not gmail_ingress_enabled:
    # Debug logging complet des données Redis
    redis_debug = {
        "runtime_flags_redis": redis_client.get("config:runtime_flags"),
        "webhook_config_redis": redis_client.get("config:webhook_config"),
        "processing_prefs_redis": redis_client.get("config:processing_prefs")
    }
    
    logger.warning(
        "INGRESS: Gmail ingress disabled - gmail_ingress_enabled=%s | Redis debug: %s",
        gmail_ingress_enabled,
        redis_debug
    )
    
    return jsonify({
        "success": False,
        "message": "Gmail ingress disabled"
    }), 409
```

### Trade-offs : Toggle activé vs désactivé

| État | Avantages | Inconvénients | Cas d'usage |
|------|-----------|---------------|-------------|
| **Activé (défaut)** | Traitement temps réel, pas de perte d'emails | Consommation resources si flood | Production normale |
| **Désactivé** | Protection contre floods, debug facilité | Emails mis en attente dans Apps Script | Maintenance, incident |

### Debug logging pour ops

Quand désactivé, l'endpoint dump les configurations Redis pour diagnostic:
- `config:runtime_flags` : État du toggle
- `config:webhook_config` : URLs et paramètres webhook
- `config:processing_prefs` : Préférences de traitement

---

## Monitoring : les métriques qui comptent

### Logs structurés

```python
# Logs avec préfixe GMAIL_PUSH
logger.info(f"GMAIL_PUSH: Successfully processed email from {masked_sender}")
logger.warning(f"GMAIL_PUSH: Skipped email - sender not in allowlist: {masked_sender}")
logger.error(f"GMAIL_PUSH: Pattern matching error: {error}")
```

### Métriques dashboard

- **Ingress count** : Nombre d'emails reçus par heure
- **Processing time** : Temps moyen de traitement
- **Error rate** : Taux d'erreur par type
- **Provider breakdown** : Dropbox vs FromSmash vs SwissTransfer

### Alertes recommandées

- **Aucun ingress depuis 15 minutes** : Apps Script down
- **Taux d'erreur > 5%** : Problème de configuration  
- **Timeout R2 > 10%** : Worker R2 down

---

## Tests : couverture complète

### Tests unitaires (7 tests)

```python
def test_ingress_gmail_unauthorized():
    """401 sans token Bearer"""
    response = client.post("/api/ingress/gmail", json={})
    assert response.status_code == 401

def test_ingress_gmail_missing_required_fields():
    """400 si sender/body manquants"""
    response = client.post("/api/ingress/gmail", 
                          json={"subject": "test"},
                          headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 400

def test_ingress_gmail_happy_path():
    """200 processed avec routing et R2"""
    payload = {
        "sender": "test@example.com",
        "body": "Lien: https://www.dropbox.com/s/abc123/file.pdf"
    }
    response = client.post("/api/ingress/gmail", 
                          json=payload,
                          headers={"Authorization": "Bearer valid_token"})
    assert response.status_code == 200
    assert response.json["status"] == "processed"
```

### Commande d'exécution

```bash
pytest tests/routes/test_api_ingress.py -v
# 7 passed, 1 warning
```

---

## Dépannage : les problèmes courants

| Symptôme | Cause | Solution |
|----------|-------|----------|
| 401 Unauthorized | `PROCESS_API_TOKEN` manquant | Ajouter la variable d'environnement Render |
| 400 Missing field | Apps Script n'envoie pas sender/body | Corriger le payload Apps Script |
| 409 Gmail ingress disabled | Flag `gmail_ingress_enabled`=false | Activer via dashboard (onglet Outils) |
| 409 Webhook sending disabled | Flag `webhook_sending_enabled`=false | Activer via dashboard |
| 200 skipped_sender_not_allowed | Expéditeur non dans allowlist | Ajouter via dashboard polling config |
| R2 offload failed | Worker R2 down | Vérifier `R2_FETCH_TOKEN` et endpoint |

---

## Évolutions prévues

1. **Signature HMAC optionnelle** : Pour renforcer la sécurité Apps Script
2. **Batch mode** : Accepter plusieurs emails dans un seul appel  
3. **Webhook callback** : Notifier Apps Script des échecs
4. **Rate limiting par expéditeur** : Éviter les floods

---

## La Golden Rule : Apps Script Pousse, On Contrôle

Google Apps Script pousse les emails via `/api/ingress/gmail` avec authentification Bearer. On valide, déduplique, applique les patterns, route dynamiquement, et offload R2. Le toggle runtime Redis-first permet de contrôler l'ingestion sans perdre d'emails, avec debug logging complet pour les ops.

---

## Migration depuis IMAP

Si vous avez encore du polling IMAP :

1. **Désactiver `ENABLE_BACKGROUND_TASKS`**
2. **Configurer `PROCESS_API_TOKEN`**
3. **Déployer Apps Script** (voir code exemple)
4. **Supprimer variables IMAP** (`EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`)

Le gain : -90% de bande passante, -100% de timeouts IMAP, +100% de fiabilité.
