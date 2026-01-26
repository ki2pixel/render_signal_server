---
name: background-poller-resilience-lab
description: Harden or modify the IMAP polling loop (locks, watchdog, HTML caps) with the approved patterns, fallbacks, and resilience tests.
---

# Background Poller Resilience Lab

À utiliser pour toute modification des fichiers `background/polling_thread.py`, `background/lock.py`, ou de la logique poller dans `email_processing/orchestrator.py`.

## Pré-requis rapides
- ENV chargées (`ENABLE_BACKGROUND_TASKS`, `BG_POLLER_LOCK_FILE`, accès Redis fonctionnel).
- Accès au virtualenv `/mnt/venv_ext4/venv_render_signal_server`.
- Logs consultables (`app_logging/*`).

## Workflow canonique
1. **Cartographier l'impact**
   - Identifier si la modification touche le lock Redis, la boucle IMAP ou la troncature HTML dans `email_processing/orchestrator.py`.
   - Noter les modules à tester (background + orchestrateur) dans la Memory Bank avant d'éditer.
2. **Locking**
   - Redis lock clé `render_signal:poller_lock`, TTL 300s (cf. `background/lock.py`).
   - Fallback `fcntl` via `/tmp/render_signal_server_email_poller.lock` ou `BG_POLLER_LOCK_FILE`.
   - Toujours logguer les échecs d'acquisition (WARNING) et éviter tout double thread.
3. **Watchdog & Timing**
   - Timeout IMAP ≥30s, rafraîchissement des configs à chaque cycle avec `PollingConfigService`.
   - Respecter strictement `ENABLE_BACKGROUND_TASKS` et injecter toute dépendance via `background_email_poller_loop`.
4. **HTML/PII Guards**
   - Conserver `MAX_HTML_BYTES = 1_000_000` (warning unique par mail) dans l'orchestrateur.
   - Scrubber via `mask_sensitive_data` avant tout log.
5. **Observabilité**
   - Utiliser exclusivement les helpers `app_logging` (pas de `print`).
   - Ajouter métriques/timestamps lorsqu'une nouvelle étape est introduite.
6. **Tests & validation**
   - Lancer le helper `./.windsurf/skills/background-poller-resilience-lab/run_poller_resilience_suite.sh` pour exécuter `tests/test_background_lock.py`, `tests/test_background_lock_extra.py`, `tests/test_lock_redis.py`, `tests/test_polling_dynamic_reload.py`, puis la sélection `-m "redis or resilience"`.
   - Compléter si besoin avec `pytest -m "redis or r2 or resilience"` et les tests ciblés supplémentaires.
7. **Traçabilité**
   - Documenter toute évolution majeure dans `docs/features/email_polling.md` (section Poller IMAP) et mettre à jour la Memory Bank (progress + decision).

## Ressources
- `run_poller_resilience_suite.sh` : active le venv, exécute `tests/test_background_lock.py`, `tests/test_background_lock_extra.py`, `tests/test_lock_redis.py`, `tests/test_polling_dynamic_reload.py`, puis la sélection `-m "redis or resilience"`.

## Conseils
- Pas de cache global mutable : récupérer la config via les getters à chaque cycle.
- Injecter les nouvelles dépendances IMAP via les paramètres de boucle pour rester testable.
- En cas de changement de schéma/config, synchroniser immédiatement la documentation et la Memory Bank.
