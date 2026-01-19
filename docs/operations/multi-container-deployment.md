# Multi-Container Deployment Guide (Lot 2)

## Overview

Ce guide couvre le déploiement multi-conteneurs sur Render avec les améliorations de résilience du Lot 2 : verrou distribué Redis, watchdog IMAP, et fallback R2 garanti.

## Prérequis

- Service Render multi-conteneurs (Standard plan ou supérieur)
- Instance Redis (Render Redis ou externe)
- Configuration Lot 2 activée

## Configuration Redis

### Variables d'environnement

```bash
# Verrou distribué Redis (recommandé pour multi-conteneurs)
REDIS_URL=redis://user:pass@host:port/db
REDIS_LOCK_TTL_SECONDS=300

# Watchdog IMAP anti-zombie
IMAP_TIMEOUT_SECONDS=30
```

### Configuration Render Redis

1. **Créer une instance Redis** sur Render
2. **Récupérer l'URL** depuis le dashboard Render
3. **Configurer REDIS_URL** dans les variables d'environnement du service

```bash
# Exemple avec Render Redis
REDIS_URL=redis://default:password@redis-render-host:6379
```

## Verrou Distribué Redis

### Implémentation

Le verrou utilise Redis avec les caractéristiques suivantes :
- **Clé** : `render_signal:poller_lock`
- **TTL** : 5 minutes (300 secondes) par défaut
- **Token** : PID du processus pour traçabilité
- **Commande** : `SET key value NX EX ttl`

### Comportement

1. **Avec Redis** : Verrou distribué garanti
2. **Sans Redis** : Fallback fcntl avec WARNING
3. **Monitoring** : `redis-cli GET render_signal:poller_lock`

### Logs de surveillance

```bash
# Succès Redis
BG_POLLER: Singleton lock acquired (Redis) pid=12345

# Fallback fcntl
BG_POLLER: Using file-based lock (unsafe for multi-container deployments)
```

## Monitoring Multi-Conteneurs

### État du verrou

```bash
# Vérifier si le verrou est actif
redis-cli GET render_signal:poller_lock

# Sortie attendue
"pid=12345"

# ou nil si aucun verrou
(nil)
```

### Logs critiques

```bash
# Vérifier les logs de polling
grep "BG_POLLER:" render.log

# Surveiller les fallbacks
grep "unsafe for multi-container" render.log

# Timeout IMAP
grep "IMAP.*timeout" render.log
```

## Watchdog IMAP Anti-Zombie

### Problème résolu

Les connexions IMAP pouvaient rester bloquées indéfiniment avec des serveurs défaillants.

### Solution

- **Timeout par défaut** : 30 secondes
- **Configurable** : `IMAP_TIMEOUT_SECONDS`
- **Prévention** : Évite les threads zombies

### Configuration

```bash
# Timeout personnalisé (optionnel)
IMAP_TIMEOUT_SECONDS=45
```

### Monitoring

```bash
# Logs de timeout IMAP
grep "IMAP.*timeout\|IMAP.*failed" render.log

# Reconnexions automatiques
grep "IMAP.*reconnect" render.log
```

## Fallback R2 Garanti

### Amélioration Lot 2

Le flux webhook continue même si l'offload R2 échoue :

1. **Conservation URLs** : `raw_url`/`direct_url` maintenues
2. **Try/except large** : Capture toutes les exceptions
3. **Log WARNING** : Échec R2 journalisé mais flux continue
4. **Timeouts adaptatifs** : 120s Dropbox `/scl/fo/`, 15s par défaut

### Logs R2

```bash
# Succès R2
R2_TRANSFER: success url=... r2_url=...

# Échec avec fallback
R2_TRANSFER: failed url=... error=... (fallback to source URLs)
```

## Checklist de Déploiement

### Avant le déploiement

- [ ] Instance Redis créée et accessible
- [ ] `REDIS_URL` configuré dans les variables d'environnement
- [ ] `REDIS_LOCK_TTL_SECONDS` défini si nécessaire
- [ ] `IMAP_TIMEOUT_SECONDS` configuré si nécessaire
- [ ] Tests de connexion Redis validés

### Après le déploiement

- [ ] Vérifier logs "Singleton lock acquired (Redis)"
- [ ] Confirmer absence de logs "unsafe for multi-container"
- [ ] Tester le verrou avec `redis-cli GET render_signal:poller_lock`
- [ ] Surveiller les timeouts IMAP
- [ ] Valider le fallback R2 (simuler échec Worker)

### Monitoring continu

- [ ] Surveillance des logs WARNING R2
- [ ] Monitoring de l'état du verrou Redis
- [ ] Vérification des reconnexions IMAP
- [ ] Tests réguliers de basculement Redis→fcntl

## Dépannage

### Verrou Redis ne fonctionne pas

**Symptômes** :
- Logs "Using file-based lock (unsafe for multi-container)"
- Double polling possible

**Solutions** :
1. Vérifier `REDIS_URL` est correct
2. Tester la connexion Redis :
   ```bash
   redis-cli -u $REDIS_URL ping
   ```
3. Vérifier les permissions Redis

### Timeouts IMAP fréquents

**Symptômes** :
- Logs "IMAP timeout"
- Reconnexions excessives

**Solutions** :
1. Augmenter `IMAP_TIMEOUT_SECONDS`
2. Vérifier la stabilité du serveur IMAP
3. Surveiller la latence réseau

### Fallback R2 systématique

**Symptômes** :
- Logs "R2_TRANSFER: failed" fréquents
- Aucune économie de bande passante

**Solutions** :
1. Vérifier `R2_FETCH_TOKEN`
2. Tester le Worker Cloudflare directement
3. Surveiller les logs du Worker

## Architecture de Résilience

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

Cette architecture garantit qu'un seul poller s'exécute à travers tous les conteneurs, éliminant le risque de double traitement des emails.

## Redis comme backend central

### Config Store Redis-first
- **Service** : `config/app_config_store.py` avec support Redis-first
- **Modes** : `redis_first` (défaut) ou `php_first` via `CONFIG_STORE_MODE`
- **Préfixe** : Configurable via `CONFIG_STORE_REDIS_PREFIX` (défaut: "r:ss:config:")

### Configuration
```bash
# Redis (requis pour multi-conteneurs)
REDIS_URL=redis://redis-host:6379/0
CONFIG_STORE_MODE=redis_first

# Désactiver fallback fichiers (éphémères)
CONFIG_STORE_DISABLE_REDIS=false
```

### Configurations supportées
- `magic_link_tokens` : Tokens magic link permanents
- `polling_config` : Configuration IMAP et fenêtres horaires
- `processing_prefs` : Préférences de traitement des emails
- `webhook_config` : Configuration URLs webhooks et SSL

### Migration
Utiliser le script `migrate_configs_to_redis.py` :
```bash
# Migration avec vérification
python migrate_configs_to_redis.py --verify

# Redis obligatoire
python migrate_configs_to_redis.py --require-redis
```

### Health Checks
- `/health` : Vérifie Redis et services critiques
- Lock Redis : Monitoring via logs `WARNING Using file-based lock`

### Scalabilité
- **Horizontal** : Plusieurs instances Render autorisées
- **Partage** : Configs et état partagés via Redis
- **Fallback** : Si Redis indisponible, mode dégradé avec lock fichier
