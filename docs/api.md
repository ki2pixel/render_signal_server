# API HTTP (Flask)

L'API est organisée en plusieurs blueprints Flask pour une meilleure modularité. Les routes sont documentées ci-dessous par catégorie fonctionnelle.

## Organisation des routes

L'API est structurée en blueprints Flask pour une meilleure organisation et maintenabilité. Voici la structure complète :

| Blueprint | Fichier | Description | Routes Principales |
|-----------|---------|-------------|-------------------|
| `health` | `routes/health.py` | Vérification de l'état du service | `GET /health` |
| `dashboard` | `routes/dashboard.py` | Interface utilisateur | `GET /`, `/login`, `/logout` |
| `api_webhooks` | `routes/api_webhooks.py` | Gestion des webhooks | `GET/POST /api/webhooks/config` |
| `api_polling` | `routes/api_polling.py` | Contrôle du polling | `POST /api/polling/toggle` |
| `api_processing` | `routes/api_processing.py` | Préférences de traitement | `GET/POST /api/processing_prefs` |
| `api_logs` | `routes/api_logs.py` | Consultation des logs | `GET /api/webhook_logs` |
| `api_test` | `routes/api_test.py` | Endpoints de test (CORS) | `GET /api/test/*` |
| `api_utility` | `routes/api_utility.py` | Utilitaires (ping, trigger, statut local) | `GET /api/ping`, `GET /api/check_trigger`, `GET /api/get_local_status` |
| `api_admin` | `routes/api_admin.py` | Admin (présence, redémarrage, déclenchement manuel) | `POST /api/test_presence_webhook`, `POST /api/restart_server`, `POST /api/check_emails_and_download` |
| `api_config` | `routes/api_config.py` | Config protégée (fenêtre horaire, flags, polling) | `GET/POST /api/get|set_webhook_time_window`, `GET/POST /api/get|update_runtime_flags`, `GET/POST /api/get|update_polling_config` |

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

### Test manuel des webhooks Make (présence)

- `POST /api/test_presence_webhook` (protégé)
  - Déclenche manuellement un webhook Make vers l'URL de présence configurée.
  - Paramètres acceptés (JSON ou form):
    - `presence`: `"true"|"false"` (obligatoire) — choisit l'URL `PRESENCE_TRUE_MAKE_WEBHOOK_URL` ou `PRESENCE_FALSE_MAKE_WEBHOOK_URL`.
  - Réponses:
    - 200: `{ "success": true, "presence": bool, "used_url": string }`
    - 400: `{ "success": false, "message": string }` (paramètre manquant ou URL non configurée)
    - 500: `{ "success": false, "message": string }` (échec d'envoi)
  - Notes:
    - Nécessite une session (voir Auth plus haut). Identifiants via env: `TRIGGER_PAGE_USER`, `TRIGGER_PAGE_PASSWORD`.
    - Les URLs de destination doivent être configurées: `PRESENCE_TRUE_MAKE_WEBHOOK_URL`, `PRESENCE_FALSE_MAKE_WEBHOOK_URL`.
    - Le payload inclut `subject`, `sender_email`, `email_id` de test et `extra_payload` `{ presence, detector: "manual_test" }`.

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

  Note: le backend extrait des URLs de livraison multi-fournisseurs (Dropbox, FromSmash, SwissTransfer) lors du traitement des e-mails via `check_media_solution_pattern()` (voir `email_polling.md` pour les détails, exemples, et règles d'extraction/normalisation).
  Note (payload simplifié): lorsque des e-mails valides sont traités, le payload de webhook inclut `delivery_links` comme liste d'objets `{ provider, raw_url }` (lien vers la page d'atterrissage du fournisseur). Les champs `direct_url`, `first_direct_download_url`, `dropbox_urls` et `dropbox_first_url` ne sont plus envoyés.

## Dashboard Webhooks (endpoints via Blueprints)

Les endpoints suivants (utilisés par `dashboard.html`) sont désormais organisés via des Blueprints Flask.

### Configuration des webhooks

- `GET /api/webhooks/config` (protégé)
  - Retourne la configuration actuelle des webhooks (URLs masquées partiellement pour sécurité)
  - Réponse: `{ "success": true, "config": {
        "webhook_url": "https://...",
        "recadrage_webhook_url": "https://...",
        "autorepondeur_webhook_url": "https://...",
        "presence_true_url": "https://...|alias",
        "presence_false_url": "https://...|alias",
        "presence_flag": bool,
        "webhook_ssl_verify": bool,
        "polling_enabled": bool
    } }`

- `POST /api/webhooks/config` (protégé)
  - Met à jour la configuration des webhooks de manière dynamique
  - Corps JSON (champs optionnels, seuls les fournis sont pris en compte):
    - `webhook_url`: string (HTTPS conseillé)
    - `recadrage_webhook_url`: string | alias `<token>@hook.eu2.make.com`
    - `autorepondeur_webhook_url`: string | alias `<token>@hook.eu2.make.com`
    - `presence_true_url`: string | alias `<token>@hook.eu2.make.com`
    - `presence_false_url`: string | alias `<token>@hook.eu2.make.com`
    - `presence_flag`: bool
    - `webhook_ssl_verify`: bool
  - Réponses:
    - 200: `{ "success": true, "message": "Configuration mise à jour avec succès." }`
    - 400: `{ "success": false, "message": "..." }` (validation échouée)
    - 500: `{ "success": false, "message": "..." }` (erreur interne)

### Contrôle du polling

- `POST /api/polling/toggle` (protégé)
  - Active ou désactive le polling IMAP dynamiquement
  - Corps JSON: `{ "enable": true|false }`
  - Note: Nécessite un redémarrage du serveur pour prise en compte complète
  - Réponse: `{ "success": true, "message": "...", "polling_enabled": bool }`

### Configuration du Polling (jours/heures/déduplication + vacances)

- `GET /api/get_polling_config` (protégé)
  - Retourne la configuration persistée côté serveur (`debug/polling_config.json`)
  - Réponse: `{ "success": true, "config": {
      "active_days": [0..6],
      "active_start_hour": 9,
      "active_end_hour": 23,
      "enable_subject_group_dedup": true,
      "sender_of_interest_for_polling": ["email1@example.com", ...],
      "vacation_start": "YYYY-MM-DD|null",
      "vacation_end": "YYYY-MM-DD|null"
    } }`

- `POST /api/update_polling_config` (protégé)
  - Met à jour la configuration de polling. Les champs sont optionnels (merge partiel) :
    - `active_days`: array d'entiers 0..6 (0=lundi)
    - `active_start_hour`: int 0..23
    - `active_end_hour`: int 0..23
    - `enable_subject_group_dedup`: bool
    - `sender_of_interest_for_polling`: array d'emails (validés/normalisés)
    - `vacation_start`: `YYYY-MM-DD` | null
    - `vacation_end`: `YYYY-MM-DD` | null
  - Réponses:
    - 200: `{ "success": true, "message": "Configuration polling enregistrée." }`
    - 400: `{ "success": false, "message": "..." }` (validation échouée)
    - 500: `{ "success": false, "message": "..." }`

## Endpoints legacy (dépréciés ou supprimés)

- Supprimés lors de l'Étape 5 (refactoring routes → blueprints):
  - `GET /api/get_webhook_config` → remplacé par `GET /api/webhooks/config`
  - `POST /api/update_webhook_config` → remplacé par `POST /api/webhooks/config`
  - `POST /api/toggle_polling` → remplacé par `POST /api/polling/toggle`

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
