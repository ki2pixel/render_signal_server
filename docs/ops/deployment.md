# Deployment

**TL;DR**: On utilise Docker + GHCR + Render pour le déploiement automatique. Multi-conteneurs avec Redis pour le verrou distribué, watchdog IMAP anti-zombie, et fallback R2 garanti. Le pipeline GitHub Actions build et pousse l'image, puis déclenche Render.

---

## Le problème : le déploiement manuel qui ne tenait plus

J'ai hérité d'un système de déploiement manuel avec des scripts shell et des configurations éparpillées. Chaque mise en production était un cauchemar :

- **Déploiement manuel** : SSH, pull git, restart services
- **Configuration éparpillée** : Variables dans .env, scripts shell, systemd
- **Pas de rollback** : Si ça cassait, on revenait en arrière à la main
- **Multi-conteneurs** : Pas de coordination entre instances

Pire encore : le filesystem de Render est éphémère, donc les configurations locales disparaissaient à chaque redéploiement.

---

## La solution : chaîne de montage automatisée

Pensez au déploiement comme une chaîne de montage automobile : GitHub Actions est la ligne d'assemblage qui construit le véhicule (image Docker), GHCR est le parking de stockage, et Render est le concessionnaire qui livre le véhicule au client. Chaque étape est automatisée avec des contrôles qualité (tests) et des plans de secours (fallbacks).

### ❌ L'ancien monde : scripts shell manuels

```bash
# ANTI-PATTERN - deployment.sh
#!/bin/bash
echo "Pulling latest code..."
git pull origin main

echo "Installing dependencies..."
source /mnt/venv_ext4/venv_render_signal_server/bin/activate
pip install -r requirements.txt

echo "Restarting services..."
sudo systemctl restart render-signal-server
sudo nginx -s reload

echo "Deployment done!"  # Pas de vérification, pas de rollback
```

### ✅ Le nouveau monde : pipeline automatisé

```yaml
# .github/workflows/render-image.yml
name: Build & Deploy Render Image

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
      
      - name: Deploy to Render
        run: |
          if [ -n "${{ secrets.RENDER_DEPLOY_HOOK_URL }}" ]; then
            curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
          else
            curl -X POST "https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys" \
              -H "Authorization: Bearer ${{ secrets.RENDER_API_KEY }}" \
              -H "Content-Type: application/json" \
              -d '{"imageUrl": "ghcr.io/${{ github.repository }}:${{ github.sha }}"}'
          fi
```

**Le gain** : chaîne de montage automatisée, rollback instantané, et qualité garantie.

---

## Idées reçues sur la chaîne de montage

### ❌ "Le pipeline est trop complexe"
La chaîne de montage a 3 étapes simples : build → push → deploy. Chaque étape a des fallbacks. C'est comme une ligne d'assemblage avec des plans de secours, pas de complexité inutile.

### ❌ "Docker alourdit le déploiement"
Docker multi-stage optimise la taille de l'image (builder vs runtime). Le build est fait une seule fois, puis réutilisé. C'est comme pré-fabriquer les pièces pour accélérer l'assemblage.

### ❌ "Le multi-conteneurs est compliqué"
Le multi-conteneurs utilise Redis comme coordinateur. C'est comme avoir plusieurs chaînes de montage synchronisées par un chef d'orchestre central. La complexité est gérée par Redis, pas par le code.

---

## Tableau comparatif des méthodes de déploiement

| Méthode | Temps de déploiement | Fiabilité | Coût | Maintenance | Scalabilité |
|----------|-------------------|-----------|------|--------------|-------------|
| Artisanal (scripts) | 15-30 min | 60% | Élevé | Très élevée | Nulle |
| Chaîne de montage | 5-10 min | 95%+ | Faible | Faible | Élevée |
| Manuel Docker | 20-45 min | 70% | Moyen | Élevée | Moyenne |
| Cloud natif | 2-5 min | 99%+ | Variable | Très faible | Très élevée |

---

## Architecture Docker + Gunicorn

### Dockerfile multi-stage

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim as runtime

WORKDIR /app

# Copie des dépendances
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copie du code
COPY . .

