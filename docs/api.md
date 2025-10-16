# API HTTP (Flask)

L'API est organisée en plusieurs blueprints Flask pour une meilleure modularité. Les routes sont documentées ci-dessous par catégorie fonctionnelle.

## Organisation des routes

L'API est structurée en blueprints Flask pour une meilleure organisation et maintenabilité. Voici la structure complète :

| Blueprint | Fichier | Description | Routes Principales |
|-----------|---------|-------------|-------------------|
| `health` | `routes/health.py` | Vérification de l'état du service | `GET /health` |
| `dashboard` | `routes/dashboard.py` | Interface utilisateur | `GET /`, `/login`, `/logout` |
| `api_webhooks` | `routes/api_webhooks.py` | Gestion des webhooks | `GET/POST /api/webhooks/config` |
| `api_polling` | `routes/api_polling.py` | Réservé pour extensions futures | — |
| `api_processing` | `routes/api_processing.py` | Préférences de traitement | `GET/POST /api/processing_prefs` |
| `api_logs` | `routes/api_logs.py` | Consultation des logs | `GET /api/webhook_logs` |
| `api_test` | `routes/api_test.py` | Endpoints de test (CORS) | `GET /api/test/*` |
| `api_utility` | `routes/api_utility.py` | Utilitaires (ping, trigger, statut local) | `GET /api/ping`, `GET /api/check_trigger`, `GET /api/get_local_status` |
| `api_admin` | `routes/api_admin.py` | Admin (redémarrage, déclenchement manuel) | `POST /api/restart_server`, `POST /api/check_emails_and_download` |
| `api_config` | `routes/api_config.py` | Configuration (fenêtres horaires, flags, polling) | `GET/POST /api/webhooks/time-window`, `GET/POST /api/runtime-flags`, `GET/POST /api/polling-config` |

## Authentification

Toutes les routes de l'API (sauf `/health` et `/login`) nécessitent une authentification. L'authentification se fait via des sessions Flask avec Flask-Login.

### Connexion

- `POST /login`
  - Paramètres : `username`, `password` (form-data ou JSON)
  - Réponse en cas de succès : Redirection vers `/`
  - Réponse en cas d'échec : Page de login avec message d'erreur

### Déconnexion

- `GET /logout`
  - Déconnecte l'utilisateur et redirige vers `/login`

## Stockage des données

Les configurations sont stockées dans un backend JSON externe avec fallback sur des fichiers locaux. Voir [storage.md](storage.md) pour plus de détails.

### Compatibilité Ascendante

Pour assurer la rétrocompatibilité, les anciennes URLs sont maintenues via des redirections dans les blueprints appropriés.

## Compatibilité

Pour assurer la rétrocompatibilité, les anciennes URLs sont maintenues via des redirections dans les blueprints appropriés.

## Authentification et UI

- `GET|POST /login`
  - Vue de connexion (template `login.html`).
  - POST avec `username`, `password` crée une session.
  - Redirige vers `/` en cas de succès.

- `GET /logout` (protégé)
  - Déconnecte l'utilisateur et redirige vers `/login`.

- `GET /` (protégé)
  - Sert le template `dashboard.html` (Dashboard Webhooks: configuration, contrôle du polling, logs).

## Endpoints utilitaires

- `GET /health`
  - Liveness endpoint simple (blueprint `health`).
  - Réponse: `{ "status": "ok" }`

- `GET /api/ping`
  - Réponse: `{ "status": "pong", "timestamp_utc": "..." }`
  - Santé de base.

- `GET /api/check_trigger`
  - Lit puis consomme le fichier `signal_data_app_render/local_workflow_trigger_signal.json` s'il existe.
  - Réponse: `{ "command_pending": bool, "payload": object|null }`

### Configuration des flags runtime

### Récupération des flags

- `GET /api/runtime-flags` (protégé)
  - Retourne les flags runtime actuels
  - Réponse :
    ```json
    {
      "success": true,
      "flags": {
        "debug_mode": false,
        "enable_verbose_logging": false,
        "force_processing": false
      }
    }
    ```

