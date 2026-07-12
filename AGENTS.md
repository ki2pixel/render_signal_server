# Repository Guidelines

## Project Structure & Module Organization

Flask application using an **application factory** (`create_app()` in `app_render.py`) with a service-oriented architecture. Services in `services/` are singletons (`ConfigService`, `AuthService`, `IngressService`, `DeduplicationService`, `WebhookConfigService`, `R2TransferService`, `MagicLinkService`, `RuntimeFlagsService`). HTTP routes are Flask Blueprints in `routes/`. Email processing pipeline lives in `email_processing/` (orchestrator, pattern matching, link extraction, IMAP client). Redis is the source of truth for `routing_rules`, `webhook_config`, `processing_prefs`, and `magic_link_tokens` — always read/write via `ConfigService`, never edit `debug/*.json` directly at runtime. Frontend is modular ES6 in `static/` bundled with Vite; `dashboard.js` orchestrates services (`ApiService`, `WebhookService`, `LogService`) and components (`TabManager`, `DOMHelper`, `MessageHelper`).

## Build, Test, and Development Commands

**Backend dev:**
```bash
source /mnt/venv_ext4/venv_render_signal_server/bin/activate  # or .venv/bin/activate
export FLASK_APP=app_render:app
flask run --host=0.0.0.0 --port=5000
```

**Frontend:** `npm run dev` (Vite dev), `npm run build` (production bundle to `static/dist/`), `npm run preview`.

**Tests:** `pytest` runs all tests. Single file: `pytest tests/test_services.py -v`. By marker: `pytest -m "redis or r2 or resilience"`. Coverage is auto-generated via `pytest-cov` with config in `.coveragerc`.

**Production:** Gunicorn (`app_render:app`) via the multistage `Dockerfile` (Node build → Python runtime). CI in `.github/workflows/render-image.yml` pushes to GHCR and triggers Render deploy.

## Coding Style & Naming Conventions

- **Python:** `black` (88 cols) + `isort` for formatting, `flake8` and `ruff` for linting, `mypy` for type checking. Type hints are mandatory. Functions < 40 lines. Use `TypedDict`/dataclasses for structured data.
- **Frontend:** ES6 modules with named exports only. Use `Object.hasOwn()` (never `hasOwnProperty`). No `innerHTML` — use `DOMHelper`. WCAG AA compliance (ARIA roles, keyboard focus). Auto-save via debounced `ApiService` calls with optimistic UI + rollback.
- **Shell scripts:** Use `[[ ]]` for all conditions (no legacy `[ ]`).
- Comments explain *why*, never *how*. Delete dead code immediately.

## Testing Guidelines

pytest with custom markers: `unit`, `integration`, `e2e`, `slow`, `redis`, `imap`. Test discovery from `tests/` and `test_app_render.py`. Every test must use **# Given / # When / # Then** comment blocks. Include failure cases ≥ normal cases. Use `fakeredis` for Redis-dependent tests (`mock_redis` fixture in `conftest.py`). Target 100% branch coverage. `pytest-timeout` enforces a 30s limit.

## Commit & Pull Request Guidelines

**Commits** follow Conventional Commits with English summaries, bullet-point bodies:
```
feat: Add sender allowlist validation for Gmail ingress

- Validate GMAIL_SENDER_ALLOWLIST before processing
- Reject unauthorized senders with 403
```
Prefixes: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `style`, `revert`. No period at end of summary. Branch naming: `feature/<slug>` or `fix/<slug>`.

**PRs** use the same prefix in the title. Body requires **Overview** and **Changes** sections; **Test Content** and **Related Issues** are recommended.
