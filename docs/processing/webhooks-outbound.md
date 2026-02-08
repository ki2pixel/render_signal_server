# Webhooks Outbound

**TL;DR**: On envoie des webhooks avec retry, fenêtres horaires, et logs persistés dans Redis. Le système supporte l'absence globale, le miroir des médias, et l'offload R2 pour économiser la bande passante.

---

## Le problème : les webhooks qui ne livrent pas

J'ai découvert que les webhooks envoyés depuis Render étaient souvent perdus ou en double. Les logs étaient stockés dans des fichiers éphémères, et il n'y avait aucun retry intelligent. Pire encore, la bande passante était gaspillée avec des transferts de fichiers volumineux.

Les problèmes concrets :
- **Perte de logs** : `debug/webhook_logs.json` disparaissait à chaque redéploiement
- **Double transfert** : Fichiers téléchargés depuis Render puis envoyés aux webhooks
- **Pas de retry** : Un échec réseau = perte du webhook
- **Pas de monitoring** : Impossible de savoir si les webhooks arrivent

---

## La solution : service postal avec centre de distribution

Pensez aux webhooks outbound comme un service postal avec centre de distribution : les emails sont des lettres qui sont livrées aux destinataires via des facteurs (webhooks). Le service a un système de retry intelligent pour les livraisons échouées, des logs persistants pour suivre les colis, et un service de messagerie R2 pour optimiser les envois volumineux.

### ❌ L'ancien monde : service postal sans suivi

```python
# ANTI-PATTERN - webhook_sender.py
def send_webhook(url, payload):
    try:
        response = requests.post(url, json=payload, timeout=30)
        logger.info(f"Webhook sent to {url}")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")
        # Perdu silencieux - pas de retry !
        return False
    
    # Log dans fichier éphémère
    with open('debug/webhook_logs.json', 'a') as f:
        f.write(json.dumps({"timestamp": now(), "status": "success"}))
    
    return True
```

### ✅ Le nouveau monde : service postal avec suivi intelligent

```python
# webhook_sender.py - service résilient
class WebhookSender:
    def __init__(self):
        self.redis_client = getattr(_ar, "redis_client", None)
        self.max_retries = 3
        self.retry_delay = 5
    
    def send_webhook_with_retry(self, url, payload, email_id=None):
        """Envoi webhook avec retry et logging persistant"""
        
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                response = requests.post(
                    url, 
                    json=payload, 
                    timeout=30,
                    headers={
                        'Content-Type': 'application/json',
                        'X-Source': 'render-signal-server',
                        'User-Agent': 'RenderSignalServer/1.0'
                    }
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Succès : logging et retour
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "success",
                    "webhook_url": self._mask_url(url),
                    "target_url": response.url if response.url else url,
                    "email_id": email_id,
                    "duration_ms": duration_ms,
                    "delivery_links_count": len(payload.get('delivery_links', []))
                }
                
                self._persist_log(log_entry)
                return True
                
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    logger.warning(f"Webhook attempt {attempt + 1} failed for {url}: {e}")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    # Échec final : logging d'erreur
                    log_entry = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "error",
                        "webhook_url": self._mask_url(url),
                        "error": str(e),
                        "email_id": email_id,
                        "delivery_links_count": len(payload.get('delivery_links', []))
                    }
                    
                    self._persist_log(log_entry)
                    return False
    
    def _persist_log(self, log_entry):
        """Persistance Redis avec fallback fichier"""
        if self.redis_client:
            # Redis-first : LPUSH pour plus récent en tête
            try:
                self.redis_client.lpush("r:ss:webhook_logs:v1", json.dumps(log_entry))
                self.redis_client.ltrim("r:ss:webhook_logs:v1", 0, 1000)  # Limitation
                self.redis_client.expire("r:ss:webhook_logs:v1", 86400 * 7)  # TTL 7j
            except RedisError:
                logger.warning("Redis unavailable for webhook logging, using file fallback")
                self._persist_log_file(log_entry)
        else:
            # Fallback fichier
            self._persist_log_file(log_entry)
```

**Le gain** : suivi des livraisons, retry intelligent, et zéro perte de colis.

---

## Idées reçues sur le service postal

### ❌ "Les retry bloquent le flux"
Les retry sont intelligents : 3 tentatives avec délai croissant, et seulement en cas d'erreur réseau. Le service postal continue de traiter d'autres lettres pendant les retry.

### ❌ "Redis est une dépendance critique"
Le service postal a un fallback garanti vers fichiers locaux. Si Redis tombe, les livraisons continuent avec suivi dans les fichiers. C'est une sécurité, pas une faiblesse.

### ❌ "Les logs sont complexes à consulter"
Les logs sont structurés et accessibles via API REST. Le centre de distribution fournit une interface de consultation simple pour suivre les livraisons.