### Mise à jour des flags

- `POST /api/runtime-flags` (protégé)
  - Met à jour les flags runtime
  - Corps JSON (tous les champs sont optionnels) :
    ```json
    {
      "debug_mode": false,
      "enable_verbose_logging": false,
      "force_processing": false
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Flags runtime mis à jour avec succès" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

Exemples curl:

```bash
# 1) Login et stockage des cookies
curl -sSL -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<USERNAME>&password=<PASSWORD>" \
  https://DOMAIN/login -o /dev/null

# 2) presence=true (JSON)
curl -sS -X POST -H "Content-Type: application/json" \
  -b cookies.txt -c cookies.txt \
  https://DOMAIN/api/test_presence_webhook \
  -d '{"presence":"true"}'

# 3) presence=false (JSON)
curl -sS -X POST -H "Content-Type: application/json" \
  -b cookies.txt -c cookies.txt \
  https://DOMAIN/api/test_presence_webhook \
  -d '{"presence":"false"}'

# Variante form-urlencoded
curl -sS -X POST \
  -b cookies.txt -c cookies.txt \
  -d "presence=true" \
  https://DOMAIN/api/test_presence_webhook
```

Remplacez `DOMAIN` par l'URL Render, et `<USERNAME>/<PASSWORD>` par vos identifiants.

## Polling e-mail (déclenchement manuel)

- `POST /api/check_emails_and_download` (protégé)
  - Lance `check_new_emails_and_trigger_webhook()` dans un thread.
  - Codes de réponse:
    - `202` si lancé: `{ "status": "success", "message": "Vérification en arrière-plan lancée." }`
    - `503` si configuration manquante.
  - Note: le backend extrait des URLs de livraison multi-fournisseurs (Dropbox, FromSmash, SwissTransfer) lors du traitement des e-mails via `check_media_solution_pattern()`.

## Format des webhooks

### Webhook principal

```json
{
  "event_type": "email_received",
  "timestamp": "2025-10-16T14:30:00Z",
  "email": {
    "id": "<email_id>",
    "subject": "Sujet de l'email",
    "from": "expediteur@example.com",
    "to": ["destinataire@example.com"],
    "date": "2025-10-16T14:25:00Z",
    "text": "Contenu texte de l'email",
    "html": "<p>Contenu HTML de l'email</p>",
    "attachments": [
      {
        "filename": "piece-jointe.pdf",
        "content_type": "application/pdf",
        "size": 12345,
        "content_id": "<content_id>"
      }
    ]
  },
  "metadata": {
    "processing_time_ms": 123,
    "detected_media": [
      {
        "provider": "swisstransfer",
        "raw_url": "https://www.swisstransfer.com/d/...",
        "direct_url": "https://www.swisstransfer.com/d/.../download"
      }
    ]
  }
}
```

### Webhook personnalisé (si activé)

```json
{
  "event_type": "email_processed",
  "timestamp": "2025-10-16T14:30:00Z",
  "email_id": "<email_id>",
  "subject": "Sujet de l'email",
  "from": "expediteur@example.com",
  "to": ["destinataire@example.com"],
  "date": "2025-10-16T14:25:00Z",
  "media_links": [
    {
      "provider": "swisstransfer",
      "url": "https://www.swisstransfer.com/d/..."
    }
  ]
}
```

## Gestion des erreurs

### Format des réponses d'erreur

Toutes les erreurs d'API suivent le format suivant :

```json
{
  "success": false,
  "error": {
    "code": "error_code",
    "message": "Message d'erreur détaillé",
    "details": {
      "field1": "Détail supplémentaire 1",
      "field2": "Détail supplémentaire 2"
    }
  }
}
```

### Codes d'erreur courants

| Code HTTP | Code erreur | Description |
|-----------|-------------|-------------|
| 400 | `validation_error` | Erreur de validation des données d'entrée |
| 401 | `unauthorized` | Authentification requise ou session expirée |
| 403 | `forbidden` | Permissions insuffisantes |
| 404 | `not_found` | Ressource non trouvée |
| 500 | `internal_error` | Erreur interne du serveur |
| 503 | `service_unavailable` | Service temporairement indisponible |

## Sécurité

### Authentification

- Toutes les requêtes doivent inclure un jeton d'authentification valide
- Les jetons sont gérés via des sessions sécurisées
- Les mots de passe sont stockés de manière sécurisée (hash + sel)

### Protection CSRF

- Toutes les requêtes POST doivent inclure un jeton CSRF valide
- Le jeton est disponible dans le cookie `csrftoken` et doit être inclus dans l'en-tête `X-CSRFToken`

### En-têtes de sécurité

L'application inclut les en-têtes de sécurité HTTP suivants :

- `Content-Security-Policy` : Restreint les sources de contenu autorisées
- `X-Content-Type-Options: nosniff` : Empêche le MIME-sniffing
- `X-Frame-Options: DENY` : Empêche le clickjacking
- `X-XSS-Protection: 1; mode=block` : Active la protection XSS des navigateurs
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` : Force l'utilisation de HTTPS
- `Referrer-Policy: strict-origin-when-cross-origin` : Contrôle les informations de référent envoyées

