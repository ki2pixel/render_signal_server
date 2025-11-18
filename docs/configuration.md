## Déploiement Render (variables)

- `RENDER_API_KEY` – Token API Render (Bearer) pour `POST /v1/services/{id}/deploys`.
- `RENDER_SERVICE_ID` – Identifiant du service Render.
- `RENDER_DEPLOY_HOOK_URL` – URL Deploy Hook Render (prioritaire si défini).
- `RENDER_DEPLOY_CLEAR_CACHE` – `true|false` (contrôle le champ `clearCache` lors des appels API Render).
- `DEPLOY_CMD` – Commande fallback locale (ex: `systemctl reload-or-restart render-signal-server; nginx -s reload`).

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
# Configuration (variables d'environnement)

## Stockage de la configuration

La configuration est gérée via une API PHP sécurisée avec un système de fallback sur des fichiers JSON locaux. Cette solution remplace l'ancienne approche basée sur MySQL.

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

## Authentification UI

- `TRIGGER_PAGE_USER` – identifiant pour la connexion UI
- `TRIGGER_PAGE_PASSWORD` – mot de passe UI
- `FLASK_SECRET_KEY` – clé secrète Flask (sessions). Ex: chaîne aléatoire robuste.

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
  - Lorsqu'il est désactivé, seuls les flux Make.com reçoivent les liens médias; ce paramètre n'affecte pas la détection `delivery_links` ou la journalisation côté poller.

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
