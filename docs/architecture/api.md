# API HTTP (Flask) - Architecture Orientée Services

L'API est organisée en plusieurs blueprints Flask pour une meilleure modularité, avec une architecture orientée services. Les services principaux sont injectés dans les blueprints pour une meilleure séparation des préoccupations.

## Architecture des Services

L'application utilise une architecture orientée services avec les composants principaux suivants :

| Service | Fichier | Description |
|---------|---------|-------------|
| `ConfigService` | `services/config_service.py` | Gestion de la configuration de l'application |
| `RuntimeFlagsService` | `services/runtime_flags_service.py` | Gestion des flags de runtime (singleton) |
| `WebhookConfigService` | `services/webhook_config_service.py` | Configuration des webhooks (singleton) |
| `DeduplicationService` | `services/deduplication_service.py` | Gestion de la déduplication (Redis ou mémoire) |
| `AuthService` | `services/auth_service.py` | Authentification et autorisation |
| `PollingConfigService` | `config/polling_config.py` | Configuration du polling IMAP |
| `MagicLinkService` | `services/magic_link_service.py` | Génération/validation magic links HMAC (singleton) |
| `R2TransferService` | `services/r2_transfer_service.py` | Offload Cloudflare R2 (fetch distant + persistance des paires source/R2) |

## Organisation des routes

L'API est structurée en blueprints Flask pour une meilleure organisation et maintenabilité. Voici la structure complète :

| Blueprint | Fichier | Services Injectés | Description |
|-----------|---------|------------------|-------------|
| `health` | `routes/health.py` | - | Vérification de l'état du service |
| `dashboard` | `routes/dashboard.py` | `AuthService` | Interface utilisateur |
| `api_auth` | `routes/api_auth.py` | `MagicLinkService` | Génération de magic links (POST `/api/auth/magic-link`) |
| `api_webhooks` | `routes/api_webhooks.py` | `WebhookConfigService` | Gestion des webhooks |
| `api_polling` | `routes/api_polling.py` | `PollingConfigService` | Configuration du polling IMAP |
| `api_processing` | `routes/api_processing.py` | `ConfigService` | Préférences de traitement |
| `api_logs` | `routes/api_logs.py` | `WebhookLogger` | Consultation des logs |
| `api_test` | `routes/api_test.py` | - | Endpoints de test (CORS) |
| `api_utility` | `routes/api_utility.py` | - | Utilitaires (ping, trigger, statut) |
| `api_admin` | `routes/api_admin.py` | `ConfigService`, `AuthService` | Administration |
| `api_config` | `routes/api_config.py` | `RuntimeFlagsService`, `PollingConfigService` | Configuration |

## Routes Principales

### Authentification
- `POST /login` - Connexion utilisateur
- `GET /logout` - Déconnexion

### Webhooks
- `GET /api/webhooks/config` - Récupérer la configuration
- `POST /api/webhooks/config` - Mettre à jour la configuration
- `GET /api/webhooks/time-window` - Récupérer la fenêtre horaire
- `POST /api/webhooks/time-window` - Mettre à jour la fenêtre horaire

### Configuration
- `GET /api/get_runtime_flags` - Récupérer les flags de runtime
- `POST /api/update_runtime_flags` - Mettre à jour les flags de runtime
- `GET /api/get_polling_config` - Récupérer la configuration du polling
- `POST /api/update_polling_config` - Mettre à jour la configuration du polling

### Administration
- `POST /api/restart_server` - Redémarrer le serveur
- `POST /api/deploy_application` - Déployer la dernière version
- `POST /api/check_emails_and_download` - Vérifier les emails manuellement

### Logs
- `GET /api/webhook_logs` - Récupérer les logs des webhooks

### Integration services-first

