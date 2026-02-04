# Gmail Push Ingress Endpoint

**Date** : 2026-02-03  
**Version** : 1.0  
**Statut** : Production Ready

---

## Vue d’ensemble

L’endpoint `POST /api/ingress/gmail` permet à un script Google Apps Script (ou tout client externe) de pousser directement des e‑mails dans l’application, contournant les limitations du polling IMAP tout en préservant tous les garde‑fous existants (authentification, déduplication, fenêtres horaires, pattern matching, routing dynamique).

---

## Architecture du flux

```
Apps Script Gmail → POST /api/ingress/gmail → AuthService → Orchestrator → Webhooks
```

### Étapes principales

1. **Authentification** – Vérification du Bearer token (`PROCESS_API_TOKEN`) via `AuthService.verify_api_key_from_request()`.
2. **Validation payload** – JSON obligatoire avec champs `subject`, `sender`, `body`, `date` (optionnels sauf `sender` et `body`).
3. **Déduplication** – Génération d’un `email_id` MD5 et vérification Redis (`is_email_id_processed_redis`).
4. **Allowlist expéditeurs** – Lecture dynamique depuis `PollingConfigService.get_sender_list()`. Si l’expéditeur n’est pas autorisé, le message est marqué comme traité (skip silencieux).
5. **Fenêtres horaires** – Application des règles globales (`_load_webhook_global_time_window`) avec exceptions par détecteur (DESABO urgent, RECADRAGE hors fenêtre).
6. **Pattern matching** – Détection Media Solution / DESABO via `pattern_matching.*`.
7. **Routing dynamique** – Évaluation des règles `RoutingRulesService` avant envoi webhook par défaut.
8. **Envoi webhook** – Délégation à `orchestrator.send_custom_webhook_flow()` avec injection des dépendances (rate limiting, logs, R2, etc.).

---

## Spécification API

### Endpoint

```
POST /api/ingress/gmail
Content-Type: application/json
Authorization: Bearer <PROCESS_API_TOKEN>
```

### Payload JSON

| Champ | Type | Requis | Description |
|-------|------|---------|-------------|
| `subject` | string | ❌ | Sujet de l’e‑mail (vide si absent) |
| `sender` | string | ✅ | Expéditeur brut (ex: `"Nom <email@domain.com>"`) |
| `body` | string | ✅ | Corps de l’e‑mail (plain text, HTML autorisé) |
| `date` | string | ❌ | Date/heure ISO 8601 (ex: `"2026-02-03T15:30:00Z"`) |

### Réponses

| Code | Statut | Description |
|------|--------|-------------|
| `200` | `processed` | E‑mail traité avec succès, webhook envoyé |
| `200` | `already_processed` | E‑mail déjà traité (doublon) |
| `200` | `skipped_sender_not_allowed` | Expéditeur non autorisé, marqué traité |
| `200` | `skipped_outside_time_window` | Hors fenêtre horaire (RECADRAGE) |
| `400` | `Invalid JSON payload` | Corps JSON invalide |
| `400` | `Missing field: sender|body` | Champs obligatoires manquants |
| `401` | `Unauthorized` | Token manquant ou invalide |
| `409` | `Webhook sending disabled` | Envoi webhooks désactivé |
| `409` | `Outside time window` | Hors fenêtre horaire (autres détecteurs) |
| `500` | `Internal error` | Erreur serveur inattendue |

### Exemple de réponse réussie

```json
{
  "success": true,
  "status": "processed",
  "email_id": "a1b2c3d4e5f67890abcd1234ef567890",
  "flow_result": {
    "webhook_sent": true,
    "webhook_url": "https://example.com/webhook",
    "delivery_links": ["https://www.dropbox.com/scl/fo/abc123"]
  },
  "timestamp_utc": "2026-02-03T15:30:00Z"
}
```

---

## Intégration Apps Script

### Prérequis

- `PROCESS_API_TOKEN` configuré côté Render (variable d’environnement obligatoire).
- URL de l’endpoint : `https://<render-domain>/api/ingress/gmail`.
- Gestion des erreurs côté Apps Script (retries 429/500).

### Exemple de code Apps Script

```javascript
function pushEmailToIngress(subject, sender, body, date) {
  const url = "https://render-signal-server-latest.onrender.com/api/ingress/gmail";
  const token = PropertiesService.getScriptProperties().getProperty("PROCESS_API_TOKEN");
  
  const payload = {
    subject: subject || "",
    sender: sender,
    body: body,
    date: date || new Date().toISOString()
  };
  
  const options = {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(url, options);
  const result = JSON.parse(response.getContentText());
  
  if (result.success) {
    Logger.log("Email pushed: " + result.status);
  } else {
    Logger.log("Push failed: " + result.message);
  }
  
  return result;
}
```

---

## Comportements spécifiques

### Allowlist expéditeurs

- Si `PollingConfigService.get_sender_list()` retourne une liste non vide, seuls les expéditeurs autorisés sont acceptés.
- En cas de refus, l’e‑mail est marqué comme traité pour éviter les tentatives répétées.

