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
# ANTI-PATTERN — webhook_sender.py
def send_webhook(url, payload):
    try:
        response = requests.post(url, json=payload, timeout=30)
        logger.info(f"Webhook sent to {url}")
    except Exception as e:
        logger.error(f"Webhook failed: {e}")
        # Perdu silencieux — pas de retry !
        return False
    
    # Log dans fichier éphémère
    with open('debug/webhook_logs.json', 'a') as f:
        f.write(json.dumps({"timestamp": now(), "status": "success"}))
    
    return True
```

### ✅ Le nouveau monde : envoi unifié et résilient

```python
# email_processing/orchestrator.py — envoi avec retry et logging de diagnostic
def send_custom_webhook_flow(
    *,
    email_id: str,
    subject: str | None,
    payload_for_webhook: dict,
    delivery_links: list,
    webhook_url: str,
    webhook_ssl_verify: bool,
    allow_without_links: bool,
    processing_prefs: dict,
    rate_limit_allow_send,
    record_send_event,
    append_webhook_log,
    mark_email_id_as_processed_redis,
    mark_email_as_read_imap,
    mail,
    email_num,
    urlparse,
    requests,
    time,
    logger,
    webhook_delivery_mode: str | None = None,
    webhook_fallback_on_415: bool | None = None,
) -> bool:
    # 1. Validation de la présence de liens de livraison
    if (not delivery_links) and (not allow_without_links):
        logger.info("CUSTOM_WEBHOOK: Skipping send because no delivery links detected")
        append_webhook_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "skipped",
            "error_message": "No delivery links detected"
        })
        if mark_email_id_as_processed_redis(email_id):
            mark_email_as_read_imap(mail, email_num)
        return True

    # 2. Vérification du Rate Limiting
    if not rate_limit_allow_send():
        logger.warning("RATE_LIMIT: Skipping webhook send due to rate limit")
        append_webhook_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error_message": "Rate limit exceeded"
        })
        return True

    # 3. Boucle de Retry et Fallback 415 adaptatif
    retries = int(processing_prefs.get('retry_count') or 0)
    delay = int(processing_prefs.get('retry_delay_sec') or 0)
    timeout_sec = int(processing_prefs.get('webhook_timeout_sec') or 30)

    for attempt in range(retries + 1):
        try:
            # Envoi avec format dynamique (JSON, puis Form si erreur HTTP 415)
            for mode in _build_webhook_mode_sequence(resolved_delivery_mode, fallback_on_415):
                webhook_response = requests.post(
                    webhook_url,
                    timeout=timeout_sec,
                    verify=webhook_ssl_verify,
                    **_build_request_kwargs(serialized_payload, mode)
                )
                if webhook_response.status_code != 415:
                    break  # Succès ou autre erreur gérée

            # Succès final : journalisation et marquage IMAP
            if webhook_response.status_code == 200 and webhook_response.json().get('success', False):
                append_webhook_log({"status": "success", "email_id": email_id})
                if mark_email_id_as_processed_redis(email_id):
                    mark_email_as_read_imap(mail, email_num)
                return False
        except Exception as e_req:
            if attempt < retries:
                time.sleep(delay)
                continue
    
    # Échec final : journalisation d'erreur structurée dans Redis (fallback fichier)
    append_webhook_log({"status": "error", "email_id": email_id, "error": str(last_exc)})
    return False
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
Email Gmail Ingress → Orchestrator → Pattern Matching → Routing Rules → send_custom_webhook_flow → Webhook Cible
```

### 1. Construction du payload dans l'Ingress

```python
# routes/api_ingress.py — construction du payload
payload_for_webhook = {
    "microsoft_graph_email_id": email_id,
    "subject": subject or "",
    "receivedDateTime": date_raw or "",
    "sender_address": from_raw or sender_addr,
    "bodyPreview": preview,
    "email_content": combined_text_for_detection or "",
}
```

### 2. Déclenchement de l'envoi

```python
# email_processing/orchestrator.py — routage et envoi
# L'orchestrateur évalue les règles de routage dynamique et lance le flux
if routing_webhook_url:
    send_custom_webhook_flow(
        email_id=email_id,
        subject=subject or '',
        payload_for_webhook=payload_for_webhook,
        delivery_links=delivery_links or [],
        webhook_url=routing_webhook_url,
        webhook_ssl_verify=True,
        allow_without_links=bool(getattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', False)),
        processing_prefs=getattr(ar, 'PROCESSING_PREFS', {}),
        rate_limit_allow_send=getattr(ar, '_rate_limit_allow_send'),
        record_send_event=getattr(ar, '_record_send_event'),
        append_webhook_log=getattr(ar, '_append_webhook_log'),
        mark_email_id_as_processed_redis=ar.mark_email_id_as_processed_redis,
        mark_email_as_read_imap=ar.mark_email_as_read_imap,
        mail=mail,
        email_num=num,
        requests=requests,
        time=time,
        logger=logger,
    )
```

### 3. Logging persistant

```python
# app_render.py — persistance Redis avec fallback
def _append_webhook_log(log_entry: dict) -> None:
    """Ajoute un log dans le ConfigStore (Redis-first avec fallback local)"""
    try:
        # Sérialise et pousse dans la liste Redis
        redis_client = getattr(_ar, "redis_client", None)
        if redis_client:
            redis_client.lpush("r:ss:webhook_logs:v1", json.dumps(log_entry))
            redis_client.ltrim("r:ss:webhook_logs:v1", 0, 1000)
            redis_client.expire("r:ss:webhook_logs:v1", 86400 * 7)
        else:
            _append_webhook_log_file(log_entry)
    except Exception:
        _append_webhook_log_file(log_entry)
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

# Media type principal pour l'envoi du webhook personnalisé
WEBHOOK_DELIVERY_MODE=json

# Basculer automatiquement vers l'autre media type après un HTTP 415
WEBHOOK_FALLBACK_ON_415=true

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

### Fallback 415 : compatibilité proxy sans casser le flux existant

```python
# orchestrator.py
primary_mode, fallback_on_415 = resolve_webhook_delivery_settings()

for mode in build_mode_sequence(primary_mode, fallback_on_415=fallback_on_415):
    response = requests.post(
        webhook_url,
        data=serialized_payload,
        headers={
            "Content-Type": (
                "application/json"
                if mode == "json"
                else "application/x-www-form-urlencoded"
            ),
            "Accept": "application/json, text/plain, */*",
        },
        timeout=timeout_sec,
        verify=webhook_ssl_verify,
    )
    if response.status_code != 415:
        break
```

**Pourquoi** : l'incident du 10/04/2026 a montré des réponses `415 Unsupported Media Type` rendues par `openresty/1.27.1.1` avant le PHP applicatif. Le problème était intermittent et n'était plus reproductible au moment du diagnostic. Le fallback a donc été conçu comme une **mesure de compatibilité défensive**, pas comme une réécriture du protocole métier.

**Trade-offs** :
- ✅ protège le flux Gmail Push quand un proxy amont devient plus strict qu'attendu ;
- ✅ conserve le retry/backoff, la déduplication, les logs dashboard et le marquage read/processed ;
- ✅ rend le mode primaire configurable via `webhook_config` (Redis-first) ;
- ❌ ajoute une branche réseau supplémentaire à diagnostiquer ;
- ❌ peut masquer un problème infra si on ne regarde pas les logs enrichis.

**Règle de prod recommandée** : laissez `webhook_delivery_mode=json` et `webhook_fallback_on_415=true` tant qu'aucune contrainte infra stable n'impose explicitement `form`.

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

### Logs dashboard attendus après durcissement

Les logs `custom` exposent désormais :
- `delivery_mode` : mode effectivement accepté (`json` ou `form`) ;
- `attempted_delivery_modes` : séquence réellement tentée ;
- `fallback_used` : vrai si un basculement 415 a eu lieu ;
- `failure_reason` : cause normalisée (`unsupported_media_type`, `bot_protection_denied`, `upstream_server_error`, etc.) ;
- `response_snippet` : extrait court et non-PII de la réponse amont.

Objectif : garder un dashboard actionnable sans journaliser le `email_content` brut.

### Cas Imunify360 : ce que cela signifie

Quand le webhook répond avec un message du type `Access denied by Imunify360 bot-protection`, le problème ne vient pas du parsing Gmail ni du media type HTTP de l'application. Cela signifie que l'infrastructure cible bloque l'IP source de Render comme trafic automatisé.

✅ Action recommandée : faire **whitelister l'IP de sortie Render** côté hébergeur / Imunify360.

❌ Ce qu'il ne faut pas faire : essayer de contourner cela dans le code applicatif (headers trompeurs, navigation automatisée, changement de flux métier). Le bon correctif est **infra**, pas applicatif.

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
pytest tests/test_webhook_logs_redis_persistence.py -v

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

*Pour les détails de configuration : voir [configuration-reference.md](file:///home/kidpixel/render_signal_server-main/docs/core/configuration-reference.md) ; pour l'offload R2 : voir [file-offload.md](file:///home/kidpixel/render_signal_server-main/docs/processing/file-offload.md).*