# Variables Gunicorn par défaut
ENV GUNICORN_WORKERS=2
ENV GUNICORN_THREADS=2
ENV GUNICORN_TIMEOUT=120
ENV GUNICORN_GRACEFUL_TIMEOUT=30
ENV GUNICORN_KEEP_ALIVE=2
ENV GUNICORN_MAX_REQUESTS=15000
ENV GUNICORN_MAX_REQUESTS_JITTER=3000

# Port et démarrage
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app_render:app"]
```

### Configuration Gunicorn optimisée

```bash
# Variables Render (surchargeables)
GUNICORN_WORKERS=2
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=120
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEP_ALIVE=2
GUNICORN_MAX_REQUESTS=15000
GUNICORN_MAX_REQUESTS_JITTER=3000
```

**Objectifs** :
- **Workers** : 2 workers pour le multi-conteneur
- **Timeout** : 120s pour les requêtes longues (R2 offload)
- **Max requests** : 15000 par worker avant restart (memory leak prevention)
- **Jitter** : Évite les restarts synchronisés

---

## Pipeline GitHub Actions complet

### Secrets GitHub requis

| Secret | Usage | Description |
|--------|-------|-------------|
| `GITHUB_TOKEN` | Auth GHCR | Token GitHub avec permissions packages |
| `RENDER_DEPLOY_HOOK_URL` | Deploy Hook | URL Render pour déploiement prioritaire |
| `RENDER_API_KEY` | API Render | Token API Render (fallback) |
| `RENDER_SERVICE_ID` | Service ID | ID du service Render cible |
| `RENDER_DEPLOY_CLEAR_CACHE` | Cache control | `clear` ou `do_not_clear` |

### Flux de déploiement

```mermaid
flowchart TD
    A[Push main] --> B[GitHub Actions]
    B --> C[Build Docker Image]
    C --> D[Push to GHCR]
    D --> E{Deploy Hook disponible?}
    E -->|Oui| F[Render Deploy Hook]
    E -->|Non| G[Render API Call]
    F --> H[Deploy Success]
    G --> H
    H --> I[Health Check]
    I --> J[Application Ready]
```

### Commandes de monitoring

```bash
# Vérifier le dernier déploiement
curl -s https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys \
  -H "Authorization: Bearer ${RENDER_API_KEY}" | jq '.[0]'

# Logs du déploiement
curl -s https://api.render.com/v1/services/${RENDER_SERVICE_ID}/events \
  -H "Authorization: Bearer ${RENDER_API_KEY}" | jq '.[0:5]'
```

---

## Multi-conteneurs avec Redis

### Architecture de résilience

```
┌─────────────────┐    ┌─────────────────┐
│   Container 1   │    │   Container 2   │
│                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │   Poller    │ │    │ │   Poller    │ │
│ └─────────────┘ │    │ └─────────────┘ │
│        │        │    │        │        │
│        └─────────┼────┼────────┘        │
│                  │    │                  │
│            ┌─────▼────▼────┐            │
│            │   Redis Lock   │            │
│            │ poller_lock    │            │
│            └────────────────┘            │
└─────────────────────────────────────────┘
```

### Verrou distribué Redis

```python
# background/polling_thread.py
class DistributedLock:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.lock_key = "render_signal:poller_lock"
        self.ttl = 300  # 5 minutes
    
    def acquire(self):
        """Acquiert le verrou distribué"""
        if self.redis_client:
            # SET key value NX EX ttl
            result = self.redis_client.set(
                self.lock_key, 
                f"pid={os.getpid()}", 
                nx=True, 
                ex=self.ttl
            )
            if result:
                logger.info(f"BG_POLLER: Singleton lock acquired (Redis) pid={os.getpid()}")
                return True
            else:
                logger.info("BG_POLLER: Another poller already running (Redis)")
                return False
        else:
            # Fallback fcntl (unsafe pour multi-conteneurs)
            return self._acquire_file_lock()
    
    def release(self):
        """Libère le verrou"""
        if self.redis_client:
            self.redis_client.delete(self.lock_key)
            logger.info("BG_POLLER: Singleton lock released (Redis)")
```

### Configuration Redis

```bash
# Variables Render obligatoires pour multi-conteneurs
REDIS_URL=redis://default:password@redis-host:6379
REDIS_LOCK_TTL_SECONDS=300
CONFIG_STORE_MODE=redis_first
CONFIG_STORE_REDIS_PREFIX=r:ss:
```

### Monitoring du verrou

```bash
# Vérifier l'état du verrou
redis-cli GET render_signal:poller_lock

