# Monitoring

**TL;DR** : `/health` reste volontairement minimal (`{"status": "ok"}`) pour les sondes Render. Les métriques détaillées vivent dans `/api/diag/runtime`, les logs webhook dans `WebhookLoggerService`, et le dashboard rafraîchit les logs toutes les 30 secondes en pause quand l'onglet est masqué.

---

## Le problème : un service qui tombe sans prévenir

Le serveur pouvait perdre des webhooks sans que personne ne le sache. Les symptômes classiques :

- Render redémarre le service, aucune alerte ne part.
- Le poller IMAP legacy meurt, les emails s'accumulent.
- Un webhook échoue en boucle, noyé dans des logs non structurés.
- Le dashboard affiche « opérationnel » alors que le dernier envoi date de trois jours.

Un `/health` qui répond `ok` ne prouve rien d'autre que « Flask est vivant ». Il faut distinguer trois questions : le process tourne-t-il, le pipeline a-t-il traité quelque chose récemment, et l'interface voit-elle la même chose que le serveur.

---

## La solution : trois couches, pas une

### ❌ L'ancien monde : logs et espoir

```python
print("webhook envoyé")
# Pas de timestamp, pas d'identifiant, pas de statut
```

### ✅ Le nouveau monde : santé, métriques, journal

```python
# routes/health.py
@bp.route("/health", methods=["GET"])
def health() -> Response | tuple[Response, int]:
    return jsonify({"status": "ok"}), 200
```

Le endpoint public est minimal par choix. Il ne touche ni Redis, ni le disque, ni le réseau : une panne de dépendance ne provoque pas de redémarrage en boucle du conteneur.

Les détails sont sur `/api/diag/runtime` (protégé par session) :

```python
{
    "process_start_time": "2026-11-25T20:58:00+00:00",
    "uptime_sec": 2490,
    "last_poll_cycle_ts": null,
    "last_webhook_sent_ts": null,
    "bg_poller_thread_alive": false,
    "make_watcher_thread_alive": false,
    "enable_background_tasks": false,
    "server_time_utc": "2026-11-25T21:39:00+00:00"
}
```

`process_start_time` est posé à l'initialisation du singleton. `last_poll_cycle_ts` et `last_webhook_sent_ts` restent `null` tant qu'aucun code ne renseigne les setters ou le global correspondant : le champ existe, mais il n'est pas encore alimenté.

Ces valeurs viennent de `RuntimeMetricsService` et des globals de `app_render` (threads legacy, dernier envoi). Elles sont assemblées par `_get_runtime_metrics_payload`.

---

## Endpoints de diagnostic

| Endpoint | Authentification | Réponse |
| --- | --- | --- |
| `GET /health` | Aucune | `{"status": "ok"}` |
| `GET /api/ping` | Aucune | `{"status": "pong", "timestamp_utc": ...}` |
| `GET /api/diag/runtime` | Session Flask-Login | Métriques de process et d'uptime |
| `GET /api/check_trigger` | Session Flask-Login | Présence d'un fichier de déclenchement local |
| `GET /api/get_local_status` | Session Flask-Login | Snapshot minimal pour l'UI distante |
| `GET /api/webhook_logs?days=7&limit=50` | Session Flask-Login | Journal webhook filtré |

`/api/ping` sert aux sondes qui ont besoin d'un timestamp ; `/health` sert à Render, qui ne lit que le code HTTP.

---

## Journal webhook

### Stockage

`WebhookLoggerService.append_log(entry)` écrit dans deux backend :

1. Redis, dans la liste `webhook_logs`, si le client est disponible ;
2. fichier `debug/webhook_logs.json`, sinon.

La liste est bornée à 500 entrées (`DEFAULT_MAX_ENTRIES`). Au-delà, les plus anciennes sont supprimées.

```python
WebhookLoggerService.get_instance().append_log({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "status": "success",
    "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
    "email_id": email_id,
})
```

### Ce qu'on y trouve

| Champ | Usage |
| --- | --- |
| `timestamp` | Reconstruction de la chronologie |
| `status` | `success` ou `error` |
| `webhook_url` | Cible, tronquée à 50 caractères |
| `email_id` | Corrélation avec les logs applicatifs |
| `error_message` | Cause d'échec côté réception |

### Lecture

`GET /api/webhook_logs?days=7&limit=50` borne `days` entre 1 et 30. Le dashboard utilise le même endpoint via `LogService.loadAndRenderLogs`.

---

## Logs applicatifs

Les logs passent par `app.logger`, avec un préfixe par domaine. Les préfixes réellement utilisés incluent :