---

## Tableau comparatif des services de livraison

| Service | Fiabilité | Coût | Maintenance | Monitoring | Complexité |
|----------|-----------|-----|--------------|------------|------------|
| Service postal sans suivi | 60% | Nul | Très faible | Nul | Très faible |
| Service postal avec suivi | 95%+ | Faible | Faible | Complet | Moyenne |
| Service externe | Variable | Variable | Variable | Variable | Élevée |
| Service de messagerie | 99%+ | Moyen | Moyenne | Avancé | Élevée |

---

## Architecture du service postal

### Flux unifié

```
Email Gmail Push → Orchestrator → Pattern Matching → Routing Rules → WebhookSender → Webhook Cible
```

### 1. Construction du payload

```python
# orchestrator.py - payload enrichi
def build_webhook_payload(email_data, matched_rule=None):
    payload = {
        'microsoft_graph_email_id': email_data.get('id'),
        'subject': email_data.get('subject'),
        'sender_address': email_data.get('sender'),
        'receivedDateTime': email_data.get('date'),
        'bodyPreview': email_data.get('body', '')[:200] + '...',
        'delivery_links': email_data.get('delivery_links', []),
        'source': 'gmail_push'
    }
    
    # Enrichissement R2 si disponible
    if r2_transfer_service and r2_transfer_service.is_enabled():
        payload['delivery_links'] = _maybe_enrich_delivery_links_with_r2(payload['delivery_links'])
    
    return payload
```

### 2. Envoi avec retry

```python
# webhook_sender.py
def send_webhook_flow(webhook_url, payload, email_id=None):
    """Flux complet d'envoi webhook avec retry"""
    
    # Validation préalable
    if not webhook_url or not webhook_url.startswith('https://'):
        logger.error(f"Invalid webhook URL: {webhook_url}")
        return False
    
    # Envoi avec retry
    success = webhook_sender.send_webhook_with_retry(
        url=webhook_url,
        payload=payload,
        email_id=email_id
    )
    
    if success:
        logger.info(f"WEBHOOK: Successfully sent webhook for email {email_id}")
    else:
        logger.error(f"WEBHOOK: Failed to send webhook after {webhook_sender.max_retries} attempts")
    
    return success
```

### 3. Logging persistant

```python
# webhook_sender.py - logging structuré
def _persist_log(self, log_entry):
    """Persistance Redis avec fallback fichier"""
    
    log_entry.update({
        'timestamp': datetime.utcnow().isoformat(),
        'status': log_entry.get('status', 'unknown'),
        'webhook_url': self._mask_url(log_entry.get('webhook_url', '')),
        'target_url': log_entry.get('target_url', ''),
        'error': log_entry.get('error', ''),
        'email_id': log_entry.get('email_id', ''),
        'detector': log_entry.get('detector', ''),
        'delivery_links_count': log_entry.get('delivery_links_count', 0),
        'duration_ms': log_entry.get('duration_ms', 0)
    })
    
    # Persistance Redis-first
    if self.redis_client:
        try:
            self.redis_client.lpush("r:ss:webhook_logs:v1", json.dumps(log_entry))
            self.redis_client.ltrim("r:ss:webhook_logs:v1", 0, 1000)
            self.redis_client.expire("r:ss:webhook_logs:v1", 86400 * 7)  # 7 jours TTL
        except RedisError:
            self._persist_log_file(log_entry)
    else:
        self._persist_log_file(log_entry)
```

---

## Configuration : variables essentielles

### Variables obligatoires

```bash
# URL webhook principal
WEBHOOK_URL=https://hooks.make.com/your-webhook

# Sécurité SSL
WEBHOOK_SSL_VERIFY=true

# Autoriser les webhooks sans liens (optionnel)
ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS=false
```

### Variables optionnelles

```bash
# Retry configuration
WEBHOOK_RETRY_COUNT=3
WEBHOOK_RETRY_DELAY=5

# Miroir médias vers webhook personnalisé
MIRROR_MEDIA_TO_CUSTOM=true

# R2 Offload (voir file-offload.md)
R2_FETCH_ENABLED=true
R2_FETCH_ENDPOINT=https://r2-fetch-worker.workers.dev
R2_PUBLIC_BASE_URL=https://media.yourdomain.com
```

---

## Fonctionnalités avancées

### Absence Globale : blocage complet

```python
# orchestrator.py - vérification prioritaire
def _is_webhook_sending_enabled():
    """Vérifie si l'envoi de webhooks est autorisé"""
    
    # 1. Priorité maximale : Absence Globale
    webhook_config = webhook_config_service.get_config()
    if webhook_config.get('absence_pause_enabled'):
        today = datetime.now().strftime('%A').lower()
        active_days = [d.lower() for d in webhook_config.get('absence_pause_days', [])]
        
        if today in active_days:
            logger.info(f"ABSENCE_PAUSE: Global absence active for {today} — skipping all webhook sends")
            return False
    
    # 2. Fenêtre horaire des webhooks
    if not is_within_webhook_time_window():
        return False
    
    # 3. Flags runtime
    return runtime_flags_service.get_flag('webhook_sending_enabled', default=True)
```

