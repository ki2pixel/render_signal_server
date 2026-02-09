# Render Signal Server

**TL;DR**: Middleware d'ingestion email haute performance avec Gmail Push, routing dynamique, et offload R2. Architecture orientée services, monitoring complet, et authentification sans mot de passe.

---

## Le problème : les webhooks qui perdaient des emails

J'ai hérité d'un système où les emails arrivaient par polling IMAP toutes les 5 minutes. Les problèmes étaient multiples :

- **Latence** : 5 minutes de retard minimum par email
- **Pertes** : Emails manqués lors des timeouts IMAP
- **Coûts** : Bande passante gaspillée avec des transferts doubles
- **Complexité** : État partagé entre plusieurs conteneurs sans coordination

Pire encore : sur Render multi-conteneurs, chaque instance pollait indépendamment, créant des doublons et des conflits de verrouillage.

---

## La solution : tour de contrôle avec Gmail Push

### Architecture de la tour de contrôle

Pensez au système comme une tour de contrôle aérienne : chaque email est un vol qui arrive et doit être dirigé vers la bonne piste (webhook) sans collision.

```
Email Gmail Push → Tour de contrôle (Orchestrator) → Routing Rules → Pistes d'atterrissage (Webhooks)
```

### Fonctionnalités clés

- **Gmail Push Ingress** : Ingestion temps réel via Apps Script
- **Routing Dynamique** : Configuration UI des règles de traitement sans redéploiement
- **Offload R2** : Transfert automatique des fichiers volumineux vers Cloudflare R2
- **Magic Links** : Authentification sécurisée sans mot de passe
- **Monitoring** : Health checks, logs structurés, métriques temps réel

---

## Idées reçues sur la tour de contrôle

### ❌ "Gmail Push est juste du polling déguisé"
Gmail Push utilise des webhooks temps réel via Apps Script. L'email arrive instantanément, pas toutes les 5 minutes.

### ❌ "Redis est optionnel pour le multi-conteneurs"
Sans Redis, chaque conteneur a son propre état. C'est comme avoir plusieurs tours de contrôle qui ne communiquent pas.

### ❌ "L'offload R2 complique le flux"
R2 est transparent : si le transfert échoue, le webhook part avec l'URL originale. La tour de contrôle a toujours une piste de secours.

---

## Tableau des approches d'ingestion

| Approche | Latence | Fiabilité | Coût bande passante | Complexité multi-conteneurs |
|----------|---------|-----------|-------------------|------------------------------|
| IMAP Polling | 5-15 min | 60-80% | Élevée (double transfert) | Très élevée (locks) |
| Gmail Push | <1s | 99%+ | Optimisée (R2) | Faible (Redis shared) |
| Webhook direct | <1s | 95% | Variable | Moyenne (load balancer) |

---

## Architecture Orientée Services

### Services de la tour de contrôle

Chaque service est un spécialiste dans la tour de contrôle :

| Service | Rôle | Caractéristiques |
|---------|------|----------------|
| `ConfigService` | Gestion configuration centralisée | Singleton, cache TTL 60s |
| `AuthService` | Authentification et autorisation | Flask-Login + Magic Links |
| `WebhookConfigService` | Configuration webhooks | Singleton, validation HTTPS |
| `RoutingRulesService` | Moteur de routage dynamique | Builder visuel + validation |
| `R2TransferService` | Offload Cloudflare R2 | Timeout adaptatifs, fallback garanti |
| `MagicLinkService` | Tokens HMAC signés | TTL configurable, stockage partagé |

### ❌ L'ancien monde : polling IMAP chaotique

```python
# ANTI-PATTERN - polling toutes les 5 minutes
while True:
    emails = imap_client.poll()  # Bloquant, timeout fréquent
    for email in emails:
        if email.is_duplicate():  # État partagé fragile
            continue
        webhook_sender.send(email)  # Pas de retry, pas de monitoring
    time.sleep(300)  # Latence garantie
```

### ✅ Le nouveau monde : tour de contrôle orchestrée

