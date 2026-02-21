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

## AppConfigStore : le système de stockage unifié

### Architecture tri-niveaux : Redis → External → Fichier

Le système `AppConfigStore` implémente une hiérarchie de stockage robuste avec failover automatique :

```python
# config/app_config_store.py
class StorageHierarchy:
    PRIMARY = "redis"        # Performance, partage multi-conteneurs
    SECONDARY = "external"   # Héritage, compatibilité legacy
    TERTIARY = "file"        # Fallback local, persistance garantie
```

**Priorité configurable** :
```python
CONFIG_STORE_MODE=redis_first  # Redis → External → File
CONFIG_STORE_MODE=php_first    # External → Redis → File
```

### Clés de configuration gérées

| Clé | Usage | Format | Mise à jour |
|-----|-------|--------|-------------|
| `runtime_flags` | Flags runtime (Gmail ingress, debug, etc.) | JSON dict | API `/api/runtime-flags` |
| `webhook_config` | Configuration webhooks sortants | JSON dict | API `/api/webhooks/config` |
| `processing_prefs` | Préférences traitement emails | JSON dict | API `/api/processing_prefs` |
| `routing_rules` | Règles routage dynamique | JSON dict | API `/api/routing_rules` |
| `magic_link_tokens` | Tokens authentification temporaire | JSON dict | Service MagicLink |

### Pattern de lecture avec failover

```python
def get_config_json(key: str, file_fallback: Optional[Path] = None) -> Dict[str, Any]:
    mode = _store_mode()
    
    if mode == "redis_first":
        data = _redis_get_json(key)  # 1. Redis (performance)
        if isinstance(data, dict):
            return data
    
    # 2. External backend (PHP legacy)
    data = _external_config_get(base_url, api_token, key)
    if isinstance(data, dict):
        return data
    
    if mode == "php_first":
        data = _redis_get_json(key)  # 3. Redis (fallback)
        if isinstance(data, dict):
            return data
    
    # 4. File fallback (dernière ligne de défense)
    return _load_from_file(file_fallback) if file_fallback else {}
```

### Pattern d'écriture avec synchronisation

```python
def set_config_json(key: str, value: Dict[str, Any], file_fallback: Optional[Path] = None) -> bool:
    # 1. Tente Redis d'abord
    if _redis_set_json(key, value):
        return True
    
    # 2. Fallback external backend
    if _external_config_set(base_url, api_token, key, value):
        return True
    
    # 3. Dernière chance: fichier local
    return _save_to_file(file_fallback, value)
```

---

## Migration Redis : passage du fichier au stockage distribué

### Le problème : fichiers locaux non partageables

Avant Redis, chaque configuration vivait dans des fichiers JSON locaux :
- `debug/runtime_flags.json` pour les flags
- `debug/webhook_config.json` pour les webhooks  
- `debug/processing_prefs.json` pour les préférences

**Problèmes** :
- Pas de partage entre conteneurs Render
- Persistance uniquement locale
- Difficile à gérer en production multi-instances

### La solution : migration progressive vers Redis

```python
# Script de migration: migrate_configs_to_redis.py
def migrate_config_to_redis(key: str, file_path: Path):
    """Migre un fichier JSON vers Redis avec préservation."""
    
    # 1. Charge depuis fichier
    if not file_path.exists():
        return False
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 2. Sauvegarde en Redis
    config_store = AppConfigStore()
    success = config_store.set_config_json(key, data, file_fallback=file_path)
    
    if success:
        # 3. Backup du fichier original
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        shutil.copy2(file_path, backup_path)
        
        logger.info(f"Migrated {key} to Redis, backup at {backup_path}")
        return True
    
    return False
```

### Commandes de migration

```bash
# Migration complète
python migrate_configs_to_redis.py --all

# Migration sélective
python migrate_configs_to_redis.py --key runtime_flags
python migrate_configs_to_redis.py --key webhook_config

# Vérification post-migration
python scripts/check_config_store.py
```

### Rollback en cas de problème

```python
# En cas de problème Redis, rollback vers fichiers
def rollback_to_files():
    config_store = AppConfigStore()
    
    for key in ["runtime_flags", "webhook_config", "processing_prefs"]:
        # Récupère depuis Redis
        data = config_store.get_config_json(key)
        if data:
            # Restore fichier depuis Redis
            file_path = Path(f"debug/{key}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Rolled back {key} to file: {file_path}")
```

### Bénéfices post-migration

| Aspect | Avant (Fichiers) | Après (Redis) |
|--------|------------------|---------------|
| **Partage** | Local uniquement | Multi-conteneurs |
| **Performance** | I/O disque lent | Mémoire rapide |
| **Persistance** | Disque local | Base de données Redis |
| **Fiabilité** | Perte si crash conteneur | Sauvegarde automatique |
| **Monitoring** | Difficile | Métriques Redis intégrées |

### Variables de contrôle migration

```bash
# Contrôle du stockage
CONFIG_STORE_DISABLE_REDIS=false     # Active Redis
CONFIG_STORE_MODE=redis_first        # Priorité Redis
CONFIG_STORE_REDIS_PREFIX=r:ss:config:  # Namespace Redis

# Contrôle external backend (legacy)
EXTERNAL_CONFIG_BASE_URL=https://external-api.com
CONFIG_API_TOKEN=your-api-token
```

---

