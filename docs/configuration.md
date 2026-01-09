## Déploiement Render (variables)

- `RENDER_API_KEY` – Token API Render (Bearer) pour `POST /v1/services/{id}/deploys`.
- `RENDER_SERVICE_ID` – Identifiant du service Render.
- `RENDER_DEPLOY_HOOK_URL` – URL Deploy Hook Render (préfixe `https://api.render.com/deploy/`, prioritaire si défini).
- `RENDER_DEPLOY_CLEAR_CACHE` – `clear|do_not_clear` (contrôle le champ `clearCache` lors des appels API Render).
- `DEPLOY_CMD` – Commande fallback locale (ex: `systemctl reload-or-restart render-signal-server; nginx -s reload`).
- `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `GUNICORN_GRACEFUL_TIMEOUT`, `GUNICORN_KEEP_ALIVE`, `GUNICORN_MAX_REQUESTS`, `GUNICORN_MAX_REQUESTS_JITTER` – valeurs injectées par Render et utilisées par le `Dockerfile`/Gunicorn. Les valeurs par défaut (2 workers, 2 threads, 120s, etc.) sont définies dans le Dockerfile et peuvent être surchargées via l’UI Render.

### Secrets GitHub Actions (pipeline GHCR → Render)

- `GHCR_USERNAME` – Nom d’utilisateur pour `docker login` (optionnel, défaut `github.actor`).
- `GHCR_TOKEN` – PAT ou `GITHUB_TOKEN` autorisé pour pousser vers GHCR.
- `RENDER_DEPLOY_HOOK_URL`, `RENDER_API_KEY`, `RENDER_SERVICE_ID`, `RENDER_DEPLOY_CLEAR_CACHE` – utilisés par `.github/workflows/render-image.yml` pour déclencher Render après push de l’image.
- Ces secrets doivent être renseignés dans les paramètres du dépôt GitHub pour que le workflow “Build & Deploy Render Image” fonctionne.

Notes:
- L'endpoint interne `POST /api/deploy_application` choisit automatiquement le meilleur chemin: Deploy Hook → API Render → commande fallback.
- Les logs masquent la clé du Deploy Hook et tracent l'identité de l'utilisateur authentifié ayant déclenché le déploiement.

## Politique SSL des webhooks

- `WEBHOOK_SSL_VERIFY=false` n'est à utiliser qu'en développement. En production, laisser `true` pour la vérification TLS/SSL.
- Lorsque désactivé, l'application émet un avertissement dans les logs au démarrage.

## Accès configuration via services

- `ConfigService` expose des accesseurs typés (`get_email_config()`, `get_api_token()`, `get_render_config()`, etc.).
- `RuntimeFlagsService` (Singleton) gère `get_all_flags()` et `update_flags()` avec persistence JSON et cache TTL 60s.
- `WebhookConfigService` (Singleton) centralise la configuration webhooks (validation HTTPS, normalisation Make.com, cache + store externe optionnel). Les champs couvrent aussi la « fenêtre horaire des webhooks » (`webhook_time_start`, `webhook_time_end`, ainsi que `global_time_start/global_time_end` pour synchronisation UI legacy). La persistance privilégie le store externe (si configuré) avec fallback fichier `debug/webhook_config.json`.
- `R2TransferService` (Singleton) active l’offload Cloudflare R2 lorsque `R2_FETCH_ENABLED=true`, vérifie la présence de `R2_FETCH_ENDPOINT`/`R2_FETCH_TOKEN`, normalise les URLs Dropbox et persiste les paires `source_url`/`r2_url` dans `WEBHOOK_LINKS_FILE`.
- `MagicLinkService` (Singleton) consomme `FLASK_SECRET_KEY`, `MAGIC_LINK_TTL_SECONDS` et `MAGIC_LINK_TOKENS_FILE` pour générer/valider les magic links et assure la création + verrouillage du fichier de tokens au démarrage.
# Configuration (variables d'environnement)

## Stockage de la configuration

La configuration est gérée via une API PHP sécurisée avec un système de fallback sur des fichiers JSON locaux. Cette solution remplace l'ancienne approche basée sur MySQL.

### Variables Magic Links

- `MAGIC_LINK_TTL_SECONDS` : Durée de validité des liens à usage unique (défaut: 900 secondes = 15 minutes)
- `MAGIC_LINK_TOKENS_FILE` : Chemin du fichier de stockage des tokens (défaut: `./magic_link_tokens.json`)
- `FLASK_SECRET_KEY` : Clé secrète HMAC pour signer les tokens (obligatoire, doit être robuste)

### Variables Cloudflare R2 (Offload fichiers)

| Variable | Description |
| --- | --- |
| `R2_FETCH_ENABLED` | Active/désactive l’offload (défaut `false`). |
| `R2_FETCH_ENDPOINT` | URL du Worker Cloudflare (ex: `https://r2-fetch.<zone>.workers.dev`). |
| `R2_FETCH_TOKEN` | Token secret envoyé dans `X-R2-FETCH-TOKEN` (obligatoire côté Render, Worker, pages PHP). |
| `R2_PUBLIC_BASE_URL` | Domaine public servant les objets R2 (CDN/Workers). |
| `R2_BUCKET_NAME` | Bucket R2 cible (ex: `render-signal-media`). |
| `WEBHOOK_LINKS_FILE` | Fichier de persistance des paires `source_url`/`r2_url` (défaut `deployment/data/webhook_links.json`). |
| `R2_LINKS_MAX_ENTRIES` | Nombre max d’entrées conservées avant rotation (défaut `1000`). |
| `JSON_LOG_MAX_BYTES` | Limite taille fichier côté PHP avant rotation (défaut `5*1024*1024`). |
| `R2_FETCH_TIMEOUT_DROPBOX_SCL_FO` | (Optionnel) Timeout spécifique pour les dossiers Dropbox `/scl/fo/` (défaut interne 120s). |

