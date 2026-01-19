# Stockage de la configuration

## Architecture de stockage

L'application utilise une architecture de stockage hiérarchique pour la persistance des configurations et des artefacts critiques :

1. **Backend JSON externe** (recommandé en production) – API PHP `config_api.php` utilisée par `WebhookConfigService`, `MagicLinkService`, etc. pour supporter les déploiements multi-workers (Render + serveur PHP).
2. **Fichiers locaux** (fallback pour le développement et compatibilité).
3. **MySQL** (déprécié, supprimé dans la version actuelle).

## Backend JSON externe

### Configuration requise

Pour activer le stockage externe, définissez ces variables d'environnement :

- `EXTERNAL_CONFIG_BASE_URL` : URL de base de l'API de configuration (ex: `https://votre-domaine.tld`)
- `CONFIG_API_TOKEN` : Jeton d'authentification pour l'API (doit correspondre à `CONFIG_API_TOKEN` dans `deployment/config/config_api.php`)

### Fichiers de configuration gérés

- **Webhooks** : Configuration des webhooks et fenêtres horaires
- **Préférences de traitement** : Règles de filtrage et de traitement des e-mails
- **Fenêtres horaires** : Configuration des plages d'exécution
- **Flags runtime** : Paramètres de débogage et fonctionnalités expérimentales
- **Magic Link tokens** : `MagicLinkService` lit/écrit la clé `magic_link_tokens` via l’API pour stocker les tokens permanents dans `deployment/data/app_config/magic_link_tokens.json`.

### Fonctionnement

1. **Ordre de priorité** :
   - L'application tente d'abord de se connecter au backend externe
   - En cas d'échec, elle utilise les fichiers locaux comme fallback
   - Une notification est journalisée en cas de basculement sur le mode fallback

2. **Mécanisme de cache** :
   - Les configurations sont mises en cache en mémoire après le premier chargement
   - Le cache est invalidé lors des opérations d'écriture
   - La synchronisation avec le stockage persistant est assurée automatiquement

3. **Sécurité** :
  - Authentification via token Bearer
  - Validation des données avant écriture
  - Chiffrement des données sensibles au repos (si configuré)