## Journalisation

Toutes les requêtes API sont journalisées avec les informations suivantes :

- Date et heure
- Adresse IP du client
- Méthode HTTP et URL
- Code de statut HTTP
- Temps de réponse
- Identifiant utilisateur (si authentifié)
- Données de la requête (sans les informations sensibles)

Les journaux sont disponibles via l'interface d'administration et peuvent être exportés au format JSON.

## Dashboard Webhooks (endpoints via Blueprints)

Les endpoints suivants (utilisés par `dashboard.html`) sont désormais organisés via des Blueprints Flask.

### Gestion des webhooks

### Configuration des webhooks

- `GET /api/webhooks/config` (protégé)
  - Retourne la configuration actuelle des webhooks
  - Réponse:
    ```json
    {
      "success": true,
      "config": {
        "webhook_url": "https://...",
        "webhook_enabled": true,
        "webhook_ssl_verify": true,
        "custom_webhook_url": "https://...",
        "custom_webhook_enabled": true,
        "mirror_media_to_custom": false
      }
    }
    ```

- `POST /api/webhooks/config` (protégé)
  - Met à jour la configuration des webhooks
  - Corps JSON (tous les champs sont optionnels) :
    ```json
    {
      "webhook_url": "https://...",
      "webhook_enabled": true,
      "webhook_ssl_verify": true,
      "custom_webhook_url": "https://...",
      "custom_webhook_enabled": true,
      "mirror_media_to_custom": false
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Configuration des webhooks mise à jour avec succès" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

### Gestion des fenêtres horaires

- `GET /api/webhooks/time-window` (protégé)
  - Récupère la fenêtre horaire des webhooks
  - Réponse :
    ```json
    {
      "success": true,
      "time_window": {
        "start_hour": 8,
        "end_hour": 20,
        "active_days": [1, 2, 3, 4, 5]
      }
    }
    ```

- `POST /api/webhooks/time-window` (protégé)
  - Met à jour la fenêtre horaire des webhooks
  - Corps JSON :
    ```json
    {
      "start_hour": 8,
      "end_hour": 20,
      "active_days": [1, 2, 3, 4, 5]
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Fenêtre horaire mise à jour avec succès" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

### Contrôle du polling (via configuration)

- `GET /api/get_polling_config` (protégé)
  - Retourne la configuration persistée côté serveur, incluant le flag `enable_polling`.
  - Réponse: `{ "success": true, "config": { ..., "enable_polling": bool } }`

- `POST /api/update_polling_config` (protégé)
  - Met à jour la configuration de polling. Champs optionnels (merge partiel), dont `enable_polling` (bool):
    - `active_days`: array d'entiers 0..6 (0=lundi)
    - `active_start_hour`: int 0..23
    - `active_end_hour`: int 0..23
    - `enable_subject_group_dedup`: bool
    - `sender_of_interest_for_polling`: array d'emails (validés/normalisés)
    - `enable_polling`: bool
  - Réponses:
    - 200: `{ "success": true, "message": "Configuration polling enregistrée.", "config": { ..., "enable_polling": bool } }`
  - Notes:
    - Le thread de polling au démarrage est conditionné par: `ENABLE_BACKGROUND_TASKS` (env) ET `enable_polling` (config persistée).
    - Un redémarrage du service est nécessaire pour (dés)activer effectivement le thread de fond.

### Configuration du Polling

### Récupération de la configuration

- `GET /api/polling-config` (protégé)
  - Retourne la configuration actuelle du polling
  - Réponse :
    ```json
    {
      "success": true,
      "config": {
        "active_days": [1, 2, 3, 4, 5],
        "active_start_hour": 9,
        "active_end_hour": 18,
        "enable_subject_group_dedup": true,
        "sender_of_interest_for_polling": ["contact@example.com"],
        "enable_polling": true
      }
    }
    ```

### Mise à jour de la configuration

- `POST /api/polling-config` (protégé)
  - Met à jour la configuration du polling
  - Corps JSON (tous les champs sont optionnels) :
    ```json
    {
      "active_days": [1, 2, 3, 4, 5],
      "active_start_hour": 9,
      "active_end_hour": 18,
      "enable_subject_group_dedup": true,
      "sender_of_interest_for_polling": ["contact@example.com"],
      "enable_polling": true
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Configuration du polling mise à jour avec succès" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

### Fenêtre horaire du polling

- `GET /api/polling-time-window` (protégé)
  - Récupère la fenêtre horaire du polling
  - Réponse :
    ```json
    {
      "success": true,
      "time_window": {
        "start_hour": 8,
        "end_hour": 20,
        "active_days": [1, 2, 3, 4, 5]
      }
    }
    ```

- `POST /api/polling-time-window` (protégé)
  - Met à jour la fenêtre horaire du polling
  - Corps JSON :
    ```json
    {
      "start_hour": 8,
      "end_hour": 20,
      "active_days": [1, 2, 3, 4, 5]
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Fenêtre horaire du polling mise à jour avec succès" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

## Endpoints legacy (dépréciés ou supprimés)

- Supprimés lors du refactoring (routes → blueprints) puis consolidation polling:
  - `GET /api/get_webhook_config` → remplacé par `GET /api/webhooks/config`
  - `POST /api/update_webhook_config` → remplacé par `POST /api/webhooks/config`
  - `POST /api/toggle_polling` et `POST /api/polling/toggle` → supprimés. Le contrôle du polling passe par `POST /api/update_polling_config` avec le champ `enable_polling`.

- Dépréciés (télécommande):
  - `GET /api/get_local_status`
  - `POST /api/trigger_local_workflow`

Ces endpoints peuvent être supprimés définitivement si aucune intégration externe ne les utilise encore.

## Sécurité

- Les routes marquées (protégé) nécessitent une session utilisateur (Flask-Login).
- Configurez `FLASK_SECRET_KEY`, `TRIGGER_PAGE_USER`, `TRIGGER_PAGE_PASSWORD` via env vars.

## Exemples de tests (curl)

Tester la santé de l'API:

```bash
curl -s http://localhost:10000/api/ping | jq .
```

Récupérer (et consommer) un signal local s'il existe:

```bash
curl -s http://localhost:10000/api/check_trigger | jq .
```

Se connecter, conserver la session, puis appeler une route protégée:

```bash
# 1) Login et stockage des cookies dans un fichier
curl -i -c cookies.txt -X POST \
  -d 'username=admin' -d 'password=mon_mot_de_passe' \
  http://localhost:10000/login

# 2) Appel de la route protégée avec les cookies (-b)
curl -b cookies.txt -s -X POST http://localhost:10000/api/check_emails_and_download | jq .

# 3) Se déconnecter (optionnel)
curl -b cookies.txt -s http://localhost:10000/logout -o /dev/null -w '\nHTTP %{http_code}\n'
```

## Fenêtre horaire des webhooks (endpoints protégés)

### Anciens endpoints (maintenus pour compatibilité)
- `GET /api/get_webhook_time_window`
  - Réponse: `{ "success": true, "webhooks_time_start": "HHhMM|null|''", "webhooks_time_end": "HHhMM|null|''", "timezone": "Europe/Paris|UTC|..." }`
  - Remarques: les champs vides/absents signifient « pas de contrainte ».

- `POST /api/set_webhook_time_window`
  - Corps JSON: `{ "start": "11h30|11:30|''", "end": "17h30|17:30|''" }`
  - Règles de validation:
    - Formats acceptés: `HHhMM`, `HH:MM`, `HHh`, `HH` (normalisés en `HHhMM`).
    - Les deux vides désactivent la contrainte.
  - Réponses:
    - 200: `{ "success": true, "webhooks_time_start": "HHhMM|null", "webhooks_time_end": "HHhMM|null" }`
    - 400: `{ "success": false, "message": string }` (paramètre manquant ou URL non configurée)
    - 500: `{ "success": false, "message": string }` (échec d'envoi)

### Nouveaux endpoints (recommandés)
- `GET /api/webhooks/time-window`
  - Récupère la fenêtre horaire actuelle pour l'envoi des webhooks
  - Réponse: `{ 
    "success": true, 
    "time_window": {
      "start": "HHhMM"|null, 
      "end": "HHhMM"|null,
      "timezone": "Europe/Paris"
    }
  }`

- `POST /api/webhooks/time-window`
  - Définit la fenêtre horaire pour l'envoi des webhooks
  - Corps JSON: `{ 
    "start": "11h30"|null, 
    "end": "17h30"|null 
  }`
  - Réponses:
    - 200: `{ "success": true, "time_window": { "start": "HHhMM"|null, "end": "HHhMM"|null } }`
    - 400: `{ "success": false, "error": "message d'erreur" }`
  - Notes:
    - Si start et end sont null, la fenêtre horaire est désactivée
    - Le format d'heure doit être HHhMM (ex: "09h30", "17h00")
    - La timezone est déterminée par `POLLING_TIMEZONE`

## Statut du worker local (télécommande) — Déprécié

- `GET /api/get_local_status` (protégé)
  - Renvoie un objet de statut consommé par `static/remote/ui.js`:
    - Champs typiques: `overall_status_text`, `status_text`, `overall_status_code_from_worker` (`idle|running|success|warning|error|unavailable`), `progress_current`, `progress_total`, `current_step_name`, `recent_downloads` (liste `{ filename, status }`).
  - En cas d'erreur HTTP, le frontend affiche un message adapté et peut déclencher un rechargement si la session a expiré (401).

> Note: `POST /api/trigger_local_workflow` peut être fourni par un service local/worker distinct. Si vous implémentez un proxy côté Flask, documentez le format attendu et la politique d'authentification.

> Dépréciation: Ces endpoints ne sont plus utilisés par le dashboard actuel basé sur `dashboard.html`. Conservez-les uniquement si vous avez des intégrations legacy qui en dépendent.

---
# Endpoints de test (CORS + API key)

Ces endpoints en lecture/écriture sont exposés sous `/api/test/*` pour permettre des tests cross-origin (CORS) depuis un frontend séparé (ex: `deployment/public_html/test-validation.html`).
Ils réutilisent la logique des endpoints protégés équivalents mais s'authentifient via une clé API au lieu des sessions.

- Authentification: header `X-API-Key: <TEST_API_KEY>`
- CORS: autoriser votre domaine via `CORS_ALLOWED_ORIGINS` (voir `configuration.md`)

Endpoints disponibles:
- `GET /api/test/get_webhook_config`
- `POST /api/test/update_webhook_config`
- `GET /api/test/get_polling_config`
- `GET /api/test/get_webhook_time_window`
- `POST /api/test/set_webhook_time_window`
- `GET /api/test/get_processing_prefs`
- `POST /api/test/update_processing_prefs`
- `GET /api/test/webhook_logs?days=N` (N=1..7)
 - `POST /api/test/clear_email_dedup`
 - `GET /api/test/get_runtime_flags`
 - `POST /api/test/update_runtime_flags`

Exemple d'appel (JS):
```js
fetch('https://votre-backend.tld/api/test/get_webhook_config', {
  headers: { 'X-API-Key': '<TEST_API_KEY>' }
}).then(r => r.json()).then(console.log)
```

Exemple d'appel (curl):
```bash
curl -sS -H 'X-API-Key: <TEST_API_KEY>' \
  https://votre-backend.tld/api/test/webhook_logs?days=7 | jq .
```

Exemples supplémentaires (curl):

```bash
# Effacer un email ID de la déduplication (utile pour re-traiter un message)
curl -sS -H 'X-API-Key: <TEST_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"email_id":"<ID_A_SUPPRIMER>"}' \
  https://votre-backend.tld/api/test/clear_email_dedup | jq .

# Récupérer les runtime flags (CORS)
curl -sS -H 'X-API-Key: <TEST_API_KEY>' \
  https://votre-backend.tld/api/test/get_runtime_flags | jq .

# Mettre à jour les runtime flags (CORS)
curl -sS -H 'X-API-Key: <TEST_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"disable_email_id_dedup": false, "allow_custom_webhook_without_links": true}' \
  https://votre-backend.tld/api/test/update_runtime_flags | jq .
```

Notes:
- Les URLs sensibles sont masquées côté lecture; envoyez l'URL complète pour modifier.
- La validation/normalisation des horaires et des listes (jours actifs, emails) est effectuée côté serveur.
- Les endpoints de test n'affectent pas l'authentification par session et n'exposent pas d'autres routes protégées.

## Runtime Flags (protégés)

Ces endpoints permettent de gérer les flags runtime pour le contrôle dynamique des fonctionnalités de débogage.

- `GET /api/get_runtime_flags` (protégé)
  - Retourne les flags runtime actuels chargés depuis `debug/runtime_flags.json` ou valeurs par défaut.
  - Réponse: `{ "success": true, "flags": { "disable_email_id_dedup": bool, "allow_custom_webhook_without_links": bool } }`

- `POST /api/update_runtime_flags` (protégé)
  - Met à jour les flags runtime et les persiste dans `debug/runtime_flags.json`.
  - Corps JSON: { "disable_email_id_dedup": bool, "allow_custom_webhook_without_links": bool }
  - Réponse: { "success": true, "message": "Flags mis à jour." }

## Redémarrage Serveur (protégé)

- `POST /api/restart_server` (protégé)
  - Programme un redémarrage du serveur via systemd (`systemctl restart render-signal-server`).
  - Nécessite la configuration sudoers pour l'utilisateur service.
  - Réponse: { "success": true, "message": "Redémarrage en cours..." }

## Préférences de Traitement (protégés)

- `GET /api/get_processing_prefs` (protégé)
  - Retourne les préférences de traitement actuelles (max_email_size_mb, require_attachments, exclude_keywords, retry_count, retry_delay_sec, webhook_timeout_sec).
  - Réponse: { "success": true, "prefs": { ... } }

- `POST /api/update_processing_prefs` (protégé)
  - Met à jour les préférences de traitement.
  - Corps JSON: champs optionnels comme max_email_size_mb, etc.
  - Réponse: { "success": true, "message": "Préférences mises à jour." }

## Endpoints de Test Supplémentaires (CORS-enabled avec X-API-Key)

En plus des endpoints de test déjà documentés, les suivants sont disponibles:

- `POST /api/test/clear_email_dedup`
  - Efface un email ID spécifique de la déduplication Redis (utile pour débogage).
  - Headers: X-API-Key
  - Corps JSON: { "email_id": "<id>" }
  - Réponse: { "success": true, "removed": bool, "email_id": "<id>" }

- `GET /api/test/get_runtime_flags`
  - Equivalent CORS de `/api/get_runtime_flags`.

- `POST /api/test/update_runtime_flags`
  - Equivalent CORS de `/api/update_runtime_flags`.