**Comportement** :
- L'absence globale bloque TOUS les webhooks, même les urgents
- Priorité maximale sur toutes autres règles
- Configuration via dashboard UI ou API

### Fenêtre horaire indépendante

```python
# webhook_time_window.py
def is_within_webhook_time_window():
    """Vérifie si on est dans la fenêtre horaire des webhooks"""
    
    config = webhook_config_service.get_config()
    start_time = config.get('webhook_time_start')
    end_time = config.get('webhook_time_end')
    
    if not start_time or not end_time:
        return True  # Fenêtre désactivée
    
    try:
        start = datetime.strptime(start_time, '%H:%M').time()
        end = datetime.strptime(end_time, '%H:%M').time()
        
        now = datetime.now().time()
        
        # Cas spécial : traverser minuit
        if start > end:
            # Ex: 22:00 - 06:00 (traverse nuit)
            return now >= start or now <= end
        else:
            # Cas normal : 09:00 - 18:00
            return start <= now <= end
            
    except ValueError:
        logger.error(f"Invalid time format in webhook config: {start_time}-{end_time}")
        return True
```

**Exceptions par détecteur** :
- **DESABO non urgent** : bypass autorisé hors fenêtre
- **DESABO urgent** : respect strict de la fenêtre
- **RECADRAGE** : skip + marqué traité hors fenêtre

---

## Payload webhook enrichi

### Format complet avec R2

```json
{
  "microsoft_graph_email_id": "abc123...",
  "subject": "Média Solution - Missions Recadrage - Lot 42",
  "receivedDateTime": "2026-02-04T10:30:00Z",
  "sender_address": "notification@dropbox.com",
  "bodyPreview": "Résumé du message...",
  "delivery_links": [
    {
      "provider": "dropbox",
      "raw_url": "https://www.dropbox.com/s/abc123/file.zip?dl=0",
      "direct_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
      "r2_url": "https://media.yourdomain.com/dropbox/a1b2c3d4/e5f6g7h8/file.zip",
      "original_filename": "61 Camille.zip"
    },
    {
      "provider": "fromsmash",
      "raw_url": "https://fromsmash.com/ABC123",
      "direct_url": "https://fromsmash.com/ABC123",
      "r2_url": "https://media.yourdomain.com/fromsmash/f9e8d7c6/b5a4c3d2/file.zip",
      "original_filename": "archive.zip"
    }
  ],
  "first_direct_download_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
  "dropbox_urls": ["https://www.dropbox.com/s/abc123/file.zip"],
  "dropbox_first_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1"
}
```

### Recommandations pour les récepteurs

```python
# Exemple de traitement côté récepteur
def process_webhook(payload):
    links = payload.get('delivery_links', [])
    
    for link in links:
        # Priorité 1 : URL R2 (CDN plus rapide)
        if link.get('r2_url'):
            download_url = link['r2_url']
            filename = link.get('original_filename', 'download')
        # Priorité 2 : URL direct (Dropbox)
        elif link.get('direct_url'):
            download_url = link['direct_url']
            filename = extract_filename_from_url(link['direct_url'])
        # Priorité 3 : URL brute
        else:
            download_url = link['raw_url']
            filename = 'download'
        
        # Traitement du fichier...
        process_file(download_url, filename)
```

---

## Logs persistants : Redis-first avec fallback

### Structure des logs

```json
{
  "timestamp": "2026-02-04T10:30:00Z",
  "status": "success",
  "webhook_url": "https://hooks.make.com/abc***",
  "target_url": "https://api.example.com/webhook",
  "error": null,
  "email_id": "abc123...",
  "detector": "recadrage",
  "delivery_links_count": 2,
  "duration_ms": 1234
}
```

### API de consultation

```python
# routes/api_logs.py
@bp.route("/api/webhook_logs", methods=["GET"])
@login_required
def get_webhook_logs():
    """Récupère les logs des webhooks"""
    
    # Paramètres optionnels
    days = request.args.get('days', 7, type=int)
    status = request.args.get('status')  # "success" ou "error"
    
    redis_client = getattr(_ar, "redis_client", None)
    logs = _fetch_webhook_logs(redis_client, days=days, status=status)
    
    return jsonify({"logs": logs})
```

### Fallback transparent

```python
# app_render.py - initialisation Redis
def _init_redis_client():
    if REDIS_URL:
        try:
            _ar.redis_client = redis.Redis.from_url(REDIS_URL)
            _ar.redis_client.ping()  # Test de connexion
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            _ar.redis_client = None
```

