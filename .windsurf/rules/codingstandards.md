---
trigger: always_on
description: 
globs: 
---

# Coding Standards – render_signal_server (v2026-01-19)

## Principes directeurs

Lisibilité > concision. Commenter le pourquoi, pas le comment. Nommage explicite. Sécurité par défaut. DRY. Tests pertinents. Configuration via ENV. Documentation à jour. Performance & résilience par design. Accessibilité inclusive.

---

## Portée et périmètre

**Backend Python**: Flask, services, email_processing, background, config, auth, dedup, app_logging, preferences.  
**Frontend ES6**: static/ (services/, components/, utils/, dashboard.js modulaire).  
**Services**: ConfigService, RuntimeFlagsService, WebhookConfigService, AuthService, PollingConfigService, DeduplicationService, R2TransferService, MagicLinkService, AppConfigStore.  
**Infrastructure**: Redis distribué, R2 offload, Docker GHCR, tests résilience.

---

## Langages et formatage

**Python**: PEP 8, Black (88 chars), isort, flake8/ruff.  
**JavaScript**: ES2022+, modules ES6, Prettier, ESLint (airbnb-base).  
**PHP**: PSR-12.  
**Fichiers**: UTF-8, LF, pas d'espaces fin de ligne.

---

## Architecture Frontend (2026-01-18)

### Structure modulaire
```
static/
├── services/
│   ├── ApiService.js (client API, 401/403)
│   ├── WebhookService.js (config+logs)
│   └── LogService.js (timer+visibility API)
├── components/
│   └── TabManager.js (onglets+ARIA)
├── utils/
│   └── MessageHelper.js (UI helpers)
└── dashboard.js (~600 lignes, orchestrateur)
```

### Standards ES6
- Imports/exports explicites : `import { ApiService } from './services/ApiService.js';`
- Classes et méthodes statiques pour les services
- JSDoc pour API publique
- Un fichier = une responsabilité

### Performance
- Lazy loading des onglets (TabManager)
- Timer intelligent avec visibility API (LogService)
- Bundle size réduit (1488→600 lignes)
- Cleanup automatique timers/écouteurs

### Sécurité
- **Protection XSS** : `createElement()` > `innerHTML`
- **Conditional logging** : uniquement localhost/127.0.0.1
- **Validation client** : formats, placeholders, inputs
- **Gestion 401/403** : ApiService avec redirection /login

### Accessibilité
- Rôles ARIA : tablist/tab/tabpanel
- Navigation clavier : Tab/Shift+Tab/Espace/Entrée
- WCAG AA : contrastes, labels, screen readers
- Responsive mobile-first (breakpoints 768px/480px)

### UX Avancé (2026-01-19)
- **Bandeau Statut Global** : Vue d'ensemble avec métriques santé système
- **Timeline Logs** : Timeline verticale avec sparkline Canvas 24h et animations
- **Panneaux Pliables** : 3 panneaux (URLs & SSL, Absence Globale, Fenêtre Horaire)
- **Auto-sauvegarde** : Sauvegarde auto préférences avec debounce 2-3s
- **Micro-interactions** : Ripple effect CSS, toast notifications, transitions fluides

---

## Architecture Backend

### Services (Singletons quand pertinent)
- **ConfigService** : config centralisée, secrets, Render
- **RuntimeFlagsService** : flags JSON, cache TTL 60s
- **WebhookConfigService** : config webhooks, validation HTTPS, Absence Globale
- **AuthService** : Flask-Login, décorateurs auth
- **PollingConfigService** : config IMAP, timezone
- **DeduplicationService** : Redis + fallback mémoire
- **R2TransferService** : offload Cloudflare R2, fallback garanti
- **MagicLinkService** : magic links HMAC, TTL configurable
- **AppConfigStore** : Redis-first store avec fallback PHP/fichiers, modes configurables