```python
# services/orchestrator.py
class EmailOrchestrator:
    def __init__(self):
        self.routing_service = RoutingRulesService.get_instance()
        self.webhook_sender = WebhookSender()
        self.r2_service = R2TransferService.get_instance()
    
    def process_email(self, email_data):
        # 1. Pattern matching (Media Solution, DESABO)
        detector = self._detect_email_type(email_data)
        
        # 2. Routing dynamique
        matched_rule = self.routing_service.evaluate(email_data, detector)
        
        # 3. Enrichissement R2
        delivery_links = self._extract_delivery_links(email_data)
        delivery_links = self._maybe_enrich_with_r2(delivery_links)
        
        # 4. Envoi webhook
        return self.webhook_sender.send_webhook(
            webhook_url=matched_rule.get('webhook_url', WEBHOOK_URL),
            payload=self._build_payload(email_data, delivery_links)
        )
```

**Le gain** : latence quasi nulle, zéro email perdu, et monitoring complet comme une tour de contrôle moderne.

---

## Ingestion Gmail Push

### Endpoint unique

```http
POST /api/ingress/gmail
Content-Type: application/json
Authorization: Bearer <PROCESS_API_TOKEN>
```

### Payload JSON

```json
{
  "subject": "Nouveau document partagé",
  "sender": "notification@dropbox.com",
  "body": "Voici le lien : https://www.dropbox.com/s/abc123/file.zip",
  "date": "2026-02-04T10:30:00Z"
}
```

### Flux de traitement

1. **Authentification** : Vérification Bearer token
2. **Validation** : Champs obligatoires (`sender`, `body`)
3. **Déduplication** : Vérification Redis avec email_id MD5
4. **Pattern matching** : Détection Media Solution / DESABO
5. **Routing dynamique** : Évaluation des règles personnalisées
6. **Offload R2** : Enrichissement des liens si activé
7. **Envoi webhook** : Distribution avec retry intelligent

---

## Routing Dynamique

### Builder visuel

Le dashboard permet de configurer les règles de traitement sans redéploiement :

```javascript
// Exemple de règle
{
  "name": "Factures Client X",
  "conditions": [
    {"field": "sender", "operator": "contains", "value": "@clientx.com"},
    {"field": "subject", "operator": "regex", "value": "facture\\s+\\d{4}"}
  ],
  "actions": {
    "webhook_url": "https://hooks.make.com/factures-x",
    "priority": "high",
    "stop_processing": true
  }
}
```

### Priorité d'évaluation

1. **Règles utilisateur** : Configuration personnalisée
2. **Fallbacks backend** : Règles héritées (DESABO, Media Solution)
3. **Défaut** : Webhook par défaut

---

## Offload Cloudflare R2

### Économie de bande passante

Le système transfère automatiquement les fichiers volumineux vers Cloudflare R2 :

```python
# Avant : double transfert coûteux
# Email → Render → Webhook (50MB) → Récepteur

# Après : offload intelligent
# Email → R2 (pull) → Webhook (lien CDN)
```

### Fallback garanti

```python
# Conservation des URLs sources même si R2 échoue
try:
    r2_result = r2_service.request_remote_fetch(source_url, provider)
    if r2_result and r2_result.get('r2_url'):
        link['r2_url'] = r2_result['r2_url']
except Exception as e:
    logger.warning(f"R2_TRANSFER: {e} (fallback to source URLs)")
    # Le flux continue avec URLs originales
```

### Configuration requise

```bash
R2_FETCH_ENABLED=true
R2_FETCH_ENDPOINT=https://r2-fetch-worker.workers.dev
R2_FETCH_TOKEN=token-secret-partagé
R2_PUBLIC_BASE_URL=https://media.domain.com
R2_BUCKET_NAME=render-signal-media
```

---

## Authentification Magic Link

### Tokens HMAC signés

```python
# Génération de token
def generate_magic_link(unlimited=False):
    token_id = secrets.token_urlsafe(32)
    created_at = time.time()
    payload = f"{token_id}:{created_at}"
    signature = hmac.new(
        FLASK_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    expires_at = None if unlimited else created_at + TTL_SECONDS
    
    return {
        'magic_link': f"https://domain.com/dashboard/magic-link/{token_id}:{signature}",
        'expires_at': datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
        'single_use': not unlimited
    }
```

### Stockage partagé

- **Redis-first** : Tokens permanents stockés dans Redis
- **Fallback fichier** : `magic_link_tokens.json` si Redis indisponible
- **API PHP** : `config_api.php` pour le multi-conteneurs Render

---

## Monitoring et Observabilité

### Health check complet