### Fenêtres horaires

- **DESABO non urgent** : bypass fenêtre si `early_ok` (comportement standard).
- **DESABO urgent** : ne contourne pas la fenêtre → 409 si hors créneau.
- **RECADRAGE** : skip + marqué traité hors fenêtre pour éviter les re‑traitements.

### Routing dynamique

- Les règles `RoutingRulesService` sont évaluées avant l’envoi webhook par défaut.
- Le flag `stop_processing` est respecté.
- Le payload enrichi inclut `source: "gmail_push"`.

### Offload R2

- Si `R2_FETCH_ENABLED=true`, les liens Dropbox/FromSmash/SwissTransfer sont offloadés vers R2.
- Le payload webhook inclut les paires `source_url`/`r2_url` et `original_filename`.

#### Helper `_maybe_enrich_delivery_links_with_r2`

- **Localisation** : `routes/api_ingress.py` avant l'appel à `send_custom_webhook_flow()`.
- **Pipeline** :
  1. Vérifie que `R2TransferService` est disponible et activé (`R2_FETCH_ENABLED=true` + endpoint configuré).
  2. Normalise chaque `raw_url` et garantit un `direct_url` fallback avant tout offload.
  3. Adapte le timeout remote fetch en fonction du provider (15s par défaut, 120s pour Dropbox `/scl/fo/`).
  4. Enrichit chaque entrée avec `r2_url`/`original_filename` lorsqu'un tuple `(url, filename)` est retourné.
  5. Persiste la paire via `R2TransferService.persist_link_pair()` pour que le backend PHP puisse la logger.

- **Résilience** :
  - Tous les appels sont best-effort : exception → warning + continuité du flux (webhook envoyé avec URLs sources).
  - Les logs `R2_TRANSFER` sont produits même côté ingress pour suivre les succès/échecs Gmail.
  - Les timeouts/fallbacks sont alignés sur l'orchestrateur IMAP afin de conserver un comportement homogène entre polling et push.

- **Tests associés** :
  - `test_ingress_gmail_enriches_delivery_links_with_r2_when_enabled`
  - `test_ingress_gmail_r2_errors_do_not_block_send`
  Ces tests valident que l'enrichissement est présent lorsqu'il réussit et que l'envoi webhook n'est jamais bloqué lorsque le Worker R2 échoue.

---

## Sécurité

- **Authentification** : Bearer token obligatoire (`PROCESS_API_TOKEN`).
- **Validation** : Payload JSON strict, champs obligatoires vérifiés.
- **Logging** : Tous les événements sont logués avec `INGRESS:` préfixe, PII masqués.
- **Rate limiting** : Hérité de `rate_limit_allow_send` global.

---

## Tests

Les tests unitaires couvrent tous les scénarios :

- `test_ingress_gmail_unauthorized` – 401 sans token
- `test_ingress_gmail_invalid_json_payload` – 400 JSON invalide
- `test_ingress_gmail_missing_required_fields` – 400 champs manquants
- `test_ingress_gmail_skips_sender_not_allowed` – 200 skip allowlist
- `test_ingress_gmail_webhook_sending_disabled` – 409 webhooks désactivés
- `test_ingress_gmail_skips_recadrage_outside_time_window` – 200 skip fenêtre
- `test_ingress_gmail_happy_path` – 200 processed

Commande d’exécution :

```bash
pytest tests/routes/test_api_ingress.py -v
```

---

## Monitoring

- **Logs** : Préfixe `INGRESS:` dans les logs applicatifs.
- **Métriques** : Inclus dans les métriques locales du dashboard (compteur d’ingress).
- **Webhook logs** : Persistance Redis via `append_webhook_log` avec `source: "gmail_push"`.

---

## Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| 401 Unauthorized | `PROCESS_API_TOKEN` manquant ou incorrect | Vérifier la variable d’environnement Render |
| 400 Missing field | Apps Script n’envoie pas `sender` ou `body` | Corriger le payload côté Apps Script |
| 409 Webhook sending disabled | Flag `webhook_sending_enabled` à false | Activer via dashboard ou API |
| 200 skipped_sender_not_allowed | Expéditeur non dans l’allowlist polling | Ajouter l’expéditeur via dashboard polling config |
| 200 skipped_outside_time_window | Email RECADRAGE hors fenêtre horaire | Ajuster la fenêtre ou envoyer pendant les heures d’ouverture |

---

## Évolutions prévues

- **Signature HMAC optionnelle** pour renforcer la sécurité côté Apps Script.
- **Batch mode** pour accepter plusieurs e‑mails dans un seul appel.
- **Webhook de callback** pour notifier Apps Script des échecs de traitement.

---

## Références

- Code source : `routes/api_ingress.py`
- Tests : `tests/routes/test_api_ingress.py`
- Services utilisés : `AuthService`, `PollingConfigService`, `RoutingRulesService`, `R2TransferService`
- Documentation associée : `docs/features/routing_rules_engine.md`, `docs/features/webhook_logs_redis.md`
