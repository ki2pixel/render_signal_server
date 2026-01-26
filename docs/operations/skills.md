# Windsurf Skills - Helpers et Workflows

Ce document référence les skills Windsurf du projet avec leurs helpers et workflows associés.

## 📋 Skills disponibles

### Architecture & Résilience
- **background-poller-resilience-lab** - Durcissement du poller IMAP (locks, watchdog, HTML caps)
  - Helper : `run_poller_resilience_suite.sh` (tests résilience + lock Redis)
  - Cible : `background/polling_thread.py`, `background/lock.py`, `email_processing/orchestrator.py`

- **routing-rules-orchestrator** - Gestion du moteur de routage dynamique
  - Helper : `test_routing_rules.sh` (service + API + orchestrator)
  - Cible : `services/routing_rules_service.py`, `routes/api_routing_rules.py`, `email_processing/orchestrator.py`

### Configuration & Stockage
- **check-config** - Diagnostic du Config Store (Redis/Fichier)
  - Helper : `inspect_store.sh` (inspection des 3 clés critiques)
  - Cible : `scripts/check_config_store.py`, API `/api/verify_config_store`

- **redis-config-guardian** - Audit et réconciliation des configs Redis
  - Helper : `audit_redis_configs.sh` (inspection + diff avec fallbacks)
  - Cible : `app_config_store`, `debug/*.json`

### Intégrations & Transferts
- **r2-transfer-service-playbook** - Pipeline R2 (Python + Workers + PHP)
  - Helper : `test_r2_worker.sh` (tests R2 + diagnostics PHP)
  - Cible : `services/r2_transfer_service.py`, `deployment/cloudflare-worker/*`, `deployment/src/JsonLogger.php`

- **magic-link-auth-companion** - Gestion Magic Link (backend + stockage + UI)
  - Helper : `revoke_magic_links.py` (révocation CLI)
  - Cible : `services/magic_link_service.py`, API `/api/auth/magic-link`, UI dashboard

### Tests & Qualité
- **testing-matrix-navigator** - Sélection et exécution des suites de tests
  - Helper : `run_test_matrix.sh` (unit, redis, r2, resilience, polling, full)
  - Cible : `pytest` avec marqueurs spécifiques

- **run-tests** - Exécution canonique des tests
  - Helper : `run_tests.sh` (déjà existant, utilise le virtualenv partagé)
  - Cible : Suite complète avec couverture

### Frontend & UX
- **webhook-dashboard-ux-maintainer** - Maintenance du dashboard moderne
  - Helper : `test_dashboard_ux.sh` (checklist manuelle + tests backend)
  - Cible : `dashboard.html`, modules ES6, accessibilité WCAG

### Documentation
- **docs-sync-automaton** - Synchronisation documentation complète
  - Helper : `run_docs_audit.sh` (tree + cloc + radon)
  - Cible : `docs/`, Memory Bank, mise à jour croisée

### Scaffolding (templates existants)
- **scaffold-js-module** - Création module JavaScript ES6
  - Template : `module_template.js`
  - Cible : `static/services/`, `static/components/`

- **scaffold-service** - Génération service Python singleton
  - Template : `service_template.py`
  - Cible : `services/`

## 🚀 Utilisation

### Exécuter un helper
```bash
# Depuis la racine du repo
./.windsurf/skills/<skill>/<helper>.sh
```

### Exemples courants
```bash
# Vérifier les configs Redis
./.windsurf/skills/check-config/inspect_store.sh

# Lancer les tests de résilience
./.windsurf/skills/background-poller-resilience-lab/run_poller_resilience_suite.sh

# Auditer les configs Redis avec diff
./.windsurf/skills/redis-config-guardian/audit_redis_configs.sh

# Lancer les tests unitaires uniquement
./.windsurf/skills/testing-matrix-navigator/run_test_matrix.sh unit

# Checklist UX du dashboard
./.windsurf/skills/webhook-dashboard-ux-maintainer/test_dashboard_ux.sh
```

## 📝 Conventions

- Tous les scripts sont exécutables (`chmod +x`)
- Activation automatique du virtualenv `/mnt/venv_ext4/venv_render_signal_server` avec fallback
- Exécution depuis la racine du repo (chemins relatifs)
- Respect des standards du projet (`set -euo pipefail`, logs structurés)

## 🔗 Références

- `.windsurf/rules/codingstandards.md` - Standards de codage et architecture
- `docs/quality/testing.md` - Stratégie de tests et marqueurs
- `memory-bank/` - État actuel et décisions du projet