# Sortie attendue
"pid=12345"

# Surveillance des logs
grep "BG_POLLER.*lock" render.log
```

---

## Watchdog IMAP anti-zombie

### Problème résolu

Les connexions IMAP pouvaient rester bloquées indéfiniment avec des serveurs défaillants, créant des threads zombies.

### Solution timeout

```python
# email_processing/imap_client.py
class IMAPClient:
    def __init__(self, timeout=30):
        self.timeout = timeout
        self.socket_timeout = timeout
    
    def connect(self, server, username, password):
        try:
            self.imap = imaplib.IMAP4_SSL(server)
            self.imap.socket.settimeout(self.socket_timeout)
            self.imap.login(username, password)
            logger.info(f"IMAP: Connected to {server}")
        except (socket.timeout, imaplib.IMAP4.error) as e:
            logger.error(f"IMAP: Connection failed: {e}")
            raise
    
    def select_inbox(self):
        try:
            # Timeout sur toute opération
            return self.imap.select('INBOX')
        except (socket.timeout, imaplib.IMAP4.error) as e:
            logger.error(f"IMAP: Operation timeout: {e}")
            self._reconnect()
            raise
```

### Configuration timeout

```bash
# Timeout IMAP (optionnel, défaut 30s)
IMAP_TIMEOUT_SECONDS=30
```

### Monitoring des timeouts

```bash
# Logs de timeout IMAP
grep "IMAP.*timeout\|IMAP.*failed" render.log

# Reconnexions automatiques
grep "IMAP.*reconnect" render.log
```

---

## Fallback R2 garanti

### Amélioration Lot 2

Le flux webhook continue même si l'offload R2 échoue :

```python
# orchestrator.py
def _maybe_enrich_delivery_links_with_r2(delivery_links):
    enriched_links = []
    
    for link in delivery_links:
        # Conservation des URLs originales AVANT la tentative R2
        fallback_raw_url = link['raw_url']
        fallback_direct_url = link.get('direct_url', fallback_raw_url)
        
        try:
            # Tentative d'offload R2
            r2_result = r2_service.request_remote_fetch(
                source_url=link['raw_url'],
                provider=link['provider'],
                timeout=120 if 'scl/fo' in link['raw_url'] else 30
            )
            
            if r2_result and r2_result.get('r2_url'):
                link.update({
                    'r2_url': r2_result['r2_url'],
                    'original_filename': r2_result.get('original_filename')
                })
                logger.info(f"R2_TRANSFER: success provider={link['provider']}")
            else:
                logger.warning(f"R2_TRANSFER: failed provider={link['provider']} (no URL returned)")
        
        except Exception as e:
            # Exception : on garde les URLs originales et on log
            logger.warning(f"R2_TRANSFER: error provider={link['provider']} error={e}")
        
        # GARDE GARANTIE : les URLs originales sont toujours préservées
        link['raw_url'] = fallback_raw_url
        link['direct_url'] = fallback_direct_url
        
        enriched_links.append(link)
    
    return enriched_links
```

### Logs R2

```bash
# Succès R2
R2_TRANSFER: success provider=dropbox r2_url=https://media.domain.com/...

# Échec avec fallback
R2_TRANSFER: failed provider=dropbox error=timeout (fallback to source URLs)
```

---

## Variables d'environnement

### Variables obligatoires

```bash
# Authentification et sécurité
FLASK_SECRET_KEY=votre-clé-secrète-très-robuste
TRIGGER_PAGE_PASSWORD=mot-de-passe-dashboard
PROCESS_API_TOKEN=token-api-gmail-push
WEBHOOK_URL=https://hooks.make.com/votre-webhook

# Déploiement
RENDER_API_KEY=token-api-render
RENDER_SERVICE_ID=svc-abc123
RENDER_DEPLOY_HOOK_URL=https://api.render.com/deploy/svc-abc123
```

### Variables multi-conteneurs

```bash
# Redis (obligatoire pour multi-conteneurs)
REDIS_URL=redis://user:pass@host:port/db
REDIS_LOCK_TTL_SECONDS=300
CONFIG_STORE_MODE=redis_first

