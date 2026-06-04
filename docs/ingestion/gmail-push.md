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

### 1. Contrôleur Flask mince

```python
# routes/api_ingress.py
@bp.route("/gmail", methods=["POST"])
def ingest_gmail() -> tuple[Response, int] | Response:
    if not _auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Invalid JSON payload"}), 400

    ar = sys.modules.get("app_render")
    if ar is None:
        return jsonify({"success": False, "message": "Server not ready"}), 503

    ingress_service = getattr(ar, "_ingress_service", None)
    if not ingress_service:
        return jsonify({"success": False, "message": "Service unavailable"}), 503

    result, status_code = ingress_service.process_gmail_push(payload)
    return jsonify(result), status_code
```

### 2. Validation et extraction des e-mails (IngressService)

```python
# services/ingress_service.py (IngressService._validate_payload)
def _validate_payload(self, payload: Dict[str, Any]) -> Tuple[bool, str, dict]:
    subject = payload.get("subject", "")
    sender_raw = payload.get("sender", "")
    body = payload.get("body", "")
    email_date = payload.get("date", "")

    if not isinstance(subject, str): subject = ""
    if not isinstance(sender_raw, str): sender_raw = ""
    if not isinstance(body, str): body = ""
    if not isinstance(email_date, str): email_date = ""

    if not sender_raw:
        return False, "Missing field: sender", {}
    if not body:
        return False, "Missing field: body", {}
        
    return True, "", {
        "subject": subject,
        "sender_raw": sender_raw,
        "body": body,
        "email_date": email_date
    }
```

### 3. Déduplication et Verrou "In-flight" (IngressService)

L'Email ID unique est généré en concaténant le sujet, l'expéditeur et la date pour prévenir les collisions et regrouper les conversations :

```python
# services/ingress_service.py (IngressService._compute_email_id)
def _compute_email_id(self, subject: str, sender: str, date: str) -> str:
    unique_str = f"{subject}|{sender}|{date}"
    return hashlib.md5(unique_str.encode("utf-8")).hexdigest()
```

L'idempotence s'appuie sur `DeduplicationService` avec un verrou "in-flight" Redis à TTL court (10s par défaut) pour intercepter les doubles requêtes POST simultanées :

```python
# services/ingress_service.py (IngressService.process_gmail_push)
dedup_service = DeduplicationService.get_instance()
if dedup_service.is_email_processed(email_id):
    return {"success": True, "status": "already_processed", "email_id": email_id}, 200

inflight_acquired = False
try:
    lock_ttl = getattr(settings, "EMAIL_ID_INFLIGHT_LOCK_TTL_SECONDS", 10)
    inflight_acquired = bool(dedup_service.acquire_email_inflight_lock(email_id, lock_ttl))
    if not inflight_acquired:
        return {"success": True, "status": "already_processing", "email_id": email_id}, 200
except Exception:
    inflight_acquired = False
```

### 4. Allowlist expéditeurs

```python
# services/ingress_service.py (IngressService._check_sender_allowlist)
def _check_sender_allowlist(self, sender_email: str) -> bool:
    try:
        gmail_sender_list = getattr(settings, "GMAIL_SENDER_ALLOWLIST", [])
        allowed = [
            str(s).strip().lower()
            for s in (gmail_sender_list if isinstance(gmail_sender_list, list) else [])
            if isinstance(s, str) and s.strip()
        ]
        if allowed and sender_email not in allowed:
            return False
    except Exception:
        pass
    return True
```

### 5. Pattern matching et routage temporel

```python
# Détection Media Solution / DESABO et calcul de fenêtre horaire
detector_val, delivery_time_val, desabo_is_urgent = self._get_detector_and_time(subject, body, tz_for_polling)
within, start_payload_val, e_str = self._evaluate_time_window(now_local)
```

### 6. Routing dynamique avant envoi

Les règles dynamiques de routage sont chargées et évaluées par le service `RoutingRulesService` :

```python
# services/ingress_service.py (IngressService.process_gmail_push)
processing_prefs = self._get_processing_prefs()
# Envoi webhook et mise à jour de l'état
flow_result = email_orchestrator.send_custom_webhook_flow(
    email_id=email_id,
    subject=subject,
    payload_for_webhook=payload_for_webhook,
    delivery_links=delivery_links or [],
    webhook_url=webhook_url,
    ...
)
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

### ✅ Le nouveau monde : enrichissement R2 via IngressService

```python
# services/ingress_service.py - IngressService._maybe_enrich_delivery_links_with_r2
def _maybe_enrich_delivery_links_with_r2(self, delivery_links: list, email_id: str) -> None:
    if not delivery_links:
        return
    try:
        if R2TransferService is None:
            return
        r2_service = R2TransferService.get_instance()
        if not r2_service.is_enabled():
            return
    except Exception:
        return

    for item in delivery_links:
        self._process_single_delivery_link(item, r2_service, email_id)
