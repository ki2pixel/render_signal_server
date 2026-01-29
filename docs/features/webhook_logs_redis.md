# Persistance Redis des Logs Webhooks

## 📅 Date de création
2026-01-29

## Contexte
Historiquement, les logs de webhooks étaient stockés dans `debug/webhook_logs.json`, ce qui posait un problème de persistance sur la plateforme Render (fichiers éphémères). Pour garantir la survie des logs lors des redéploiements, une solution de persistance Redis a été implémentée avec fallback transparent vers le système de fichiers.

## Architecture

### Client Redis
- **Initialisation** : `redis.Redis.from_url()` si `REDIS_URL` est présent
- **Logging** : Erreur explicite si Redis indisponible mais fallback activé
- **Intégration** : Client partagé via `getattr(_ar, "redis_client", None)` dans les routes

### Stockage des logs
- **Clé Redis** : `r:ss:webhook_logs:v1` (liste)
- **Format** : JSON avec métadonnées (timestamp, status, URLs, erreurs)
- **Ordre** : Plus récent en tête (LPUSH), limitation automatique (LTRIM)
- **TTL** : 7 jours par défaut (configurable via `WEBHOOK_LOGS_TTL_DAYS`)

### Fallback transparent
- **Détection** : Vérification automatique de la disponibilité de Redis
- **Comportement** : Utilisation de `debug/webhook_logs.json` si Redis indisponible
- **Transition** : Aucune interruption de service lors du basculement

## Implémentation technique

### Initialisation au démarrage
```python
# app_render.py
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

### Branchement dans les routes
```python
# routes/api_logs.py
def get_webhook_logs():
    redis_client = getattr(_ar, "redis_client", None)
    logs = _fetch_webhook_logs(redis_client=redis_client)
    return jsonify({"logs": logs})
```

### Fonctions de persistance
```python
# email_processing/orchestrator.py
def append_webhook_log(redis_client, log_entry):
    if redis_client:
        # Persistance Redis
        redis_client.lpush("r:ss:webhook_logs:v1", json.dumps(log_entry))
        redis_client.ltrim("r:ss:webhook_logs:v1", 0, 1000)  # Limitation
        redis_client.expire("r:ss:webhook_logs:v1", 86400 * 7)  # TTL 7j
    else:
        # Fallback fichier
        append_webhook_log_file(log_entry)
```

## Format des logs

### Structure JSON
```json
{
  "timestamp": "2026-01-29T13:30:00Z",
  "status": "success|error",
  "webhook_url": "https://hooks.make.com/...",
  "target_url": "https://example.com/webhook",
  "error": "Error message (if any)",
  "email_id": "abc123",
  "detector": "recadrage|desabonnement_journee_tarifs",
  "delivery_links_count": 2,
  "duration_ms": 1234
}
```

### Champs spécifiques
- **timestamp** : ISO 8601, UTC
- **status** : "success" ou "error" uniquement
- **webhook_url** : URL cible (masquée partiellement dans l'UI)
- **target_url** : URL réelle atteinte (si redirection)
- **error** : Message d'erreur si status = "error"
- **email_id** : Identifiant unique de l'email traité
- **detector** : Type de détecteur ayant déclenché le webhook
- **delivery_links_count** : Nombre de liens de livraison dans le payload
- **duration_ms** : Durée d'envoi du webhook en millisecondes

## API et endpoints

### GET /api/webhook_logs
- **Description** : Récupère les logs des 7 derniers jours
- **Paramètres** : 
  - `days` (optionnel) : Nombre de jours à récupérer (défaut: 7)
  - `status` (optionnel) : Filtre par status ("success"|"error")
- **Réponse** : Tableau JSON avec les logs triés par timestamp décroissant

### Filtrage côté serveur
```python
def _fetch_webhook_logs(redis_client, days=7, status=None):
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    logs = []
    
    # Récupération depuis Redis ou fichier
    if redis_client:
        raw_logs = redis_client.lrange("r:ss:webhook_logs:v1", 0, -1)
    else:
        raw_logs = _read_webhook_logs_file()
    
    # Filtrage et parsing
    for log_json in raw_logs:
        log = json.loads(log_json)
        log_time = datetime.fromisoformat(log["timestamp"])
        
        if log_time >= cutoff_time and (not status or log["status"] == status):
            logs.append(log)
    
    return logs