- `api_config` s’appuie directement sur `RuntimeFlagsService.get_instance()` et `PollingConfigService` pour lire/mettre à jour la configuration (flags, fenêtres horaires, polling) @routes/api_config.py#27-367.
- `api_webhooks` consomme `WebhookConfigService` pour charger/persister la configuration webhook (validation HTTPS, normalisation Make.com, cache + store externe) @routes/api_webhooks.py.
- `api_admin` et `dashboard` récupèrent les dépendances via `ConfigService`/`AuthService` initialisés dans `app_render.py`.
- Les tests d’intégration privilégient les appels API-first (GET/POST) pour vérifier la cohérence entre services et routes @tests/test_routes_*.

## Authentification

Toutes les routes de l'API (sauf `/health` et `/login`) nécessitent une authentification. L'authentification se fait via des sessions Flask avec Flask-Login.

### Connexion

- `POST /login`
  - Paramètres : `username`, `password` (form-data ou JSON)
  - Réponse en cas de succès : Redirection vers `/`
  - Réponse en cas d'échec : Page de login avec message d'erreur

### Authentification par Magic Link

#### Génération d'un Magic Link

- `POST /api/auth/magic-link` (protégé)
  - **Nécessite une session utilisateur valide**
  - Corps JSON optionnel :
    ```json
    {
      "unlimited": false
    }
    ```
    - `unlimited` (booléen, optionnel) : Si `true`, génère un lien permanent (sans expiration)
  
  - Réponse en cas de succès (201) :
    ```json
    {
      "success": true,
      "magic_link": "https://example.com/dashboard/magic-link/token.1234567890.abcdef123456",
      "expires_at": "2024-12-31T23:59:59+00:00",
      "unlimited": false
    }
    ```
  
  - Réponses d'erreur :
    - 401 : Non authentifié
    - 403 : Accès refusé (si l'utilisateur n'a pas les droits)
    - 500 : Erreur serveur

#### Utilisation d'un Magic Link

- `GET /dashboard/magic-link/<token>`
  - Valide et consomme le token de magic link
  - Redirige vers le tableau de bord si le token est valide
  - Affiche une page d'erreur si le token est invalide ou expiré
  
  - Réponses :
    - 302 : Redirection vers le tableau de bord (succès)
    - 400 : Token invalide ou expiré
    - 403 : Accès refusé (lien déjà utilisé ou révoqué)

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

-### Récupération des flags

- `GET /api/get_runtime_flags` (protégé)
  - Retourne les flags runtime actuels: `disable_email_id_dedup`, `allow_custom_webhook_without_links`.
  - Réponse :
    ```json
    {
      "success": true,
      "flags": {
        "disable_email_id_dedup": false,
        "allow_custom_webhook_without_links": false
      }
    }
    ```

### Mise à jour des flags

- `POST /api/update_runtime_flags` (protégé)
  - Met à jour les flags runtime et les persiste dans `debug/runtime_flags.json`.
  - Implémentation via `RuntimeFlagsService.update_flags()` (mise à jour atomique + invalidation du cache TTL 60s).
  - Corps JSON (champs optionnels) :
    ```json
    {
      "disable_email_id_dedup": true,
      "allow_custom_webhook_without_links": true
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Modifications enregistrées. Un redémarrage peut être nécessaire." }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

### Configuration de la fenêtre horaire des webhooks

#### Récupération de la fenêtre horaire

- `GET /api/webhooks/time-window` (protégé)
  - Récupère la configuration actuelle de la fenêtre horaire des webhooks
  - Réponse :
    ```json
    {
      "success": true,
      "webhooks_time_start": "09h00",
      "webhooks_time_end": "18h00"
    }
    ```

#### Mise à jour de la fenêtre horaire

- `POST /api/webhooks/time-window` (protégé)
  - Met à jour la fenêtre horaire des webhooks
  - Corps JSON :
    ```json
    {
      "start": "09h00",
      "end": "18h00"
    }
    ```
  - Formats acceptés : `HHhMM`, `HH:MM`, `HHh`, `HH` (normalisés en `HHhMM`)
  - Pour désactiver : `"start": null, "end": null`
  - Réponses :
    - 200 : `{ "success": true, "message": "Time window updated.", "webhooks_time_start": "09h00", "webhooks_time_end": "18h00" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)