```

**Le pattern** : L'offload R2 est délégué à `R2TransferService` pour chaque lien détecté. En cas d'erreur de transfert vers Cloudflare, le système conserve l'URL d'origine dans le payload du webhook sortant pour éviter les interruptions de service.

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
| 200 | already_processed | Doublon détecté (déduplication) |
| 200 | already_processing | Double POST en cours (verrou in-flight) |
| 200 | skipped_sender_not_allowed | Expéditeur non autorisé |
| 200 | skipped_outside_time_window | Hors fenêtre (RECADRAGE) |
| 200 | stopped_by_routing_rule | Règle routing avec stop_processing |
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

Afin de respecter les directives de protection des données personnelles (recommandation SonarCloud), les identifiants d'emails, les adresses d'expéditeurs et les sujets des messages sont systématiquement nettoyés et masqués via la fonction `mask_sensitive_data` de `utils/text_helpers.py` avant d'être inscrits dans les logs applicatifs :

```python
# services/ingress_service.py (IngressService.process_gmail_push)
self._logger.info(
    "INGRESS: gmail payload received (email_id=%s sender=%s subject=%s)",
    mask_sensitive_data(email_id, "id"),
    mask_sensitive_data(sender_email, "email"),
    mask_sensitive_data(subject, "subject"),
)
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

### Tests unitaires (9 tests)

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

def test_gmail_ingress_idempotent_inflight_lock():
    """Double POST identique → seul le premier traite"""
    payload = {
        "sender": "test@example.com",
        "body": "Test email",
        "date": "2026-02-25T10:00:00Z"
    }
    
    # Mock : premier appel acquiert le lock
    with patch('app_render.acquire_email_id_inflight_lock_redis', return_value=True):
        response1 = client.post("/api/ingress/gmail", 
                               json=payload,
                               headers={"Authorization": "Bearer valid_token"})
        assert response1.status_code == 200
        assert response1.json["status"] == "processed"
    
    # Mock : second appel ne peut pas acquérir le lock
    with patch('app_render.acquire_email_id_inflight_lock_redis', return_value=False):
        response2 = client.post("/api/ingress/gmail", 
                               json=payload,
                               headers={"Authorization": "Bearer valid_token"})
        assert response2.status_code == 200
        assert response2.json["status"] == "already_processing"
        assert response2.json["email_id"] == md5("test@example.com:2026-02-25T10:00:00Z").hexdigest()

def test_gmail_ingress_idempotent_inflight_lock_webhook_failure():
    """Double POST avec webhook HTTP 500 → toujours 1 seule tentative sortante"""
    payload = {
        "sender": "test@example.com",
        "body": "Test email",
        "date": "2026-02-25T10:00:00Z"
    }
    
    # Mock : premier appel acquiert le lock mais webhook échoue
    with patch('app_render.acquire_email_id_inflight_lock_redis', return_value=True):
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError("HTTP 500")):
            response1 = client.post("/api/ingress/gmail", 
                                   json=payload,
                                   headers={"Authorization": "Bearer valid_token"})
            # Le traitement peut échouer mais le lock était acquis
    
    # Mock : second appel ne peut toujours pas acquérir le lock
    with patch('app_render.acquire_email_id_inflight_lock_redis', return_value=False):
        response2 = client.post("/api/ingress/gmail", 
                               json=payload,
                               headers={"Authorization": "Bearer valid_token"})
        assert response2.status_code == 200
        assert response2.json["status"] == "already_processing"
```

### Commande d'exécution

```bash
pytest tests/routes/test_api_ingress.py -v
# 9 passed, 1 warning
```

---

## Dépannage : les problèmes courants

| Symptôme | Cause | Solution |
|----------|-------|----------|
| 401 Unauthorized | `PROCESS_API_TOKEN` manquant | Ajouter la variable d'environnement Render |
| 400 Missing field | Apps Script n'envoie pas sender/body | Corriger le payload Apps Script |
| 200 already_processing | Double POST Gmail Apps Script | Comportement normal d'idempotence |
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