## Services consommateurs : l'intégration transparente

### Pattern d'usage dans les services

Tous les services de configuration suivent le même pattern d'intégration :

```python
class ExampleService:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 30  # secondes
        self._app_config_store = AppConfigStore()
    
    def get_config(self):
        now = time.time()
        
        # Cache hit rapide
        if (self._cache and 
            self._cache_timestamp and 
            (now - self._cache_timestamp) < self._cache_ttl):
            return self._cache
        
        # Cache miss: reload depuis AppConfigStore
        self._cache = self._app_config_store.get_config_json("example_config")
        self._cache_timestamp = now
        
        return self._cache
    
    def update_config(self, new_config):
        # Validation locale
        validated = self._validate_config(new_config)
        
        # Persistance via AppConfigStore
        success = self._app_config_store.set_config_json(
            "example_config", 
            validated, 
            file_fallback=self._file_path
        )
        
        if success:
            # Invalidation cache
            self._cache = None
            self._cache_timestamp = None
        
        return success
```

### Services migrés

- `RuntimeFlagsService` : `runtime_flags`
- `WebhookConfigService` : `webhook_config`  
- `MagicLinkService` : `magic_link_tokens`
- `RoutingRulesService` : `routing_rules`

**Tous utilisent AppConfigStore avec cache TTL 30s et fallback fichier.**

---

## Sécurité et audit du stockage

### Séparation des secrets

**Dans Redis** : configurations métier (flags, règles, préférences)
**Dans variables env** : secrets (clés API, tokens, mots de passe)

```python
# ✅ Correct : configs dans Redis
runtime_flags = {"gmail_ingress_enabled": true}
webhook_config = {"url": "https://webhook.com", "ssl_verify": true}

# ❌ Incorrect : secrets dans configs
webhook_config = {"url": "https://webhook.com", "api_key": "secret123"}
```

### Audit des accès

```python
# Logs d'audit (sans exposer valeurs sensibles)
logger.info(f"CONFIG: {key} updated by {user_id}")
logger.info(f"CONFIG: {key} read from {store_type}")  # redis/external/file

# Métriques
config_reads_total.labels(store=store_type, key=key).inc()
config_writes_total.labels(store=store_type, key=key).inc()
```

### Validation d'intégrité

```python
def validate_config_integrity():
    """Vérifie cohérence entre stores."""
    redis_data = _redis_get_json(key)
    file_data = _load_from_file(file_path)
    
    if redis_data != file_data:
        logger.warning(f"CONFIG_DRIFT: {key} differs between Redis and file")
        # Auto-sync si configuré
        if _env_bool("CONFIG_AUTO_SYNC", False):
            _redis_set_json(key, file_data)
```

---

## Monitoring et observabilité

### Métriques essentielles

- **Store usage** : % lectures par store (Redis vs External vs File)
- **Cache hit rate** : % cache hits par service (>90% attendu)
- **Migration status** : configs migrées vs fichiers restants
- **Error rates** : échecs lecture/écriture par store

### Alertes critiques

- **Redis unavailable** : bascule external/file (acceptable)
- **External backend down** : impact sur legacy (monitorer)
- **File writes failing** : problème persistance (critique)
- **Config drift detected** : incohérence stores (investiguer)

### Commandes de diagnostic

```bash
# État des stores
python scripts/check_config_store.py --verbose

# Statistiques Redis
redis-cli keys "r:ss:config:*"
redis-cli memory stats

# Validation intégrité
python scripts/check_config_store.py --integrity
```

---

## Évolutions futures (Q3 2026)

### Performance avancée

- **Cache distribué** : Redis Cluster pour haute disponibilité
- **Compression** : configs volumineuses compressées
- **Sharding** : séparation par domaine fonctionnel

### Fonctionnalités

- **Historique versions** : rollback configs par timestamp
- **AB testing** : variantes config par utilisateur/groupe
- **Hot reload** : modification configs sans restart

### Sécurité renforcée

- **Encryption at rest** : configs sensibles chiffrées
- **Audit trails** : historique complet modifications
- **RBAC configs** : permissions par clé/config

---

## La Golden Rule : Hiérarchie de stockage, migration progressive, failover garanti

AppConfigStore fournit une hiérarchie Redis-first avec fallbacks robustes. La migration des fichiers vers Redis se fait progressivement avec backup automatique. Chaque service utilise le même pattern cache TTL avec invalidation cohérente. Les secrets restent dans les variables d'environnement, les configs métier dans le store unifié.

Configuration centralisée = cohérence garantie = évolution simplifiée.

---

## Checklist de mise en service

- [ ] 4 disjoncteurs obligatoires définis
- [ ] `FLASK_SECRET_KEY` est aléatoire et robuste
- [ ] `WEBHOOK_URL` est en HTTPS
- [ ] `PROCESS_API_TOKEN` est partagé avec Apps Script
- [ ] Redis configuré si multi-conteneur
- [ ] AppConfigStore migré vers Redis (`migrate_configs_to_redis.py`)
- [ ] Variables de contrôle stockage définies (`CONFIG_STORE_MODE`, etc.)
- [ ] R2 configuré si offload activé
- [ ] Variables de développement désactivées en prod
- [ ] Services consommateurs utilisent AppConfigStore (cache TTL 30s)
- [ ] Monitoring stores configuré (`check_config_store.py`)