Exemples curl:

```bash
# 1) Login et stockage des cookies
curl -sSL -c cookies.txt -b cookies.txt \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<USERNAME>&password=<PASSWORD>" \
  https://DOMAIN/login -o /dev/null

# (Présence) Les endpoints de test de présence ont été supprimés.
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

### Webhook principal (payload custom)

```json
{
  "microsoft_graph_email_id": "<email_id>",
  "subject": "Sujet de l'email",
  "receivedDateTime": "2025-10-16T14:25:00Z",
  "sender_address": "expediteur@example.com",
  "bodyPreview": "Résumé du message",
  "email_content": "Contenu complet (texte + HTML nettoyé)",
  "delivery_links": [
    {
      "provider": "swisstransfer",
      "raw_url": "https://www.swisstransfer.com/d/...",
      "direct_url": "https://www.swisstransfer.com/d/...",
      "r2_url": "https://media.example.com/swisstransfer/f9e8d7c6/b5a4c3d2/file",
      "original_filename": "archive.zip"
    },
    {
      "provider": "dropbox",
      "raw_url": "https://www.dropbox.com/s/abc123/file.zip?dl=0",
      "direct_url": "https://www.dropbox.com/s/abc123/file.zip?dl=1",
      "r2_url": "https://media.example.com/dropbox/a1b2c3d4/e5f6g7h8/file.zip",
      "original_filename": "61 Camille.zip"
    },
    {
      "provider": "fromsmash",
      "raw_url": "https://fromsmash.com/ABC123",
      "direct_url": "https://fromsmash.com/ABC123",
      "r2_url": "https://media.example.com/fromsmash/c4d5e6f7/a8b9c0d1/file",
      "original_filename": "archive.zip"
    }
  ],
  "first_direct_download_url": null,
  "dropbox_urls": [],
  "dropbox_first_url": null
}
```

Notes :

- Les champs reflètent `email_processing/payloads.py::build_custom_webhook_payload()`.
- `delivery_links` contient toujours `raw_url` et peut aussi inclure :
  - `direct_url` : URL de téléchargement direct (si déterminée)
  - `r2_url` : URL Cloudflare R2 si l'offload a réussi (prioritaire pour le téléchargement)
  - `original_filename` : Nom de fichier d'origine extrait depuis `Content-Disposition` (servi par le Worker via `httpMetadata.contentDisposition`)
- **Stratégie de priorité recommandée pour les récepteurs** :
  1. Utiliser `r2_url` si présent (téléchargement plus rapide, économe en bande passante)
  2. Sinon utiliser `direct_url` (téléchargement direct depuis la source)
  3. En fallback utiliser `raw_url` (URL originale)
- Les champs `dropbox_*` sont fournis pour compatibilité legacy.
- La présence de `r2_url` dépend du succès de l'offload R2 (voir `docs/r2_offload.md`)

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

### En-têtes de sécurité

L'application inclut les en-têtes de sécurité HTTP suivants :

- `Content-Security-Policy` : Restreint les sources de contenu autorisées
- `X-Content-Type-Options: nosniff` : Empêche le MIME-sniffing
- `X-Frame-Options: DENY` : Empêche le clickjacking
- `X-XSS-Protection: 1; mode=block` : Active la protection XSS des navigateurs
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` : Force l'utilisation de HTTPS
- `Referrer-Policy: strict-origin-when-cross-origin` : Contrôle les informations de référent envoyées