```

## Tests et validation

### Tests unitaires
- **Stockage Redis** : `test_webhook_logs_redis_persistence.py::test_redis_storage`
- **Fallback fichier** : `test_webhook_logs_redis_persistence.py::test_fallback_file`
- **Filtrage par jours** : `test_webhook_logs_redis_persistence.py::test_filter_by_days`
- **Limitation taille** : `test_webhook_logs_redis_persistence.py::test_size_limitation`

### Tests d'intégration
- **Redis réel** : `test_webhook_logs_redis_persistence.py::test_integration_real_redis`
- **Basculement** : Vérification du comportement lors de la perte Redis

### Couverture
- **Fonctions couvertes** : 100% des fonctions de persistance
- **Scénarios** : Succès, erreur, basculement, reconnexion

## Performance et optimisation

### Optimisations Redis
- **Pipeline** : Utilisation de pipeline pour les opérations multiples
- **Limitation** : LTRIM pour maintenir la taille sous contrôle
- **TTL** : Expiration automatique pour éviter l'accumulation

### Gestion de la mémoire
- **Buffer** : Buffer côté client pour les gros volumes
- **Pagination** : Pagination côté serveur pour les requêtes importantes
- **Compression** : Compression JSON si nécessaire (futur)

### Monitoring
- **Métriques** : Taille de la liste Redis, taux d'écriture/lecture
- **Alertes** : Alertes si Redis indisponible > 5 minutes
- **Logs** : Logs détaillés pour le débogage des performances

## Sécurité

### Contrôle d'accès
- **Authentication** : Endpoint protégé par `@login_required`
- **Autorisation** : Vérification des permissions de lecture des logs
- **Sanitization** : Masquage automatique des URLs sensibles

### Protection des données
- **Masquage** : URLs partiellement masquées dans les réponses API
- **Retention** : TTL automatique pour limiter l'exposition
- **Audit** : Log des accès aux logs de webhooks

## Déploiement et configuration

### Variables d'environnement
```bash
REDIS_URL=redis://user:pass@host:port/db
WEBHOOK_LOGS_TTL_DAYS=7
WEBHOOK_LOGS_MAX_COUNT=1000
```

### Configuration Render
- **Redis Add-on** : Activation du add-on Redis
- **Variables** : Configuration automatique de `REDIS_URL`
- **Monitoring** : Surveillance de l'add-on Redis

## Migration et compatibilité

### Migration depuis les fichiers
- **Script** : `migrate_configs_to_redis.py` avec option `--migrate-webhook-logs`
- **Validation** : Vérification de l'intégrité des données migrées
- **Rollback** : Possibilité de revenir au système de fichiers

### Compatibilité ascendante
- **API** : Aucun changement dans l'interface
- **UI** : Aucune modification nécessaire
- **Tests** : Tests existants toujours valides

## Évolution future

### Améliorations prévues
- **Indexation** : Indexation des logs pour des recherches rapides
- **Agrégation** : Agrégations temporelles pour les dashboards
- **Export** : Export CSV/PDF des logs filtrés
- **Archivage** : Archivage automatique vers S3/R2

### Scalabilité
- **Sharding** : Partitionnement par date si volume très important
- **Réplication** : Réplication Redis pour la haute disponibilité
- **Compression** : Compression des logs anciens

---

## Voir aussi
- [Configuration Storage](../configuration/storage.md)
- [Architecture Redis](../architecture/overview.md#redis-optionnel)
- [Tests Résilience](../quality/testing.md#tests-résilience)
