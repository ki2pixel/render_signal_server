# Configuration Reference

**TL;DR**: 4 variables obligatoires au démarrage, Redis pour la persistence, et tout le reste est optionnel avec des valeurs par défaut sûres.

---

## Le problème : la configuration éparpillée

J'ai ouvert un projet où les configurations étaient partout : variables d'environnement, fichiers JSON, globals Python modifiés au runtime. Pire encore, certaines variables étaient "optionnelles" mais le code plantait si elles manquaient.

Le déploiement sur Render ? Un cauchemar. Chaque environnement avait ses propres variables, et il était impossible de savoir lesquelles étaient vraiment nécessaires.

---

## La solution : panneau électrique centralisé

Pensez à la configuration comme un panneau électrique : 4 disjoncteurs obligatoires (variables critiques) protègent tout le système, des interrupteurs modulaires (services) contrôlent chaque zone, et des fusibles de sécurité (validations) empêchent les surcharges. Redis est le tableau principal qui synchronise toutes les zones.

### ❌ L'ancien monde : câblage désordonné

```python
# ANTI-PATTERN dans app_render.py
webhook_url = os.environ.get('WEBHOOK_URL', 'https://default.com')  # Silent fallback
if not webhook_url:
    logger.warning("Missing webhook URL")  # Warning silencieux
```

### ✅ Le nouveau monde : tableau électrique sécurisé

```python
# config/settings.py
def _get_required_env(key):
    value = os.environ.get(key)
    if not value:
        logger.error(f"Missing required environment variable: {key}")
        raise ValueError(f"Missing required environment variable: {key}")
    return value

# Validation au démarrage
FLASK_SECRET_KEY = _get_required_env('FLASK_SECRET_KEY')
TRIGGER_PAGE_PASSWORD = _get_required_env('TRIGGER_PAGE_PASSWORD')
PROCESS_API_TOKEN = _get_required_env('PROCESS_API_TOKEN')
WEBHOOK_URL = _get_required_env('WEBHOOK_URL')
```

**Résultat** : le système refuse de démarrer si un disjoncteur critique est manquant. L'erreur est explicite et immédiate, comme un tableau électrique qui refuse de s'allumer sans protection.

---

## Idées reçues sur le tableau électrique

### ❌ "Les fallbacks sont dangereux"
Les fallbacks sont des fusibles : si Redis tombe, le système continue en mode dégradé avec les fichiers locaux. C'est une sécurité, pas une faiblesse. Le tableau électrique a toujours des circuits de secours.

### ❌ "La validation au démarrage bloque le déploiement"
La validation au démarrage empêche les déploiements cassés. Mieux vaut un échec immédiat qu'un système en production qui plante silencieusement. C'est comme tester les disjoncteurs avant de mettre le courant.

### ❌ "Les variables optionnelles créent de la complexité"
Les variables optionnelles ont des valeurs par défaut sûres. Le tableau électrique n'exige que les disjoncteurs critiques; le reste est des options configurables avec des valeurs par défaut sécurisées.

---

## Tableau des approches de configuration

| Approche | Validation | Multi-conteneurs | Performance | Sécurité | Résilience |
|----------|------------|------------------|--------------|----------|------------|
| Variables seules | Nulle | Impossible | Maximale | Faible | Nulle |
| Fichiers JSON | Faible | Difficile | Moyenne | Moyenne | Faible |
| Services + Redis | Élevée | Excellente | Optimisée | Élevée | Élevée |
| Microservices | Variable | Excellente | Variable | Variable | Très élevée |

---

## Disjoncteurs obligatoires : les 4 piliers

| Disjoncteur | Protection | Usage |
|-------------|-----------|-------|
| `FLASK_SECRET_KEY` | Sessions + signatures Magic Link | Sécurité |
| `TRIGGER_PAGE_PASSWORD` | Accès dashboard UI | Authentification |
| `PROCESS_API_TOKEN` | Apps Script → `/api/ingress/gmail` | Ingestion |
| `WEBHOOK_URL` | Destination webhooks sortants | Intégration |

Ces 4 disjoncteurs sont validés par `_get_required_env()` qui lève `ValueError` au démarrage. Les tests dans `tests/test_settings_required_env.py` couvrent tous les scénarios.

---

## Services de configuration : le tableau électrique Redis-first

### AppConfigStore : le tableau principal

```python
class AppConfigStore:
    def __init__(self):
        self._redis_client = None
        if REDIS_URL:
            self._redis_client = redis.Redis.from_url(REDIS_URL)
    
    def get_config_json(self, key):
        # 1. Priorité Redis
        if self._redis_client:
            try:
                data = self._redis_client.get(f"r:ss:{key}:v1")
                if data:
                    return json.loads(data)
            except RedisError:
                logger.warning(f"Redis failed for {key}, falling back")
        
        # 2. Fallback fichier
        return self._load_from_file(key)
```