### Variables sensibles R2 (non à commiter)

- `R2_FETCH_TOKEN`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ACCOUNT_ID`

### Architecture du système de configuration

1. **Backend API** (préféré) :
   - Stockage sécurisé des paramètres de configuration
   - Authentification par jeton d'API
   - Gestion centralisée des paramètres
   - Localisation : `deployment/config/config_api.php`

2. **Fallback local** (si l'API n'est pas disponible) :
   - Fichiers JSON stockés localement
   - Structure de dossiers : `debug/`
   - Fichiers principaux :
     - `webhook_config.json` - Configuration des webhooks
     - `processing_prefs.json` - Préférences de traitement
     - `webhook_time_window.json` - Fenêtres horaires

### Configuration requise

#### Variables d'environnement
- `EXTERNAL_CONFIG_BASE_URL` - URL de base de l'API de configuration (ex: `https://votre-domaine.tld`)
- `CONFIG_API_TOKEN` - Jeton d'authentification sécurisé pour l'API

#### Sécurité
- Le jeton d'API doit être fort et unique
- Le répertoire de stockage doit être en dehors de la racine web
- Les permissions doivent être correctement définies (750 pour les dossiers, 640 pour les fichiers)
- L'API doit être accessible uniquement en HTTPS

### Migration depuis l'ancien système
1. Exporter les configurations existantes
2. Configurer le nouveau backend API
3. Mettre à jour les variables d'environnement
4. Tester le fonctionnement avec le nouveau système

Pour plus de détails sur la configuration avancée, consultez le fichier `deployment/README.md`.

## Authentification

### Authentification de base
- `TRIGGER_PAGE_USER` – identifiant pour la connexion UI
- `TRIGGER_PAGE_PASSWORD` – mot de passe UI
- `FLASK_SECRET_KEY` – clé secrète Flask (sessions et signature des tokens Magic Link). Doit être une chaîne aléatoire robuste.

### Magic Links
- `MAGIC_LINK_TTL_SECONDS` – durée de validité des liens à usage unique en secondes (défaut: 900 - 15 minutes)
- `MAGIC_LINK_TOKENS_FILE` – chemin vers le fichier de stockage des tokens (défaut: `./magic_link_tokens.json`)
- `MAGIC_LINK_ENABLED` – active/désactive la fonctionnalité de Magic Links (défaut: `true`)

#### Recommandations pour les Magic Links
- Le fichier de tokens doit être stocké dans un répertoire sécurisé avec des permissions restrictives
- Pour une sécurité optimale, définissez un `MAGIC_LINK_TTL_SECONDS` court (ex: 300 pour 5 minutes)
- Régénérez périodiquement `FLASK_SECRET_KEY` pour invalider tous les tokens existants