> À ce stade, aucune protection CSRF n'est implémentée côté serveur. Les clients doivent s'appuyer sur les sessions authentifiées et/ou une clé API (`X-API-Key`) selon le blueprint utilisé.

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
  - Retourne la configuration actuelle des webhooks, fusion des valeurs persistées et des valeurs par défaut d'environnement.
  - Le champ `webhook_url` est masqué (suffixe `***`) côté lecture pour éviter d'exposer l'URL complète dans l'interface.
  - Réponse:
    ```json
    {
      "success": true,
      "config": {
        "webhook_url": "https://webhook.example.com/***",
        "webhook_ssl_verify": true,
        "webhook_sending_enabled": true,
        "webhook_time_start": "09h00",
        "webhook_time_end": "18h00",
        "absence_pause_enabled": false,
        "absence_pause_days": []
      }
    }
    ```

- `POST /api/webhooks/config` (protégé)
  - Met à jour la configuration des webhooks. Tous les champs sont optionnels et sont fusionnés avec la configuration courante.
  - **Validation** :
    - `webhook_url` doit être une URL **HTTPS** sinon la requête est rejetée (`400`).
    - `absence_pause_days` doit être une liste de jours valides (`monday` → `sunday`). Les valeurs sont normalisées côté serveur (`strip()` + `lower()`) avant comparaison;
    - au moins un jour doit être présent si `absence_pause_enabled` est `true`, sinon la requête échoue (`400`).
  - Corps JSON :
    ```json
    {
      "webhook_url": "https://webhook.example.com/endpoint",
      "webhook_ssl_verify": false,
      "webhook_sending_enabled": false,
      "webhook_time_start": "09h00",
      "webhook_time_end": "18h00",
      "absence_pause_enabled": true,
      "absence_pause_days": ["monday", "friday"]
    }
    ```
  - Réponses :
    - 200 : `{ "success": true, "message": "Configuration des webhooks mise à jour avec succès" }`
    - 400 : `{ "success": false, "message": "..." }` (erreur de validation)
    - 500 : `{ "success": false, "message": "..." }` (erreur serveur)
  - `webhook_sending_enabled` contrôle l'envoi global des webhooks personnalisés. S'il est positionné à `false`, le poller continue de traiter les emails mais n'enverra pas de requêtes HTTP sortantes tant que le flag n'est pas réactivé.
  - Lorsque `absence_pause_enabled` est activé et que le jour courant est listé, `_is_webhook_sending_enabled()` retourne `false` et le poller sort immédiatement du cycle (log `ABSENCE_PAUSE`) sans ouvrir de connexion IMAP.

### Gestion des fenêtres horaires

- Voir la section « Configuration de la fenêtre horaire des webhooks » ci-dessus. Les endpoints renvoient/acceptent des champs `webhooks_time_start` et `webhooks_time_end` (formats `HHhMM`/`HH:MM`).

### Contrôle du polling (via configuration `api_config`)

- `GET /api/get_polling_config` (protégé)
  - Retourne la configuration courante en fusionnant les valeurs persistées et les alias runtime (`settings.POLLING_ACTIVE_*`).
  - Réponse :
    ```json
    {
      "success": true,
      "config": {
        "active_days": [0, 1, 2, 3, 4],
        "active_start_hour": 9,
        "active_end_hour": 18,
        "enable_subject_group_dedup": true,
        "sender_of_interest_for_polling": ["contact@example.com"],
        "vacation_start": null,
        "vacation_end": null,
        "enable_polling": true
      }
    }
    ```

- `POST /api/update_polling_config` (protégé)
  - Met à jour la configuration du polling (jours, heures, dédup, expéditeurs, période de vacances, flag `enable_polling`).
  - Réponses :
    - 200 : `{ "success": true, "message": "Configuration polling mise à jour. Un redémarrage peut être nécessaire." }`
    - 400 / 500 en cas d'erreur de validation ou d'I/O.
  - Notes : la modification du flag `enable_polling` nécessite un redémarrage pour affecter le thread de fond.

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
  - `POST /api/toggle_polling` (legacy)
  - `POST /api/polling/toggle` (legacy, maintien tests)

