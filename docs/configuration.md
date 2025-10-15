# Configuration (variables d'environnement)

Toutes les valeurs sensibles et spécifiques à l'environnement doivent être fournies via variables d'environnement. Des valeurs de référence `REF_*` existent dans `app_render.py` pour le développement, mais NE DOIVENT PAS être utilisées en production.

## Authentification UI
- `TRIGGER_PAGE_USER` – identifiant pour la connexion UI
- `TRIGGER_PAGE_PASSWORD` – mot de passe UI
- `FLASK_SECRET_KEY` – clé secrète Flask (sessions). Ex: chaîne aléatoire robuste.

## IMAP / E-mail
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `IMAP_SERVER` (ex: `mail.inbox.lt`)
- `IMAP_PORT` (ex: `993`)
- `IMAP_USE_SSL` (`true|false`)

## Polling et fenêtre d'activité
- `POLLING_TIMEZONE` (ex: `Europe/Paris` ou `UTC`)
- `POLLING_ACTIVE_START_HOUR` (ex: `9`)
- `POLLING_ACTIVE_END_HOUR` (ex: `23`)
- `POLLING_ACTIVE_DAYS` (liste CSV de 0=Mon à 6=Sun, ex: `0,1,2,3,4`)
- `EMAIL_POLLING_INTERVAL_SECONDS` (ex: `30`)
- `POLLING_INACTIVE_CHECK_INTERVAL_SECONDS` (ex: `600`)
- `DISABLE_EMAIL_ID_DEDUP` (`true|false`, défaut `false`) – bypass la déduplication par email ID pour débogage.

### Contrôle d'exécution des tâches de fond (sécurité opérationnelle)
- `ENABLE_BACKGROUND_TASKS` (`true|false`) – doit être `true` pour démarrer `background_email_poller()`. Laissez `false` sur les workers secondaires.
- `BG_POLLER_LOCK_FILE` (chemin) – fichier de verrou pour assurer un singleton inter-processus (défaut: `/tmp/render_signal_server_email_poller.lock`).

## Webhooks / Intégrations
- `WEBHOOK_URL` – URL de réception de vos événements (obligatoire pour envoi)
- `RECADRAGE_MAKE_WEBHOOK_URL` – webhook Make.com pour les emails de recadrage Média Solution (missions recadrage)
  * Anciennement `MAKECOM_WEBHOOK_URL` (toujours supporté pour rétrocompatibilité)
- `AUTOREPONDEUR_MAKE_WEBHOOK_URL` – webhook Make.com pour les emails d'autorépondeur (désabonnement/journée/tarifs habituels)
  * Anciennement `DESABO_MAKE_WEBHOOK_URL` (toujours supporté pour rétrocompatibilité)