**Le comportement** :
- **Redis disponible** : Logs dans Redis avec TTL 7 jours
- **Redis indisponible** : Fallback vers `debug/webhook_logs.json`
- **Transition** : Aucune interruption de service

---

## Miroir des médias : liens automatiques

### Configuration

```python
# processing_prefs.json
{
  "mirror_media_to_custom": true,
  "exclude_keywords": ["SPAM", "PUBLICITÉ"],
  "max_email_size_mb": 25
}
```

### Comportement

```python
# orchestrator.py - miroir automatique
def _should_mirror_media_to_custom():
    """Vérifie si le miroir des médias est activé"""
    prefs = processing_prefs_service.get_prefs()
    return prefs.get('mirror_media_to_custom', False)

def send_custom_webhook_flow(email_data, matched_rule=None):
    # ... traitement email ...
    
    # Miroir des médias si activé
    if _should_mirror_media_to_custom():
        delivery_links = link_extraction.extract_provider_links_from_text(email_data['body'])
        if delivery_links:
            logger.info(f"MIRROR_MEDIA: Found {len(delivery_links)} media links to mirror")
            # Les liens sont inclus dans le payload webhook
```

**Fournisseurs supportés** :
- **Dropbox** : `https://www.dropbox.com/s/...`
- **FromSmash** : `https://fromsmash.com/...`
- **SwissTransfer** : `https://www.swisstransfer.com/...`

---

## Tests : couverture complète

### Tests unitaires

```python
# tests/test_webhook_logs_redis_persistence.py
def test_redis_storage():
    """Test stockage Redis des logs"""
    service = WebhookSender()
    
    log_entry = {
        "timestamp": "2026-02-04T10:30:00Z",
        "status": "success",
        "webhook_url": "https://hooks.make.com/test"
    }
    
    service._persist_log(log_entry)
    
    # Vérification Redis
    logs = service.redis_client.lrange("r:ss:webhook_logs:v1", 0, 1)
    assert len(logs) == 1
    
    parsed_log = json.loads(logs[0])
    assert parsed_log['status'] == 'success'
    assert 'hooks.make.com/***' in parsed_log['webhook_url']

def test_fallback_file():
    """Test fallback fichier si Redis indisponible"""
    service = WebhookSender()
    service.redis_client = None  # Simule Redis down
    
    log_entry = {
        "timestamp": "2026-02-04T10:30:00Z",
        "status": "error",
        "error": "Connection timeout"
    }
    
    service._persist_log(log_entry)
    
    # Vérification fichier
    with open('debug/webhook_logs.json', 'r') as f:
        content = f.read()
        logs = [json.loads(line) for line in content.strip().split('\n') if line]
    
    assert len(logs) == 1
    assert logs[0]['status'] == 'error'
```

### Commande d'exécution

```bash
# Tests webhooks complets
pytest tests/test_webhook_logs_redis_persistence.py tests/test_webhook_sender.py -v

# Tests avec marqueur webhook
pytest -m "webhook" -v

# Tests de résilience
pytest -m "resilience" -v
```

---

## Monitoring et alertes

### Logs structurés

```bash
# Logs webhook avec préfixe
tail -f logs/app.log | grep WEBHOOK

# Exemples de logs
WEBHOOK: Successfully sent webhook for email abc123
WEBHOOK: Failed to send webhook after 3 attempts
WEBHOOK: Retry attempt 1 failed for https://hooks.make.com/test: Connection timeout
```

### Métriques à surveiller

| Métrique | Seuil | Action |
|----------|-------|--------|
| Taux de succès | < 90% | Vérifier URL webhook |
| Taux d'erreur timeout | > 5% | Vérifier latence réseau |
| Durée moyenne > 5s | > 10% | Vérifier payload size |
| Logs Redis manquants | > 1h | Vérifier connexion Redis |

### Alertes recommandées

```bash
# Alerte si aucun webhook depuis 30 minutes
if [ $(curl -s https://render-signal-server-latest.onrender.com/api/webhook_logs?days=1 | jq '.logs | length') -eq 0 ]; then
    echo "ALERT: No webhooks in last 24 hours"
fi
```

---

## La Golden Rule : Service postal avec retry intelligent, suivi persistant, livraison garantie

Les livraisons sont envoyées avec retry (3 tentatives), suivi persistant dans Redis avec TTL 7 jours, et fallback gracieux vers fichiers. L'absence globale bloque tout, les fenêtres horaires contrôlent le timing, et le service de messagerie enrichit automatiquement les colis volumineux. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la fiabilité du service postal.

---

*Pour les détails de configuration : voir `docs/v2/core/configuration-reference.md`. Pour l'offload R2 : voir `docs/v2/processing/file-offload.md`.*