4. **Intégration applicative (services)** :
   - `WebhookConfigService` peut lire/écrire via le store externe si disponible, avec fallback fichier `debug/webhook_config.json` et cache mémoire TTL 60s (invalidation à l'update).
   - Les endpoints de fenêtre horaire (`/api/get_webhook_time_window`, `/api/set_webhook_time_window`) synchronisent best-effort `global_time_start/global_time_end` avec la clé `webhook_config` du store externe.
   - `MagicLinkService` interroge `config_api.php` pour la clé `magic_link_tokens` lorsque `EXTERNAL_CONFIG_BASE_URL` + `CONFIG_API_TOKEN` sont définis, avec fallback fichier JSON local si l’API est indisponible.

5. **Journalisation** :
   - Toutes les opérations de lecture/écriture sont journalisées
   - Les erreurs sont enregistrées avec un niveau de sévérité approprié

### Configuration du serveur PHP

1. Déployez les fichiers PHP dans votre hébergement web :
   - `deployment/public_html/config_api.php` → Point d'entrée de l'API
   - `deployment/config/config_api.php` → Configuration (à sécuriser hors du webroot)

2. Configurez le jeton d'API dans `deployment/config/config_api.php` :
   ```php
   define('CONFIG_API_TOKEN', 'votre_jeton_secret_ici');
   ```

3. Assurez-vous que le dossier de stockage est accessible en écriture par le serveur web :
   ```bash
   mkdir -p /chemin/vers/deployment/data/app_config
   chmod 775 /chemin/vers/deployment/data/app_config
   ```

## Fallback local

Si le backend externe n'est pas configuré ou n'est pas accessible, l'application utilise des fichiers JSON locaux dans le dossier `debug/` :

- `debug/webhook_config.json` - Configuration des webhooks
- `debug/processing_prefs.json` - Préférences de traitement
- `debug/webhook_time_window.json` - Fenêtres horaires des webhooks
- `debug/runtime_flags.json` - Paramètres d'exécution

### Comportement en mode fallback

- **Lecture** : Les fichiers locaux sont lus directement
- **Écriture** : Les modifications sont enregistrées dans les fichiers locaux
- **Synchronisation** : Aucune synchronisation automatique avec le backend externe n'est effectuée
- **Notification** : Un avertissement est affiché dans l'interface utilisateur


## Secrets et artefacts Gmail OAuth (deployment/)

Les éléments suivants sont gérés par l'écosystème PHP (`deployment/`) et doivent être sauvegardés/protégés :

- `deployment/data/env.local.php` — secrets OAuth (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, etc.).
- `deployment/data/gmail_oauth_last_check.json` — dernier statut de l'auto-check (`last_run_ts`, succès/échec, détails).
- `deployment/data/gmail_oauth_check_history.jsonl` — historique append-only de chaque auto-check (un JSON par ligne).

### Recommandations

- Restreindre les permissions (`chmod 600` ou équivalent) et conserver ces fichiers hors du webroot (`deployment/data/`).
- Inclure ces fichiers dans les plans de sauvegarde chiffrés. Ils contiennent des tokens OAuth et l'historique d'envoi.
- Surveiller l'existence/la fraîcheur de `gmail_oauth_last_check.json` pour détecter les auto-checks bloqués.
- En cas de rotation de secrets, mettre à jour `env.local.php` puis relancer un `POST action=dry-run` via `GmailOAuthTest.php` pour vérifier.


## Redis Config Store (2026-01-19)

### Architecture
- **Service** : `config/app_config_store.py` avec support Redis-first
- **Modes** : `redis_first` (défaut) ou `php_first` via `CONFIG_STORE_MODE`
- **Préfixe** : Configurable via `CONFIG_STORE_REDIS_PREFIX` (défaut: "r:ss:config:")

### Configuration
```bash
# Redis (recommandé pour multi-conteneurs)
REDIS_URL=redis://user:pass@host:port/db
CONFIG_STORE_MODE=redis_first
CONFIG_STORE_REDIS_PREFIX=r:ss:config:

# Fallback PHP (legacy)
EXTERNAL_CONFIG_BASE_URL=https://php-server.example.com
CONFIG_API_TOKEN=your_token
```

### Migration
Utiliser le script `migrate_configs_to_redis.py` :
```bash
# Dry-run pour vérification
python migrate_configs_to_redis.py --dry-run

# Migration avec vérification
python migrate_configs_to_redis.py --verify

# Redis obligatoire
python migrate_configs_to_redis.py --require-redis
```

### Vérification après migration
Un utilitaire dédié permet de lire les clés directement dans Redis et de vérifier leur structure :

```bash
python -m scripts.check_config_store

# Limiter aux préférences et afficher le JSON brut
python -m scripts.check_config_store --keys processing_prefs --raw
```

Le script retourne `0` si toutes les clés vérifiées sont présentes et valides, sinon `1`.

> **Depuis le dashboard** : un bouton « 📦 Migrer les configurations » (section « Migration configs → Redis ») déclenche `/api/migrate_configs_to_redis` sur le serveur Render et affiche le log retourné. À utiliser si l'accès CLI n'est pas disponible.

### Configurations supportées
- `magic_link_tokens` : Tokens magic link permanents
- `polling_config` : Configuration IMAP et fenêtres horaires
- `processing_prefs` : Préférences de traitement des emails
- `webhook_config` : Configuration URLs webhooks et SSL

### Comportement
- **Ordre de priorité** : Redis → PHP externe → fichiers locaux (selon mode)
- **Cache** : Client Redis avec décode_responses=True
- **Fallback** : Basculement automatique avec logging WARNING
- **Atomicité** : Opérations JSON avec sérialisation ensure_ascii=False

## Artefacts R2 Offload (deployment/)

L'offload Cloudflare R2 (côté Flask) persiste un historique des transferts dans :

- `deployment/data/webhook_links.json`

### Schéma supporté (mixte legacy + R2)

Ce fichier contient une liste d'objets et supporte **deux formats** pour la rétrocompatibilité :

#### Format R2 (nouveau, recommandé)
```json
{
  "source_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
  "r2_url": "https://media.yourdomain.com/dropbox/a1b2c3d4/e5f6g7h8/file.zip",
  "provider": "dropbox",
  "created_at": "2026-01-08T14:30:00.123456Z",
  "email_id": "md5-hash-email-id",
  "original_filename": "61 Camille.zip"
}
```

#### Format legacy (historique)
```json
{
  "url": "https://www.dropbox.com/s/abc123/file.zip?dl=0",
  "timestamp": "2025-10-17T10:30:00+02:00",
  "source": "webhook"
}
```

### Champs du format R2

- `source_url` (string, obligatoire) : URL source normalisée
- `r2_url` (string, obligatoire) : URL publique R2 du fichier transféré
- `provider` (string) : Nom du provider (`dropbox`, `fromsmash`, `swisstransfer`, `unknown`)
- `created_at` (string, ISO 8601) : Timestamp de création (UTC)
- `email_id` (string, optionnel) : ID de l'email source pour traçabilité
- `original_filename` (string, optionnel) : Nom de fichier d'origine extrait depuis Content-Disposition

### Utilisation du fichier

Ce fichier est utilisé par :

- **Backend Python** (`R2TransferService`) : pour conserver la relation `source_url` → `r2_url` et réutiliser les URLs R2 sur des emails futurs
- **Pages PHP de test** (`deployment/public_html/test.php`, `deployment/public_html/test-direct.php`) : pour afficher un diagnostic de conformité et les dernières entrées
- **JsonLogger PHP** : pour logger les paires R2 via `logR2LinkPair()` et `logDeliveryLinkPairs()`

### Gestion côté PHP

Le logger PHP (`deployment/src/JsonLogger.php`) gère automatiquement les deux formats :

```php
// Logger une paire R2 (nouveau format)
$jsonLogger->logR2LinkPair($sourceUrl, $r2Url, $provider, $emailId, $originalFilename);

// Logger les paires depuis delivery_links (mixte)
$jsonLogger->logDeliveryLinkPairs($deliveryLinks, $emailId);

// Logger une URL legacy (compatibilité)
$jsonLogger->logDropboxUrl($url, 'webhook');
```

### Rotation et maintenance

- **Rotation automatique** : Le fichier conserve les 1000 dernières entrées par défaut (`R2_LINKS_MAX_ENTRIES`)
- **Taille maximale** : 5 MB par défaut (`JSON_LOG_MAX_BYTES`)
- **Backup automatique** : En cas de dépassement, le fichier est archivé avec timestamp
- **Diagnostics** : Les pages PHP affichent le comptage par format (legacy vs R2) et par provider


## Dépannage

### Erreurs courantes

#### Erreurs d'authentification
- **Symptômes** : Erreurs 401 Unauthorized dans les logs
- **Solutions** :
  - Vérifiez que `CONFIG_API_TOKEN` correspond entre l'application et `deployment/config/config_api.php`
  - Vérifiez que le header `Authorization: Bearer` est correctement envoyé
  - Assurez-vous que l'horloge du serveur est synchronisée (NTP)

#### Problèmes de permissions
- **Symptômes** : Erreurs 500 ou échec d'écriture
- **Solutions** :
  - Vérifiez les permissions du dossier de stockage : `chmod 775 /chemin/vers/donnees`
  - Vérifiez le propriétaire des fichiers : `chown www-data:www-data /chemin/vers/donnees/*`
  - Consultez les logs d'erreurs PHP pour plus de détails

#### Problèmes de performance
- **Symptômes** : Lenteur du chargement de la configuration
- **Solutions** :
  - Activez le cache OPcache pour PHP
  - Vérifiez la latence réseau vers le serveur de configuration
  - Considérez l'utilisation d'un CDN pour les fichiers statiques

### Surveillance

#### Métriques clés
- Temps de réponse du backend de configuration
- Taux d'erreurs (4xx, 5xx)
- Taux d'utilisation du cache
- Fréquence des basculements en mode fallback

#### Alertes recommandées
- Plus de 3 échecs consécutifs du backend externe
- Temps de réponse > 1 seconde
- Taux d'erreur > 1% sur 5 minutes
- Utilisation du disque > 80% sur le volume de stockage

## Référence de l'API

### Lecture d'une configuration

```bash
curl -H "Authorization: Bearer VOTRE_TOKEN" \
  "https://votre-domaine.tld/config_api.php?key=webhook_config"
```

**Paramètres** :
- `key` (obligatoire) : Clé de configuration à récupérer (ex: `webhook_config`, `processing_prefs`)

**Réponse** :
```json
{
  "status": "success",
  "data": {
    "webhook_url": "https://exemple.com/webhook",
    "webhook_enabled": true,
    "time_window": {
      "start_hour": 8,
      "end_hour": 20,
      "active_days": [1, 2, 3, 4, 5]
    }
  },
  "timestamp": "2025-10-16T14:30:00Z"
}
```

### Écriture d'une configuration

```bash
curl -X POST \
  -H "Authorization: Bearer VOTRE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "webhook_config",
    "config": {
      "webhook_url": "https://exemple.com/webhook",
      "webhook_enabled": true,
      "time_window": {
        "start_hour": 8,
        "end_hour": 20,
        "active_days": [1, 2, 3, 4, 5]
      }
    }
  }' \
  "https://votre-domaine.tld/config_api.php"
```

**Corps de la requête** :
- `key` (obligatoire) : Clé de configuration à mettre à jour
- `config` (obligatoire) : Objet de configuration complet

**Réponse** :
```json
{
  "status": "success",
  "message": "Configuration mise à jour avec succès",
  "timestamp": "2025-10-16T14:35:00Z"
}
```

### Codes d'erreur

| Code HTTP | Description |
|-----------|-------------|
| 200 | Succès |
| 400 | Requête invalide (paramètres manquants ou invalides) |
| 401 | Non autorisé (token invalide ou manquant) |
| 403 | Accès refusé (permissions insuffisantes) |
| 404 | Clé de configuration non trouvée |
| 500 | Erreur interne du serveur |

## Bonnes pratiques

1. **Sécurité** :
   - Utilisez toujours HTTPS pour les connexions au backend
   - Limitez l'accès à l'API par adresse IP si possible
   - Changez régulièrement les jetons d'API
   - Ne stockez jamais de jetons dans le code source

2. **Sauvegarde** :
   - Mettez en place des sauvegardes régulières des fichiers de configuration
   - Conservez un historique des modifications
   - Testez régulièrement la restauration des sauvegardes