**Les circuits gérés** : `runtime_flags`, `webhook_config`, `processing_prefs`, `routing_rules`, `magic_link_tokens`.

### Interrupteurs singletons avec cache

Tous les services de configuration sont des interrupteurs singletons avec cache court :

```python
class WebhookConfigService:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 30  # secondes
        self._app_config_store = AppConfigStore()
    
    def get_config(self):
        if self._is_cache_expired():
            self._cache = self._app_config_store.get_config_json("webhook_config")
        return self._cache
```

**Avantages** :
- Performances : pas de lecture disque à chaque appel
- Fraîcheur : cache de 30s maximum
- Résilience : fallback fichier si Redis down
- Sécurité : chaque interrupteur protège sa zone

---

## Circuits par zone fonctionnelle

### Zone Sécurité & Accès

| Disjoncteur | Description | Réglage par défaut |
|-------------|-------------|------------------|
| `FLASK_SECRET_KEY` | Clé HMAC pour sessions et Magic Links | **Obligatoire** |
| `TRIGGER_PAGE_PASSWORD` | Mot de passe dashboard | **Obligatoire** |
| `MAGIC_LINK_TTL_SECONDS` | Durée vie magic links | `900` (15min) |
| `MAGIC_LINK_TOKENS_FILE` | Stockage tokens magic links | `./magic_link_tokens.json` |

**Le pattern Magic Link** :
```python
# Génération
token = generate_hmac_token(flask_secret_key, email, expires_at)
# Stockage JSON avec verrou RLock
magic_link_service.save_token(token, email, expires_at)
# Validation
token_data = magic_link_service.consume_token(token)
if token_data and not token_data['expired']:
    create_flask_session(token_data['email'])
```

### Zone Ingestion Gmail Push

| Disjoncteur | Description | Réglage par défaut |
|-------------|-------------|------------------|
| `PROCESS_API_TOKEN` | Token Bearer pour `/api/ingress/gmail` | **Obligatoire** |
| `GMAIL_SENDER_ALLOWLIST` | Expéditeurs autorisés (CSV) | Vide = tous |
| `MAX_HTML_BYTES` | Limite parsing HTML anti-OOM | `1048576` (1MB) |

**Flow Gmail Push** :
```python
# POST /api/ingress/gmail
if not auth_service.verify_api_key_from_request(request):
    return jsonify({"success": False}), 401

# Validation allowlist
if sender not in GMAIL_SENDER_ALLOWLIST:
    logger.info(f"Sender {sender} not in allowlist, marking as processed")
    return jsonify({"success": True, "status": "skipped"}), 200
```

### Zone Webhooks Sortants

| Disjoncteur | Description | Réglage par défaut |
|-------------|-------------|------------------|
| `WEBHOOK_URL` | URL webhook personnalisé | **Obligatoire** |
| `WEBHOOK_SSL_VERIFY` | Vérification TLS | `true` |
| `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` | Envoi sans liens détectés | `false` |

**Validation stricte dans WebhookConfigService** :
```python
def validate_webhook_url(self, url):
    if not url.startswith('https://'):
        raise ValueError("Webhook URLs must use HTTPS")
    if not validators.url(url):
        raise ValueError("Invalid webhook URL format")
    return normalize_make_webhook_url(url)  # Make.com si applicable
```

### Zone Offload Cloudflare R2

| Disjoncteur | Description | Réglage par défaut |
|-------------|-------------|------------------|
| `R2_FETCH_ENABLED` | Active offload | `false` |
| `R2_FETCH_ENDPOINT` | URL Worker Cloudflare | Non défini |
| `R2_FETCH_TOKEN` | Token `X-R2-FETCH-TOKEN` | Non défini |
| `R2_PUBLIC_BASE_URL` | CDN public R2 | Non défini |
| `R2_FETCH_TIMEOUT_DROPBOX_SCL_FO` | Timeout Dropbox spécial | `120` |

**Pattern fallback garanti** :
```python
def upload_to_r2(self, source_url):
    try:
        return self._worker_client.fetch(source_url)
    except (WorkerTimeout, WorkerError):
        logger.warning(f"R2 offload failed, preserving original URL")
        return {"r2_url": None, "original_url": source_url}  # Fallback
```

### Zone Déploiement Render

| Disjoncteur | Description | Réglage par défaut |
|-------------|-------------|------------------|
| `RENDER_API_KEY` | Token API Render | Non défini |
| `RENDER_SERVICE_ID` | ID service Render | Non défini |
| `RENDER_DEPLOY_HOOK_URL` | URL Deploy Hook | Non défini |
| `RENDER_DEPLOY_CLEAR_CACHE` | Clear cache deploy | `do_not_clear` |

**Pipeline automatique** :
```yaml
# .github/workflows/render-image.yml
- name: Deploy to Render
  run: |
    if [ "$RENDER_DEPLOY_HOOK_URL" ]; then
      curl -X POST "$RENDER_DEPLOY_HOOK_URL"
    else
      curl -X POST "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
        -H "Authorization: Bearer $RENDER_API_KEY"
    fi
```