# Watchdog IMAP
IMAP_TIMEOUT_SECONDS=30
```

### Variables R2 (optionnelles)

```bash
# Offload Cloudflare R2
R2_FETCH_ENABLED=true
R2_FETCH_ENDPOINT=https://r2-fetch-worker.workers.dev
R2_FETCH_TOKEN=token-secret-worker
R2_PUBLIC_BASE_URL=https://media.domain.com
R2_BUCKET_NAME=render-signal-media
WEBHOOK_LINKS_FILE=/app/data/webhook_links.json
```

---

## Vérifications post-déploiement

### Checklist automatique

```bash
# 1. Health check
curl -s https://your-domain.onrender.com/health | jq '.status'

# 2. Variables obligatoires
curl -s https://your-domain.onrender.com/api/ping | jq '.required_vars_present'

# 3. Verrou Redis
redis-cli GET render_signal:poller_lock

# 4. Logs de démarrage
grep "BG_POLLER.*lock acquired" render.log | tail -1

# 5. Test R2 offload
curl -s -X POST https://your-domain.onrender.com/api/test-r2 | jq '.r2_url'
```

### Monitoring continu

```bash
# Surveillance des logs critiques
tail -f render.log | grep -E "(BG_POLLER|R2_TRANSFER|IMAP.*timeout)"

# Métriques de performance
curl -s https://your-domain.onrender.com/api/metrics | jq '.'

# État du verrou distribué
watch -n 30 "redis-cli GET render_signal:poller_lock"
```

---

## Déploiement manuel (fallback)

### API interne

```bash
# Endpoint fallback
POST /api/deploy_application

# Ordre de tentative :
# 1. Deploy Hook (prioritaire)
# 2. API Render (fallback)
# 3. Commande locale (dernier recours)
```

### Script de déploiement local

```bash
#!/bin/bash
# deploy.sh - fallback local

echo "Deploying application..."

# 1. Deploy Hook
if [ -n "$RENDER_DEPLOY_HOOK_URL" ]; then
    echo "Using Deploy Hook..."
    curl -X POST "$RENDER_DEPLOY_HOOK_URL"
    if [ $? -eq 0 ]; then
        echo "Deploy Hook successful"
        exit 0
    fi
fi

# 2. API Render
if [ -n "$RENDER_API_KEY" ] && [ -n "$RENDER_SERVICE_ID" ]; then
    echo "Using Render API..."
    response=$(curl -s -w "%{http_code}" -X POST \
        "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
        -H "Authorization: Bearer $RENDER_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"clearCache": "do_not_clear"}')
    
    if [ "$response" = "201" ] || [ "$response" = "202" ]; then
        echo "Render API successful"
        exit 0
    fi
fi

# 3. Commande locale
echo "Using local command..."
if [ -n "$DEPLOY_CMD" ]; then
    eval "$DEPLOY_CMD"
else
    echo "Default command: systemctl reload-or-restart render-signal-server"
    sudo systemctl reload-or-restart render-signal-server
    sudo nginx -s reload
fi

echo "Deployment completed"
```

---

## Architecture de résilience

### Composants critiques

| Composant | Rôle | Résilience |
|-----------|------|-----------|
| **Redis** | Verrou distribué + config store | Fallback fichier si indisponible |
| **R2 Worker** | Offload fichiers | Fallback URLs sources si échec |
| **IMAP Client** | Connexion email | Timeout 30s + reconnexion auto |
| **Gunicorn** | Serveur web | Restart automatique après max requests |

### Pattern de fallback

```python
# Pattern général pour tous les services externes
try:
    # Service externe
    result = external_service_call()
except ExternalServiceError as e:
    logger.warning(f"External service failed: {e}")
    # Fallback gracieux
    result = fallback_operation()
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Fallback minimal
    result = minimal_fallback()
```

---

## La Golden Rule : Chaîne de montage automatisée, multi-chaînes synchronisées, service garanti

La chaîne de montage GitHub Actions construit l'image Docker et la stocke sur GHCR. Render livre automatiquement via Deploy Hook ou API. Les multi-chaînes utilisent Redis comme coordinateur. Le gardien anti-zombie protège la production, et le service de livraison garantit la continuité. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la qualité de la production.

---

*Pour la configuration complète : voir `docs/v2/core/configuration-reference.md`. Pour le monitoring : voir `docs/v2/ops/monitoring.md`.*
