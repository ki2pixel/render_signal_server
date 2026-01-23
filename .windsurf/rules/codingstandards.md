---
trigger: always_on
description: 
globs: 
---

# Coding Standards – render_signal_server (v2026-01)

## 1. Principes Directeurs
*   **Priorités** : Lisibilité > Concision. Sécurité par défaut. DRY.
*   **Approche** : Commenter le *pourquoi*. Nommage explicite. Config via ENV.
*   **Qualité** : Performance & Résilience "by design". Accessibilité (WCAG AA).

---

## 2. Stack & Formatage
| Domaine | Techno | Standards | Outils |
| :--- | :--- | :--- | :--- |
| **Backend** | **Python** (Flask) | PEP 8, Black (88 chars) | `isort`, `flake8/ruff`, `pytest` |
| **Frontend** | **JS (ES6+)** | Modules natifs, Classes | `Prettier`, `ESLint`, JSDoc |
| **Legacy/Infra** | **PHP**, Redis, R2 | PSR-12, UTF-8 LF | Docker GHCR |

---

## 3. Architecture

### 3.1 Frontend (ES6 Modulaire)
**Structure** : `static/{services, components, utils, dashboard.js}`.
*   **Pattern** : 1 fichier = 1 responsabilité. Imports explicites.
*   **UX 2026** : Bandeau Statut, Timeline Canvas (Sparkline), Auto-save (debounce), Panneaux pliables.
*   **Performance** : Lazy loading (Onglets), Visibility API (Timer pause), Cleanup automatique.
*   **Sécurité** : Pas d'`innerHTML`, Validation client, Redirection 401/403 via `ApiService`.

### 3.2 Backend (Services & Singletons)
*   **Config & Flags** : `ConfigService` (env), `RuntimeFlagsService` (cache 60s), `AppConfigStore` (Redis-first).
*   **Métier** : `email_processing` (Orchestrator anti-OOM), `DeduplicationService` (Redis).
*   **Infra Externe** : `R2TransferService` (Offload + Fallback), `WebhookConfigService` (SSL check).
*   **Auth** : Flask-Login, Magic Links HMAC, Décorateurs `@login_required`.

---

## 4. Résilience & Performance (Critique)

### Backend
*   **Anti-OOM** : Parsing HTML tronqué à 1MB (`MAX_HTML_BYTES`).
*   **Verrou Distribué** : Redis `render_signal:poller_lock` (TTL 5min) + fallback fichier.
*   **Timeouts I/O** : IMAP (30s), R2 (Adaptatif 15-120s).
*   **Stratégie d'Erreur** : "Always Fallback". Catch large aux frontières → Log WARNING → Flux continu (ne jamais crasher le polling).

### Frontend
*   **Optimisation** : Bundle réduit, micro-interactions CSS (Ripple, Toast).
*   **Accessibilité** : Navigation clavier, ARIA (tablist/panel), Responsive mobile-first.

---

## 5. Sécurité & Logs

*   **Entrées** : Validation stricte (Back & Front). Pas de secrets en dur.
*   **Logs** : Centralisés (`app_logging/`), Anonymisés (`mask_sensitive_data`).
*   **Secrets** : Gestion via `ConfigService`. `FLASK_SECRET_KEY` robuste obligatoire.
*   **Protection** : Webhooks HTTPS vérifié. Logs conditionnels (Localhost seulement pour logs verbeux).

---

## 6. Environnement & Tests

**Chemin Venv** : `/mnt/venv_ext4/venv_render_signal_server`

### Commandes Clés
```bash
# Activation
source /mnt/venv_ext4/venv_render_signal_server/bin/activate

# Tests (Unitaires + Intégration + Couverture)
pytest --cov=.

# Tests Résilience (Redis, R2, OOM)
pytest -m "redis or r2 or resilience" --cov=.

# Vérification Store Redis
python -m scripts.check_config_store
```

### Stratégie de Test
*   **Couverture** : Services, Helpers, API Routes.
*   **Types** : Unitaires (majorité), E2E (flux critiques polling/webhooks).
*   **Résilience** : Simulation timeout/down pour Redis et R2.

---

## 7. Configuration & Déploiement

### Variables ENV Obligatoires
`FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`, `MAKECOM_API_KEY`.

### Git Workflow
*   **Branches** : `feature/<slug>` ou `fix/<slug>`.
*   **Commits** : Conventional (`feat:`, `fix:`, `refactor:`, `test:`).
*   **CI/CD** : Tests bloquants, Mise à jour doc auto.