---

## Préférences de traitement : la configuration dynamique

Les préférences vivent dans `processing_prefs.json` et sont modifiables à chaud via API :

```json
{
  "exclude_keywords": ["SPAM", "PUBLICITÉ"],
  "webhook_exclude_keywords": {
    "webhook1": ["TEST", "INTERNE"]
  },
  "require_attachments": false,
  "max_email_size_mb": 25,
  "retry_count": 2,
  "retry_delay_sec": 5,
  "webhook_timeout_sec": 30,
  "mirror_media_to_custom": true,
  "enable_subject_group_dedup": true
}
```

**API endpoints** :
- `GET /api/processing_prefs` - Lecture
- `POST /api/processing_prefs` - Mise à jour avec validation

**Validation côté serveur** :
```python
def validate_processing_prefs(self, prefs):
    if prefs.get('max_email_size_mb', 0) < 0:
        raise ValueError("max_email_size_mb must be positive")
    if prefs.get('retry_count', 0) < 0:
        raise ValueError("retry_count must be positive")
    # ... autres validations
```

---

## Interrupteurs Runtime : les commandes de service

Les flags runtime permettent d'activer/désactiver des fonctionnalités sans redémarrage :

```json
{
  "gmail_ingress_enabled": true,
  "debug_mode": false,
  "maintenance_mode": false,
  "force_email_processing": false
}
```

**Services concernés** :
- `RuntimeFlagsService` : gestion des flags
- `Gmail ingress` : respecte `gmail_ingress_enabled`
- Dashboard UI : toggle dans l'onglet "Outils"

**Pattern de vérification** :
```python
# Dans api_ingress.py
if not runtime_flags_service.get_flag('gmail_ingress_enabled'):
    logger.info("Gmail ingress disabled, returning 409")
    return jsonify({"success": False, "message": "Gmail ingress disabled"}), 409
```

---

## Fusibles de sécurité : les protections du tableau

| Fusible | Description | Pourquoi |
|--------|-------------|---------|
| `REDIS_URL` | URL Redis pour déduplication/locks | Multi-conteneur |
| `MAX_HTML_BYTES` | Limite parsing HTML | Anti-OOM |
| `ENABLE_BACKGROUND_TASKS` | Active tâches fond (legacy) | Contrôle déploiement |
| `DISABLE_EMAIL_ID_DEDUP` | Bypass déduplication | Debug uniquement |

**Verrou distribué Redis** :
```python
# Anti-doublon polling IMAP (legacy)
redis_lock = redis_client.setnx('render_signal:poller_lock', 'locked')
if not redis_lock:
    logger.info("Another poller is already running")
    return
```

---

## Secrets : jamais à exposer sur le tableau

Ces variables ne doivent **jamais** être dans le code ou le git :

- `FLASK_SECRET_KEY`
- `R2_FETCH_TOKEN`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ACCOUNT_ID`
- `CONFIG_API_TOKEN`
- `PROCESS_API_TOKEN`
- `TRIGGER_PAGE_PASSWORD`

**Pattern de sécurité** :
```python
# config/settings.py
def _get_required_env(key):
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value  # Jamais de log de la valeur elle-même
```

---

## Développement vs Production

### Development (`.env` local)

```bash
FLASK_SECRET_KEY=dev-secret-key-not-for-production
TRIGGER_PAGE_PASSWORD=admin
PROCESS_API_TOKEN=dev-token
WEBHOOK_URL=http://localhost:8080/webhook
REDIS_URL=redis://localhost:6379/0
R2_FETCH_ENABLED=false
```

### Production (variables Render)

```bash
FLASK_SECRET_KEY=${random-256-bit}
TRIGGER_PAGE_PASSWORD=${secure-password}
PROCESS_API_TOKEN=${random-64-char}
WEBHOOK_URL=https://webhook.example.com/endpoint
REDIS_URL=${redis-cloud-url}
R2_FETCH_ENABLED=true
R2_FETCH_TOKEN=${worker-token}
```

---

## La Golden Rule : Tableau électrique sécurisé, services centralisés

Les 4 disjoncteurs obligatoires sont validés au démarrage avec `ValueError`. Toute la configuration dynamique passe par des interrupteurs services avec Redis-first et fallback fichier. Les secrets ne sont jamais exposés. Le reste a des valeurs par défaut sûres. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la sécurité du tableau électrique.

---

## Checklist de mise en service

- [ ] 4 disjoncteurs obligatoires définis
- [ ] `FLASK_SECRET_KEY` est aléatoire et robuste
- [ ] `WEBHOOK_URL` est en HTTPS
- [ ] `PROCESS_API_TOKEN` est partagé avec Apps Script
- [ ] Redis configuré si multi-conteneur
- [ ] R2 configuré si offload activé
- [ ] Variables de développement désactivées en prod