- Dépréciés (télécommande):
  - `GET /api/get_local_status`
  - `POST /api/trigger_local_workflow`

Ces endpoints peuvent être supprimés définitivement si aucune intégration externe ne les utilise encore.

## Sécurité

- Les routes marquées (protégé) nécessitent une session utilisateur (Flask-Login).
- Configurez `FLASK_SECRET_KEY`, `DASHBOARD_USER`, `DASHBOARD_PASSWORD` via env vars.

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
  - Réponse: `{ "success": true, "webhooks_time_start": "HHhMM"|null, "webhooks_time_end": "HHhMM"|null }`

- `POST /api/webhooks/time-window`
  - Définit la fenêtre horaire pour l'envoi des webhooks
  - Corps JSON: `{ "start": "11h30"|""|null, "end": "17h30"|""|null }`
  - Réponses:
    - 200: `{ "success": true, "message": "Time window updated.", "webhooks_time_start": "HHhMM"|null, "webhooks_time_end": "HHhMM"|null }`
    - 400: `{ "success": false, "message": "..." }`
  - Notes:
    - Si start et end sont tous deux vides (ou null), la contrainte est désactivée
    - Formats acceptés: `HHhMM` ou `HH:MM` (ex: "09h30", "17:45")

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

## Déploiement applicatif (protégé)

- `POST /api/deploy_application` (protégé)
  - Déclenche un déploiement de l'application selon l'ordre de préférence suivant:
    1) Render Deploy Hook si `RENDER_DEPLOY_HOOK_URL` est défini (validation de préfixe + masquage de clé dans les logs)
    2) Render API si `RENDER_API_KEY` et `RENDER_SERVICE_ID` sont définis (payload `{ clearCache: <bool> }`)
    3) Fallback local via commande shell `DEPLOY_CMD` (par défaut: reload-or-restart du service + reload Nginx)
  - Exemples de réponses:
    - 200: `{ "success": true, "message": "Déploiement Render déclenché via Deploy Hook." }`
    - 200: `{ "success": true, "message": "Déploiement Render lancé (voir dashboard Render).", "deploy_id": "...", "status": "queued" }`
    - 200: `{ "success": true, "message": "Déploiement planifié (fallback local)." }`
    - 502: `{ "success": false, "message": "Render API error: ..." }`
  - Variables d'environnement: voir `docs/configuration.md` (RENDER_API_KEY, RENDER_SERVICE_ID, RENDER_DEPLOY_HOOK_URL, RENDER_DEPLOY_CLEAR_CACHE, DEPLOY_CMD)

## Préférences de Traitement (protégés)

- `GET /api/processing_prefs` (protégé)
  - Retourne les préférences de traitement actuelles (max_email_size_mb, require_attachments, exclude_keywords, retry_count, retry_delay_sec, webhook_timeout_sec, mirror_media_to_custom).
  - Réponse: { "success": true, "prefs": { ... } }

- `POST /api/processing_prefs` (protégé)
  - Met à jour les préférences de traitement.
  - Corps JSON: champs optionnels comme max_email_size_mb, etc.
  - Réponse: { "success": true, "message": "Préférences mises à jour.", "prefs": { ... } }

### Endpoints Legacy (compatibilité)

Pour maintenir la compatibilité avec l'UI et les tests existants, les alias suivants sont disponibles:
- `GET /api/get_processing_prefs` → redirige vers `GET /api/processing_prefs`
- `POST /api/update_processing_prefs` → redirige vers `POST /api/processing_prefs`

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

## Fonctionnalités supprimées

### Automation Make (Presence)
- **Statut** : Supprimée en 2025-11-18 lors du refactoring
- **Raison** : Simplification de la maintenance et réduction de la complexité
- **Remplacement** : Utilisation directe des webhooks personnalisés via l interface dashboard
- **Impact** : Les endpoints PRESENCE_* et MAKE_* automatisés ne sont plus disponibles