### Modules métier
- **email_processing/orchestrator.py** : cycle polling, règles métier, anti-OOM
- **background/lock.py** : verrou Redis distribué + fallback fcntl
- **routes/** : blueprints Flask (api_*.py, dashboard.py, health.py)

---

## Sécurité

### Backend
- Validation entrées côté serveur (Flask, PHP)
- Flask-Login pour UI, décorateurs `@login_required`, `api_key_required`
- Secrets via ENV uniquement (jamais commités)
- `FLASK_SECRET_KEY` robuste en production
- Webhooks : SSL vérifié en production, logs WARNING si désactivé

### Frontend
- Construction DOM sécurisée (pas d'innerHTML non contrôlé)
- Conditional logging : `console.log` uniquement localhost
- Validation inputs avant envoi API
- ApiService : gestion centralisée 401/403

### Infrastructure
- Redis : `REDIS_URL` avec mot de passe + TLS si possible
- R2 : `R2_FETCH_TOKEN` obligatoire pour Worker
- Logs : anonymisation PII via `mask_sensitive_data()`

---

## Performance & Résilience

### Backend
- **Anti-OOM** : limite HTML parsing à 1MB (`MAX_HTML_BYTES`)
- **Timeouts** : IMAP 30s, R2 adaptatif (120s Dropbox, 15s autres)
- **Fallbacks** : conservation URLs sources si R2 échoue, flux continu
- **Verrou distribué** : Redis `render_signal:poller_lock` TTL 5min
- **Caches** : RuntimeFlagsService (TTL 60s), WebhookConfigService

### Frontend
- Lazy loading onglets, visibility API polling
- Responsive design mobile-first
- Gestion mémoire : cleanup timers/écouteurs
- Accessibilité WCAG AA complète

---

## Gestion erreurs et logs

### Erreurs
- Exceptions explicites dans services
- Attraper aux frontières (routes, background)
- Fallbacks gracieux : try/except larges avec WARNING mais flux continu

### Logs
- Centraliser webhook logs dans `app_logging/webhook_logger.py`
- Structurés et contextualisés (ID email, détecteur, décision)
- Pas de secrets/emails complets
- Niveaux : `R2_TRANSFER:*`, `HTML content truncated`, `Using file-based lock`

---

## Tests

### Structure
- **Unitaires** : services, utils, helpers (majorité)
- **Intégration** : routes API, services ensemble
- **E2E** : flux critiques (polling, webhooks, absence globale)
- **Résilience** : Redis lock, R2 fallback, anti-OOM, watchdog IMAP

### Environnement & Commandes
- **Environnement partagé** : `/mnt/venv_ext4/venv_render_signal_server`
- **Activation** : `source /mnt/venv_ext4/venv_render_signal_server/bin/activate`
- **Commandes résilience** :
```bash
# Tests résilience avec couverture
pytest -m "redis or r2 or resilience" --cov=.

# Tests complets
pytest --cov=.
```

### Marqueurs pytest
- `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`
- `@pytest.mark.redis`, `@pytest.mark.imap` pour services externes
- `@pytest.mark.slow` pour tests longs

### Services à tester
- Tous les services (Config, RuntimeFlags, Webhook, Auth, Polling, Dedup, R2, MagicLink)
- Helpers reset_instance pour Singletons
- Approche API-first quand pertinent

### Résilience (Lot 2/3)
- **Redis lock** : `test_lock_redis.py` format Given/When/Then
- **R2 resilience** : `test_r2_resilience.py` scénarios exception/None/timeout
- **Anti-OOM** : validation troncature HTML >1MB
- **Watchdog IMAP** : timeout 30s anti-zombie

### CI
- pytest avec couverture obligatoire
- Seuil dans `docs/quality/testing.md` et `.coveragerc`

---

## Configuration

### Variables ENV obligatoires
- `FLASK_SECRET_KEY`, `DASHBOARD_USER`, `DASHBOARD_PASSWORD`
- `EMAIL_*` (IMAP), `WEBHOOK_URL`, `WEBHOOK_SSL_VERIFY`
- `ENABLE_BACKGROUND_TASKS`
- `REDIS_URL` (multi-conteneurs)
- `R2_FETCH_*` (offload), `MAGIC_LINK_*` (auth)

### Services de configuration
- Utiliser services dédiés, pas accès direct fichiers JSON
- ConfigService pour plupart, RuntimeFlagsService pour flags debug
- WebhookConfigService pour config webhooks, PollingConfigService pour IMAP

### Redis Config Store
- **Service** : `config/app_config_store.py` avec modes `redis_first`/`php_first`
- **Configurations** : magic_link_tokens, polling_config, processing_prefs, webhook_config
- **Migration** : `migrate_configs_to_redis.py --verify`
- **Vérification** : `/api/verify_config_store` ou `python -m scripts.check_config_store`

---

## Git et commits

### Branches
- `feature/<slug>` ou `fix/<slug>`
- Courte durée, PRs ciblées

### Messages
- Conventional Commits : `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Présent, concis, explicite

### PRs
- Petites, ciblées, description claire
- Frontend : captures écran si applicable
- Résilience : scénarios défaillance testés

---

## Développement Frontend

### Patterns
- **Modularité** : 1 fichier = 1 responsabilité
- **Imports** : nommés et explicites
- **Exports** : uniquement API publique
- **Sécurité** : jamais innerHTML non contrôlé
- **Performance** : lazy loading + visibility API
- **Accessibilité** : ARIA + navigation clavier

### Exemple service
```javascript
export class ApiService {
  static async get(url) {
    const res = await fetch(url);
    return this.handleResponse(res);
  }
  
  static handleResponse(res) {
    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Session expirée');
    }
    return res;
  }
}
```

---

## Développement Résilience

### Patterns
- **Always fallback** : toujours prévoir fallback gracieux
- **Log mais continue** : WARNING mais ne jamais interrompre flux critique
- **Timeouts explicites** : toujours configurer I/O timeouts
- **Conservation état** : préserver état initial pour fallback

### Exemple fallback R2
```python
fallback_raw_url = source_url
try:
    r2_result = r2_service.request_remote_fetch(...)
except Exception:
    r2_result = None
    logger.warning("R2_TRANSFER: fallback to source URL")
# Flux continue avec fallback_raw_url
```

---

## Métriques actuelles

- **Tests** : 389 passed, 13 skipped, 0 failed
- **Couverture** : ~70%
- **Frontend** : 5 modules ES6, 1488→600 lignes, UX avancé complet
- **Résilience** : Redis lock, R2 fallback, anti-OOM, watchdog IMAP
- **Performance** : lazy loading, visibility API, timeouts robustes
- **Documentation** : Synchronisée avec code via workflow docs-updater

---

*Ce document reflète l'état actuel du projet avec frontend modulaire, résilience infrastructure, performance optimisée et accessibilité inclusive. Référence pour tout nouveau développement.*