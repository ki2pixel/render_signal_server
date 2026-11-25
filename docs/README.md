# Render Signal Server

**TL;DR**: Middleware d'ingestion email haute performance avec Gmail Push, routing dynamique, et offload R2. Architecture orientée services, monitoring complet, et magic links en alternative au mot de passe.

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
- **Magic Links** : Authentification par lien signé, en complément du mot de passe
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
| `ConfigService` | Accès centralisé à la configuration | Sans état, lit `config.settings` |
| `AuthService` | Authentification et autorisation | Flask-Login + Magic Links |
| `IngressService` | Ingestion Gmail Push | Singleton, exécuteur borné, dédup + R2 + webhook |
| `WebhookConfigService` | Configuration webhooks | Singleton, validation HTTPS |
| `RoutingRulesService` | Moteur de routage dynamique | Builder visuel + validation, Redis-first |
| `DeduplicationService` | Verrou in-flight et mémoire Redis | Fallback mémoire si Redis indisponible |
| `RuntimeFlagsService` | Flags d'exécution | Cache 60s, Redis + fichier |
| `R2TransferService` | Offload Cloudflare R2 | Timeout adaptatifs, fallback garanti |
| `MagicLinkService` | Tokens HMAC signés | TTL configurable, stockage partagé |
| `RateLimitService` | Limitation du débit webhook | Compteur partagé entre workers |
| `RuntimeMetricsService` | Métriques runtime | Métriques exposées par `/api/utility` |
| `WebhookLoggerService` | Journal des webhooks | Redis-first, fallback JSON |

### ❌ L'ancien monde : polling IMAP chaotique

```python
# ANTI-PATTERN — polling toutes les 5 minutes
while True:
    emails = imap_client.poll()  # Bloquant, timeout fréquent
    for email in emails:
        if email.is_duplicate():  # État partagé fragile
            continue
        webhook_sender.send(email)  # Pas de retry, pas de monitoring
    time.sleep(300)  # Latence garantie
```

### ✅ Le nouveau monde : tour de contrôle orchestrée

Le chemin Gmail Push tient en une méthode publique, `IngressService.process_gmail_push(payload)`, qui retourne `(réponse, code HTTP)` :

| Étape | Responsable | Détail |
| --- | --- | --- |
| 1. Validation | `IngressService._validate_payload` | Champs obligatoires, types, taille du corps |
| 2. Barrières | `_check_ingress_enabled`, `_check_preconditions` | Runtime flag, allowlist, envoi webhook activé |
| 3. Idempotence | `DeduplicationService` | `is_email_processed`, puis `acquire_email_inflight_lock` |
| 4. Traitement | `_process_in_background` ou `_process_fresh_email` | Pattern matching, routing, résolution du créneau |
| 5. Enrichissement | `_maybe_enrich_delivery_links_with_r2` | Best-effort, URL source conservée si R2 échoue |
| 6. Envoi | `send_custom_webhook_flow` | Rate limit, fallback 415, journal webhook |

`send_custom_webhook_flow` reçoit explicitement ses dépendances (callbacks de rate limit, d'enregistrement d'événement, de journalisation et de marquage de déduplication). Rien n'est lu depuis un module global implicite : le chemin IMAP et le chemin Gmail Push peuvent l'appeler avec leurs propres implémentations.

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

Un token a la forme `<token_id>.<expires>.<signature>` : l'identifiant et l'expiration sont signés ensemble en HMAC SHA-256 avec `FLASK_SECRET_KEY`. Un token permanent utilise la chaîne `permanent` à la place du timestamp.

```python
# services/magic_link_service.py
token_id = secrets.token_urlsafe(16)
expires_component = "permanent" if unlimited else str(int(expires_at.timestamp()))
signature = self._sign_components(token_id, expires_component)
token = f"{token_id}.{expires_component}.{signature}"
```

`consume_token(token)` vérifie la signature, contrôle l'expiration, puis marque le token comme consommé. Une signature invalide et un token déjà utilisé produisent deux messages distincts.

### Génération et consommation

- `POST /api/auth/magic-link` (session requise) : corps `{"unlimited": false}`, réponse `201` avec `magic_link`, `expires_at`, `unlimited`.
- Le lien pointe vers la route de consommation du blueprint `dashboard`, qui valide le token puis ouvre la session.
- **Stockage** : fichier JSON verrouillé (`MAGIC_LINK_TOKENS_FILE`), avec miroir optionnel vers Redis ou l'API PHP `config_api.php` quand `REDIS_URL` ou `EXTERNAL_CONFIG_BASE_URL` + `CONFIG_API_TOKEN` sont définis.
- **Nettoyage** : les tokens expirés sont purgés au chargement et après consommation.

---

## Monitoring et Observabilité

### Health check

`GET /health` répond volontairement de façon minimale, pour rester compatible avec les sondes Render :

```json
{"status": "ok"}
```

Les métriques détaillées sont exposées par `GET /api/utility` : démarrage du process, uptime, dernier cycle de polling, dernier webhook envoyé, état du poller legacy. `GET /api/utility/diag/runtime` fournit le même type d'information pour le diagnostic local.

### Logs structurés

Le journal webhook est centralisé par `WebhookLoggerService.append_log(entry)` : Redis si disponible, sinon fichier `debug/webhook_logs.json`. Les entrées sont aussi écrites dans les logs applicatifs avec le préfixe `WEBHOOK:`.

```python
WebhookLoggerService.get_instance().append_log({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "status": "success",
    "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
    "email_id": email_id,
})
```

Les URL de webhook sont tronquées à 50 caractères avant journalisation. Les emails, identifiants et sujets sensibles passent par `mask_sensitive_data` dans les logs applicatifs.

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

- **Suite** : `pytest` (marqueurs `unit`, `integration`, `e2e`, `slow`, `redis`, `imap`, `r2`, `resilience`)
- **Couverture** : générée par `pytest-cov` (configuration dans `.coveragerc`)
- **État de référence** : se référer au dernier run CI ; la suite recense plus de 400 fonctions de test

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
- **Extraction de liens** : `docs/ingestion/link-extraction.md`
- **Routing dynamique** : `docs/processing/routing-engine.md`
- **Pattern matching** : `docs/processing/pattern-matching.md`
- **Déduplication** : `docs/processing/deduplication-engine.md`
- **Offload R2** : `docs/processing/file-offload.md`
- **Authentification** : `docs/access/authentication.md`
- **Magic Links** : `docs/core/magic-link-auth.md`
- **Runtime Flags** : `docs/ops/runtime-flags.md`
- **Dashboard UI** : `docs/access/dashboard-ui.md`
- **Backfill recadrage 30 jours** : `docs/ops/backfill-recadrage.md`

### Communauté

- **Issues** : Signalement via GitHub Issues
- **Discussions** : Discussions GitHub Discussions
- **Wiki** : Documentation collaborative via GitHub Wiki
- **Roadmap** : Évolution prévue et futures améliorations

---

## La Golden Rule : Tour de contrôle orchestrée

Le système est une tour de contrôle où Gmail Push est le radar, les services sont les contrôleurs, Redis est le système de coordination, et R2 optimise les pistes d'atterrissage. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la sécurité et l'efficacité du trafic.

---

*Pour commencer : voir [architecture.md](core/architecture.md) ; pour le déploiement : voir [deployment.md](ops/deployment.md) ; pour le dépannage : voir [troubleshooting.md](ops/troubleshooting.md).*