| Préfixe | Domaine |
| --- | --- |
| `CFG`, `CFG WEBHOOK`, `CFG REDIS` | Configuration et démarrage |
| `SVC` | Initialisation des services |
| `INGRESS` | Gmail Push |
| `DEDUP`, `DEDUP_EMAIL`, `DEDUP_GROUP` | Déduplication |
| `PATTERN_MATCH`, `RECADRAGE`, `DESABO` | Détection |
| `ROUTING_RULES` | Routage dynamique |
| `CUSTOM_WEBHOOK`, `WEBHOOK` | Envoi sortant |
| `R2_TRANSFER` | Offload Cloudflare |
| `MAGIC_LINK` | Authentification |
| `POLLER`, `IMAP` | Poller legacy |
| `PROCESS` | Cycle de vie du process |

Les emails, identifiants et sujets sensibles passent par `mask_sensitive_data` avant journalisation. Les URL de webhook sont tronquées, jamais écrites en entier.

### Chercher une panne

```bash
# Dernier envoi réussi
grep "CUSTOM_WEBHOOK:.*success" render.log | tail -5

# Erreurs d'ingestion
grep -E "INGRESS|DEDUP" render.log | grep -i error | tail -20

# Redémarrages
grep "PROCESS: SIGTERM" render.log
```

Les logs Render sont éphémères. Pour un historique, il faut un collecteur externe ou exporter `debug/webhook_logs.json`.

---

## Dashboard : ce que voit l'utilisateur

`static/services/status_banner.js` calcule un statut à partir des logs :

| Indicateur | Fenêtre | Règle |
| --- | --- | --- |
| Dernière exécution | Tous les logs | Date du log le plus récent, formatée en relatif |
| Incidents récents | 24 h | Nombre de logs en erreur |
| Erreurs critiques | 1 h | Nombre de logs en erreur |
| Webhooks actifs | 1 h | Nombre total d'envois |

Statut global :

- `error` si au moins une erreur critique sur l'heure ;
- `warning` si des incidents existent sur 24 h ;
- `success` sinon.

L'icône porte `role="img"` et un `aria-label` explicite (`Statut : opérationnel`, `dégradé`, `critique`). Le bandeau réutilise les caches de `LogService` et `WebhookService` quand ils ont moins de 60 secondes, sinon il interroge l'API.

`LogService` rafraîchit la timeline toutes les 30 secondes. Le polling est coupé quand `document.hidden` passe à `true` et relancé au retour. Il n'y a pas de websocket ni de server-sent events : le dashboard est un client passif.

---

## Limites mémoire et timeouts

| Protection | Valeur | Emplacement |
| --- | --- | --- |
| Troncature HTML | 1 Mo | `email_processing/orchestrator.py` (`MAX_HTML_BYTES`) |
| Timeout IMAP | 30 s | `email_processing/imap_client.py` |
| Timeout R2 standard | 30 s | `R2TransferService.request_remote_fetch` |
| Timeout R2 Dropbox `/scl/fo/` | 120 s | `IngressService._process_single_delivery_link` |
| Timeout R2 Gmail Push standard | 15 s | `IngressService._process_single_delivery_link` |
| Verrou in-flight par email | 15 min | `EMAIL_ID_INFLIGHT_LOCK_TTL_SECONDS` |
| Verrou poller IMAP legacy | 5 min | `render_signal:poller_lock` |

Ces valeurs sont des garde-fous, pas des objectifs de performance. Un timeout R2 déclenche le fallback vers l'URL source ; un timeout IMAP laisse le cycle suivant reprendre.

---

## Alertes recommandées

Il n'existe pas de gestionnaire d'alertes interne. Les alertes se configurent à l'extérieur :

1. **Sonde HTTP** sur `/health`, toutes les 5 minutes. Deux échecs consécutifs déclenchent une alerte.
2. **Absence de trafic** : alerter si aucun log `INGRESS: gmail payload received` ou `CUSTOM_WEBHOOK` n'apparaît pendant 15 minutes en heures ouvrées.
3. **Erreurs répétées** : alerter si plus de 5 logs `status="error"` sur 15 minutes.
4. **Tokens magic link** : surveiller les pics de génération permanente et les signatures invalides.

Le dashboard ne remplace pas une sonde externe : si le serveur est down, il ne s'affiche pas non plus.

---

## La Golden Rule : mesurer le pipeline, pas seulement le processus

Un process qui répond `ok` peut avoir arrêté de traiter des emails depuis une heure. La santé se lit sur trois plans : le process est vivant, le dernier traitement est récent, et l'interface montre le même état que le serveur. `/health` répond à la première question, `/api/diag/runtime` et les logs répondent aux deux autres.