## IMAP / E-mail
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `IMAP_SERVER` (ex: `mail.inbox.lt`)
- `IMAP_PORT` (défaut: `993`)
- `IMAP_SSL` (défaut: `true`)
- `EMAIL_CONFIG_VALID` (validation des paramètres IMAP)
- `DISABLE_EMAIL_ID_DEDUP` (`true|false`, défaut `false`) – bypass la déduplication par email ID pour débogage.
### Contrôle d'exécution des tâches de fond (sécurité opérationnelle)
- `ENABLE_BACKGROUND_TASKS` (`true|false`) – doit être `true` pour démarrer `background_email_poller()`. Laissez `false` sur les workers secondaires.
- `BG_POLLER_LOCK_FILE` (chemin) – fichier de verrou pour assurer un singleton inter-processus (défaut: `/tmp/render_signal_server_email_poller.lock`).
 - Watcher Make (optionnel) – ne démarre que si `ENABLE_BACKGROUND_TASKS=true` ET `MAKECOM_API_KEY` est défini (réduction du bruit 401 en absence de clé).

## Webhooks
- `DEBUG_EMAIL` – active le mode débogage pour les e-mails (pas d'envoi réel)
- `DEBUG_WEBHOOK` – active le mode débogage pour les webhooks (pas d'envoi réel)
- `WEBHOOK_URL` - URL du webhook personnalisé qui recevra les notifications
- `WEBHOOK_SSL_VERIFY` - Vérification SSL pour les appels sortants (désactivez uniquement pour le débogage, défaut: `true`)
- `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` - Si `true`, envoie les webhooks même sans liens détectés (défaut: `false`)

Variables avancées:
- `ORCHESTRATOR_ALLOW_LEGACY_DELEGATION` - Si `true`, l'orchestrateur peut déléguer le cycle complet à `app_render._legacy_check_new_emails_and_trigger_webhook` si cette fonction existe. Défaut: désactivé.

Notes (service):
- La validation stricte des URLs et la normalisation Make.com sont centralisées dans `WebhookConfigService`.
- Les valeurs sont mises en cache (TTL 60s) et invalidées lors des mises à jour via l'API.

## Gmail OAuth (pour envoi d'emails depuis les webhooks)
- `GMAIL_CLIENT_ID` - ID client OAuth de Google Cloud Console
- `GMAIL_CLIENT_SECRET` - Secret client OAuth de Google Cloud Console
- `GMAIL_REFRESH_TOKEN` - Refresh token obtenu via OAuth Playground
- `GMAIL_FROM_EMAIL` - Adresse e-mail expéditrice (doit correspondre au compte Gmail)
- `GMAIL_FROM_NAME` - Nom d'affichage optionnel pour l'expéditeur
- `AUTOREPONDEUR_TO` - Adresse e-mail destinataire pour les notifications d'autorépondeur
- `GMAIL_OAUTH_CHECK_KEY` - Clé de sécurité pour l'auto-check périodique
- `GMAIL_OAUTH_CHECK_INTERVAL_DAYS` - Intervalle en jours pour les vérifications automatiques (défaut: 7)
- `GMAIL_OAUTH_TEST_TO` - Adresse de test pour les envois d'exemple

## Fichiers de configuration locaux (fallback)

- `WEBHOOK_CONFIG_FILE` – fichier de configuration (défaut: `debug/webhook_config.json`)
- `PROCESSING_PREFS_FILE` – préférences de traitement (défaut: `debug/processing_prefs.json`)
- `WEBHOOK_SSL_VERIFY` – Vérification SSL (désactivez uniquement en développement, défaut: `true`)
- `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` – Si `true`, envoie les webhooks même sans liens détectés (défaut: `false`)

Fichiers supplémentaires (services):
- `RUNTIME_FLAGS_FILE` – fichier JSON des flags runtime (défaut: `debug/runtime_flags.json`) utilisé par `RuntimeFlagsService`.
- `POLLING_CONFIG_FILE` – fichier JSON de configuration du polling (défaut: `debug/polling_config.json`).
- `TRIGGER_SIGNAL_FILE` – fichier de signal local (par défaut sous `signal_data_app_render/`).

## Redis (optionnel)
- `REDIS_URL` – ex: `redis://:password@host:6379/0`
 - `SUBJECT_GROUP_TTL_DAYS` (int, défaut `0`) – si > 0, active une clé TTL par groupe de sujet pour la déduplication (nécessite Redis). `0` = pas d'expiration.

## Chemins locaux
- `RENDER_DISC_PATH` – dossier pour fichiers éphémères (par défaut `./signal_data_app_render`).

## Fenêtres horaires

### Fenêtre horaire des e-mails
- `POLLING_ACTIVE_START_HOUR` - Heure de début de la fenêtre d'envoi (0-23)
- `POLLING_ACTIVE_END_HOUR` - Heure de fin de fenêtre d'envoi (0-23)
- `POLLING_ACTIVE_DAYS` - Jours actifs (0=dimanche à 6=samedi, séparés par des virgules, ex: `1,2,3,4,5` pour du lundi au vendredi)

### Fenêtre horaire des webhooks
Une fenêtre horaire dédiée est disponible pour contrôler l'envoi des webhooks, indépendamment de la réception des e-mails :
- Configurable via l'interface utilisateur ou l'API (`GET/POST /api/webhooks/time-window`)
- Persistée via `WebhookConfigService` (store externe prioritaire, fallback fichier `debug/webhook_config.json`)
- Peut être désactivée pour envoyer les webhooks à toute heure
- Rechargée dynamiquement par le serveur sans redémarrage nécessaire

Variables d'environnement (fallback):
- `WEBHOOKS_TIME_START`, `WEBHOOKS_TIME_END` : noms canoniques.
- `WEBHOOK_TIME_START`, `WEBHOOK_TIME_END` : rétrocompatibilité (dépréciés) ; utilisés si les variables canoniques ne sont pas définies.

### Gestion via l'interface utilisateur
- La section "Fenêtre Horaire" du tableau de bord permet de configurer :
  - L'activation/désactivation de la fenêtre horaire
  - Les heures de début et de fin
  - Les jours de la semaine actifs
  - L'application immédiate des changements

### Gestion via API
- `GET /api/webhooks/time-window` - Récupère la configuration actuelle
- `POST /api/webhooks/time-window` - Met à jour la configuration

Synchronisation avec store externe (best-effort):
- Lors d'un `GET /api/get_webhook_time_window`, l'application tente de synchroniser `global_time_start/global_time_end` depuis le store externe si disponibles.
- Lors d'un `POST /api/set_webhook_time_window`, l'application met à jour le store externe avec les valeurs courantes (si accessible). Le fallback fichier local reste opérationnel en cas d'indisponibilité du store externe.

Exemple de réponse :
```json
{
  "enabled": true,
  "start_hour": 8,
  "end_hour": 20,
  "active_days": [1, 2, 3, 4, 5]
}
```

## Log niveau
- `FLASK_LOG_LEVEL` – `DEBUG|INFO|WARNING|ERROR` (défaut: `INFO`).


## Préférences de Traitement (processing_prefs.json)

Le fichier `debug/processing_prefs.json` contient des paramètres de traitement des e-mails qui peuvent être modifiés sans redémarrage du serveur. Ces préférences sont chargées au démarrage et peuvent être mises à jour via l'API ou l'interface utilisateur.

### Paramètres disponibles

- `exclude_keywords` (array) : 
  - Liste de mots-clés globaux pour filtrer les e-mails (ne pas traiter si présents dans l'objet ou le corps)
  - Peut être remplacé par des listes spécifiques par webhook
  
- `webhook_exclude_keywords` (object) : 
  - Mots-clés spécifiques par webhook (ex: `{"webhook1": ["mot1", "mot2"]}`)
  - Surcharge les mots-clés globaux pour les webhooks spécifiés

- `require_attachments` (bool) : 
  - Si `true`, n'envoie le webhook que pour les e-mails avec pièces jointes
  - Par défaut: `true`

- `max_email_size_mb` (int|null) : 
  - Taille maximale des e-mails en Mo 
  - `null` pour désactiver la limite
  - Par défaut: `25`

- `retry_count` (int) : 
  - Nombre de tentatives en cas d'échec d'envoi du webhook
  - Par défaut: `2`

- `retry_delay_sec` (int) : 
  - Délai en secondes entre les tentatives
  - Par défaut: `5`

- `webhook_timeout_sec` (int) : 
  - Délai d'expiration pour les appels webhook
  - Par défaut: `30`

- `rate_limit_per_hour` (int) : 
  - Limite de taux d'appels webhook par heure
  - Par défaut: `10`

- `notify_on_failure` (bool) : 
  - Activer les notifications en cas d'échec
  - Par défaut: `true`

- `mirror_media_to_custom` (bool) : 
  - **Paramètre critique** - Active l'envoi des liens de téléchargement (SwissTransfer, Dropbox, FromSmash) vers le webhook personnalisé configuré dans `WEBHOOK_URL`.
  - `true` : Active le miroir vers le webhook personnalisé (défaut depuis `routes/api_processing.py`).
  - `false` : Désactive l'envoi des liens au webhook personnalisé.
  - Lorsqu'il est désactivé, seuls les flux Make.com (s'ils sont configurés) reçoivent les liens médias; ce paramètre n'affecte pas la détection `delivery_links` ou la journalisation côté poller.

- `enable_subject_group_dedup` (bool) :
  - Active la déduplication par groupe de sujets
  - Si activé, les e-mails avec des sujets similaires (même expéditeur et préfixe commun) sont groupés
  - Par défaut: `true`

### Gestion via l'API

Les préférences de traitement peuvent être gérées via les endpoints suivants :
- `GET /api/processing/prefs` - Récupère les préférences actuelles
- `POST /api/processing/prefs` - Met à jour les préférences
- `GET /api/processing/prefs/defaults` - Récupère les valeurs par défaut

### Validation

Les valeurs sont validées côté serveur avant d'être appliquées. Les erreurs de validation sont renvoyées avec un code HTTP 400 et un message d'erreur détaillé.

### Exemple de configuration complète :
```json
{
  "exclude_keywords": ["SPAM", "PUBLICITÉ"],
  "webhook_exclude_keywords": {
    "webhook1": ["TEST", "INTERNE"],
    "webhook2": ["ARCHIVE"]
  },
  "require_attachments": false,
  "max_email_size_mb": 25,
  "retry_count": 2,
  "retry_delay_sec": 5,
  "webhook_timeout_sec": 30,
  "rate_limit_per_hour": 10,
  "notify_on_failure": true,
  "mirror_media_to_custom": true,
  "enable_subject_group_dedup": true
}
```

### Ordre de priorité des configurations

1. **Mots-clés d'exclusion** :
   - Les mots-clés spécifiques au webhook (`webhook_exclude_keywords`) ont priorité sur les mots-clés globaux (`exclude_keywords`)
   - Si un webhook n'a pas de configuration spécifique, les mots-clés globaux sont utilisés

2. **Fenêtres horaires** :
   - La fenêtre horaire des webhooks est indépendante de celle des e-mails
   - Si la fenêtre horaire des webhooks est désactivée, les webhooks sont envoyés à tout moment (sous réserve des autres validations)
   - Si la fenêtre horaire des e-mails est en dehors des heures actives, les e-mails ne sont pas récupérés du tout

3. **Traitement des pièces jointes** :
   - Si `require_attachments` est `true` mais qu'aucune pièce jointe n'est détectée, le webhook n'est pas envoyé
   - Les liens vers des médias externes (comme SwissTransfer) sont considérés comme des "pièces jointes virtuelles"

## CORS et Endpoints de Test
- `TEST_API_KEY` – clé API utilisée pour authentifier les endpoints de test sous `/api/test/*` via le header `X-API-Key`.
- `CORS_ALLOWED_ORIGINS` – liste CSV d'origines autorisées pour CORS (ex: `https://webhook.kidpixel.fr,http://localhost:8080`).
  - Conseillé: limiter aux domaines nécessaires uniquement.

Notes:
- Les endpoints `/api/test/*` répliquent la logique des endpoints protégés mais sans sessions; ils sont destinés aux validations cross-origin.
- Les URLs sensibles retournées par lecture sont masquées partiellement; envoyez l'URL complète pour mettre à jour.

## Bonnes pratiques
- Ne jamais committer de secrets.
- Utiliser un gestionnaire de secrets/variables (dotenv, Vault, etc.).
- Forcer des mots de passe forts et rotation régulière.