```json
{
  "status": "ok",
  "timestamp": "2026-02-04T10:30:00Z",
  "version": "v2.0.0",
  "uptime": 86400,
  "services": {
    "redis": {"status": "ok", "connected": true},
    "background_tasks": {"status": "running", "lock_acquired": true}
  },
  "metrics": {
    "memory_usage_mb": 256,
    "error_rate_24h": 2.5,
    "active_webhooks": 42,
    "last_webhook": "2026-02-04T10:25:00Z"
  }
}
```

### Logs structurés

```python
# Logs avec contexte et métriques
webhook_logger.info("Webhook sent", 
    webhook_url=mask_url(webhook_url),
    email_id=email_id,
    status="success",
    duration_ms=1234,
    delivery_links_count=2
)

r2_logger.info("File transferred to R2",
    provider=provider,
    source_url=mask_url(source_url),
    r2_url=r2_url,
    file_size_mb=26.5,
    duration_ms=45000
)
```

---

## Déploiement

### Pipeline automatisé

```yaml
# .github/workflows/render-image.yml
name: Build & Deploy Render Image

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          ghcr.io/${{ github.repository }}:latest
          ghcr.io/${{ github.repository }}:${{ github.sha }}
      
      - name: Deploy to Render
        run: |
          if [ -n "${{ secrets.RENDER_DEPLOY_HOOK_URL }" ]; then
            curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
          else
            curl -X POST "https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys" \
              -H "Authorization: Bearer ${ secrets.RENDER_API_KEY }}" \
              -H "Content-Type: application/json" \
              -d '{"imageUrl": "ghcr.io/${{ github.repository }}:${{ github.sha }}"}'
```

### Variables d'environnement

```bash
# Variables obligatoires
FLASK_SECRET_KEY=votre-clé-secrète
TRIGGER_PAGE_PASSWORD=mot-de-passe-dashboard
PROCESS_API_TOKEN=token-api-gmail-push
WEBHOOK_URL=https://hooks.make.com/votre-webhook

# Multi-conteneurs
REDIS_URL=redis://user:pass@host:port/db
ENABLE_BACKGROUND_TASKS=false  # Un seul conteneur actif
```

---

## Tests et Qualité

### Couverture de tests

- **Tests unitaires** : 356/356 passants (100%)
- **Couverture code** : 67.73% (objectif : 80%+)
- **Tests résilience** : Marqueurs `@pytest.mark.redis`/`@pytest.mark.r2`/`@pytest.mark.resilience`

### Tests de résilience

```python
# Tests Redis lock
@pytest.mark.redis
def test_redis_distributed_lock():
    # Test du verrou distribué Redis
    lock_acquired = distributed_lock.acquire()
    assert lock_acquired is True
    
    # Test fallback si Redis indisponible
    with patch('redis.Redis.from_url', side_effect=ConnectionError):
        lock_acquired = distributed_lock.acquire()
        assert lock_acquired is False  # Fallback file lock
        assert "Using file-based lock" in caplog

# Tests R2 fallback
@pytest.mark.r2
def test_r2_fallback_on_worker_failure():
    # Test que le flux continue même si R2 échoue
    result = r2_service.request_remote_fetch("invalid_url")
    assert result is None  # Fallback gracieux garantit
```

---

## Support et Maintenance

### Documentation complète

- **Guide d'installation** : `docs/ops/deployment.md`
- **Guide de dépannage** : `docs/ops/troubleshooting.md`
- **Référence API** : `docs/core/configuration-reference.md`
- **Architecture** : `docs/core/architecture.md`
- **Ingestion Gmail Push** : `docs/ingestion/gmail-push.md`
- **Routing dynamique** : `docs/processing/routing-engine.md`
- **Offload R2** : `docs/processing/file-offload.md`
- **Authentification** : `docs/access/authentication.md`
- **Dashboard UI** : `docs/access/dashboard-ui.md`

### Communauté

- **Issues** : Signalement via GitHub Issues
- **Discussions** : Discussions GitHub Discussions
- **Wiki** : Documentation collaborative via GitHub Wiki
- **Roadmap** : Évolution prévue et futures améliorations

---

## La Golden Rule : Tour de contrôle orchestrée

Le système est une tour de contrôle où Gmail Push est le radar, les services sont les contrôleurs, Redis est le système de coordination, et R2 optimise les pistes d'atterrissage. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la sécurité et l'efficacité du trafic.

---

*Pour commencer : voir `docs/v2/core/architecture.md`. Pour le déploiement : voir `docs/v2/ops/deployment.md`. Pour le dépannage : voir `docs/v2/ops/troubleshooting.md`.*