- `MAKECOM_API_KEY` – clé API Make.com (si usage d'appels API)
- `PROCESS_API_TOKEN` – token attendu pour des appels d'API sortants vers ce service (si utilisé par des intégrations)
- `WEBHOOK_SSL_VERIFY` – booléen (`true|false`, défaut `true`). Contrôle la vérification SSL des appels webhook sortants. Laissez `true` en production. Mettre `false` uniquement pour le débogage/legacy, avec un certificat non conforme (un avertissement est loggé).

### Fenêtre horaire des webhooks DESABO
- `WEBHOOKS_TIME_START` – heure de début de la fenêtre pour les webhooks DESABO (format: HHhMM, HH:MM, etc., ex: "13h00")
- `WEBHOOKS_TIME_END` – heure de fin de la fenêtre pour les webhooks DESABO (format: HHhMM, HH:MM, etc., ex: "19h00")
- Note: Ces variables contrôlent la fenêtre horaire pour l'envoi des webhooks DESABO. Si l'email est traité avant la fenêtre, start_payload = WEBHOOKS_TIME_START; sinon "maintenant".

**Note sur les renommages :** Les anciennes variables `MAKECOM_WEBHOOK_URL` et `DESABO_MAKE_WEBHOOK_URL` continuent de fonctionner pour assurer la rétrocompatibilité. Les nouveaux noms clarifient le rôle de chaque webhook :
- **RECADRAGE** : pour les emails "Média Solution - Missions Recadrage" avec URLs de livraison
- **AUTOREPONDEUR** : pour les emails détectés avec "Se désabonner" + "journée" + "tarifs habituels" + lien Dropbox /request/

### Présence « samedi » (Make.com)
- `PRESENCE` – booléen (`true|false`). Sélectionne le webhook Make à utiliser lorsque des emails contenant « samedi » sont détectés à la fois dans le sujet et le corps.
- `PRESENCE_TRUE_MAKE_WEBHOOK_URL` – URL du webhook Make à utiliser si `PRESENCE=true`.
- `PRESENCE_FALSE_MAKE_WEBHOOK_URL` – URL du webhook Make à utiliser si `PRESENCE=false`.

Formats acceptés pour `PRESENCE_*_MAKE_WEBHOOK_URL`:
- URL complète: `https://hook.eu2.make.com/<token>`
- Alias: `<token>@hook.eu2.make.com` (normalisé automatiquement en URL HTTPS)
- `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` (`true|false`, défaut `false`) – permet l'envoi du webhook custom même si aucun lien de livraison n'est détecté.

## Redis (optionnel)
- `REDIS_URL` – ex: `redis://:password@host:6379/0`
 - `SUBJECT_GROUP_TTL_DAYS` (int, défaut `0`) – si > 0, active une clé TTL par groupe de sujet pour la déduplication (nécessite Redis). `0` = pas d'expiration.

## Chemins locaux
- `RENDER_DISC_PATH` – dossier pour fichiers éphémères (par défaut `./signal_data_app_render`).

### Override UI de la fenêtre horaire des webhooks
 La fenêtre horaire des webhooks Make peut être configurée via l'UI (`dashboard.html`).
 - Persistance côté serveur dans `debug/webhook_time_window.json` (pas de variable d'environnement).
 - Rechargée dynamiquement par le serveur; effet immédiat sans redéploiement.

## Log niveau
- `FLASK_LOG_LEVEL` – `DEBUG|INFO|WARNING|ERROR` (défaut: `INFO`).

## Résolution de liens – Headless (deprecated)
- Depuis le 2025-10-10, la résolution automatique des liens directs (ZIP/API) a été supprimée.
- Les variables ci-dessous sont conservées à titre documentaire mais ne produisent plus d'effet dans le code actuel.
- `ENABLE_HEADLESS_RESOLUTION` (`true|false`) – active la résolution avancée via navigateur headless (Playwright) pour FromSmash/SwissTransfer.
- `HEADLESS_MODE` (`true|false`) – `true` pour headless (défaut), `false` pour mode visible (diagnostic).
- `HEADLESS_MAX_ATTEMPTS` (int) – nombre de passes d'interaction (défaut 3).
- `HEADLESS_CLICK_TIMEOUT_MS` (int) – timeout pour `expect_download` (défaut 5000).
- `HEADLESS_TOTAL_TIMEOUT_MS` (int) – deadline globale par URL (défaut 45000).
- `HEADLESS_SCROLLS_PER_ATTEMPT` (int) – nombre de scrolls par passe (défaut 1).
- `HEADLESS_TRACE` (`true|false`) – journaliser les URLs réseau observées (sans contenu) pour diagnostic.
- `HEADLESS_USER_AGENT` (str) – User-Agent personnalisé (défaut: Chrome moderne).
- `HEADLESS_TZ` (str) – timezone navigateur (défaut `Europe/Paris`).
- `HEADLESS_ACCEPT_LANGUAGE` (str) – entête `Accept-Language` (défaut `fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7`).

Notes:
- Ces variables sont obsolètes et sans effet depuis la suppression de la fonctionnalité. Conservez-les non définies.

## Préférences de Traitement (processing_prefs.json)

Le fichier `debug/processing_prefs.json` contient des paramètres de traitement des e-mails qui peuvent être modifiés sans redémarrage du serveur. Voici les paramètres disponibles :

- `exclude_keywords` (array) : Liste de mots-clés pour filtrer les e-mails (ne pas traiter si présents dans l'objet ou le corps)
- `require_attachments` (bool) : Si `true`, n'envoie le webhook que pour les e-mails avec pièces jointes
- `max_email_size_mb` (int|null) : Taille maximale des e-mails en Mo (`null` pour désactiver la limite)
- `retry_count` (int) : Nombre de tentatives en cas d'échec d'envoi du webhook
- `retry_delay_sec` (int) : Délai en secondes entre les tentatives
- `webhook_timeout_sec` (int) : Délai d'expiration pour les appels webhook
- `rate_limit_per_hour` (int) : Limite de taux d'appels webhook par heure
- `notify_on_failure` (bool) : Activer les notifications en cas d'échec
- `mirror_media_to_custom` (bool) : **Paramètre critique** - Active l'envoi des liens de téléchargement (SwissTransfer, Dropbox, FromSmash) vers le webhook personnalisé configuré dans `WEBHOOK_URL`
  - `true` : Active le miroir vers le webhook personnalisé (recommandé pour la production)
  - `false` : Désactive l'envoi des liens au webhook personnalisé

### Exemple de configuration :
```json
{
  "exclude_keywords": ["SPAM", "PUBLICITÉ"],
  "require_attachments": false,
  "max_email_size_mb": 25,
  "retry_count": 2,
  "retry_delay_sec": 5,
  "webhook_timeout_sec": 30,
  "rate_limit_per_hour": 10,
  "notify_on_failure": true,
  "mirror_media_to_custom": true
}
```

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
