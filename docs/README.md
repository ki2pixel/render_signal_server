# Documentation du projet

Ce dossier contient la documentation fonctionnelle et technique de l'application « render_signal_server ».

La documentation est organisée pour répondre rapidement aux besoins des développeurs, des opérateurs et des administrateurs système.

## Plan de lecture

- Architecture générale: `architecture.md`
- Installation locale et exécution: `installation.md`
- API HTTP (routes Flask): `api.md`
- Interface utilisateur (Dashboard Webhooks): `ui.md`
- Polling Email IMAP (logique et planification): `email_polling.md`
- Sécurité (bonnes pratiques et risques): `securite.md`
- Déploiement (Gunicorn/Reverse proxy): `deploiement.md`
- Dépannage (problèmes courants): `depannage.md`
- Webhooks (payloads entrants/sortants): `webhooks.md`
- Check-list de mise en production: `checklist_production.md`

## Aperçu rapide

### Nouveautés récentes (2025-10)

- __Refactor modulaire__: extraction de `auth/`, `config/`, `utils/`, `email_processing/` pour améliorer la maintenabilité.
- __Pattern matching e-mail__: `email_processing/pattern_matching.py` gère Média Solution + détection d'URLs via `URL_PROVIDERS_PATTERN`.
- __UI Dashboard__: navigation par onglets (Vue d'ensemble, Webhooks, Polling, Préférences, Outils), gestion des flags runtime et logs.
- __Liens de téléchargement__: suppression de la résolution automatique des liens directs; les payloads exposent uniquement `{ provider, raw_url }`.
- __Webhook DESABO__: `start_payload` = `WEBHOOKS_TIME_START_STR` si traité avant fenêtre, sinon `"maintenant"` (voir `email_polling.md`).

## Simulation des webhooks (sans réseau)

Un script de simulation permet d'inspecter les payloads générés sans dépendre d'une boîte mail ni d'appels HTTP réels.

- Script: `debug/simulate_webhooks.py`
- Exécution (désactive le poller en arrière-plan et mocke `requests.post`):

```bash
DISABLE_BACKGROUND_TASKS=true \
python debug/simulate_webhooks.py
```

Scénarios couverts:
- Cas Dropbox (payload custom expose aussi les champs legacy `dropbox_urls`/`dropbox_first_url`)
- Cas non-Dropbox (FromSmash, SwissTransfer)
- Cas Présence/Désabonnement (webhooks Make) avec inclusion de `webhooks_time_start`/`webhooks_time_end` si configurés

Le script affiche les JSON générés et les « appels HTTP » simulés, sans trafic réseau réel.
