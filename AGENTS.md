# Repository Guidelines

## Project Structure & Module Organization

Flask application using an **application factory** (`create_app()` in `app_render.py`) with a service-oriented architecture. Singleton services in `services/` are `IngressService`, `DeduplicationService`, `WebhookConfigService`, `RoutingRulesService`, `R2TransferService`, `MagicLinkService`, `RuntimeFlagsService`, `RateLimitService`, `RuntimeMetricsService`, and `WebhookLoggerService` (all expose `get_instance()`). `ConfigService` and `AuthService` are non-singleton services instantiated by the composition root. HTTP routes are Flask Blueprints in `routes/`. Email processing pipeline lives in `email_processing/` (orchestrator, pattern matching, link extraction, IMAP client). The config store (Redis-first, JSON fallback) is the source of truth for `routing_rules`, `webhook_config`, `processing_prefs`, and `magic_link_tokens`; read/write through the owning service (`RoutingRulesService`, `WebhookConfigService`, `preferences/processing_prefs.py` + `routes/api_processing.py` via `config/app_config_store.py`, `MagicLinkService`), never edit `debug/*.json` directly at runtime. Frontend is modular ES6 in `static/` bundled with Vite; `dashboard.js` orchestrates services (`ApiService`, `WebhookService`, `LogService`, `RoutingRulesService`) and components (`TabManager`, `ConfirmDialog`, `JsonViewer`), while `DOMHelper` and `MessageHelper` are utilities.

## Build, Test, and Development Commands

**Backend dev:**
```bash
source /mnt/venv_ext4/venv_render_signal_server/bin/activate  # or .venv/bin/activate
export FLASK_APP=app_render:app
flask run --host=0.0.0.0 --port=5000
```

**Frontend:** `npm run dev` (Vite dev), `npm run build` (production bundle to `static/dist/`), `npm run preview`.

**Tests:** `pytest` runs all tests. Single file: `pytest tests/test_services.py -v`. By marker: `pytest -m "unit"`, `pytest -m "integration"`, `pytest -m "redis or imap"`. R2 and resilience suites do not have a dedicated marker yet: select them by file (`pytest tests/test_r2_transfer_service.py tests/test_r2_resilience.py -v`). Coverage is auto-generated via `pytest-cov` with config in `.coveragerc`.

**Production:** Gunicorn (`app_render:app`) via the multistage `Dockerfile` (Node build → Python runtime). CI in `.github/workflows/render-image.yml` pushes to GHCR and triggers Render deploy.

## Coding Style & Naming Conventions

- **Python:** `black` (88 cols) + `isort` for formatting, `flake8` and `ruff` for linting, `mypy` for type checking. Type hints are mandatory. Functions < 40 lines. Use `TypedDict`/dataclasses for structured data.
- **Frontend:** ES6 modules with named exports only. Use `Object.hasOwn()` (never `hasOwnProperty`). No `innerHTML` for dynamic or user data: build nodes with `createElement`/`textContent`/`replaceChildren`; `DOMHelper` handles element lookup (`[data-target]` first, legacy ID fallback). A static, non-interpolated template in `ConfirmDialog` is the documented exception. WCAG AA compliance (ARIA roles, keyboard focus). Auto-save via debounced `ApiService` calls with optimistic UI + rollback.
- **Shell scripts:** Use `[[ ]]` for all conditions (no legacy `[ ]`).
- Comments explain *why*, never *how*. Delete dead code immediately.

## Testing Guidelines

pytest with custom markers: `unit`, `integration`, `e2e`, `slow`, `redis`, `imap`. Test discovery from `tests/` and `test_app_render.py`. New or modified tests must use **# Given / # When / # Then** comment blocks (the existing suite is being migrated progressively). Include failure cases ≥ normal cases. Use `fakeredis` for Redis-dependent tests (`mock_redis` fixture in `conftest.py`). Target 100% branch coverage. `pytest-timeout` enforces a 30s limit.

## Commit & Pull Request Guidelines

**Commits** follow Conventional Commits with English summaries, bullet-point bodies:
```
feat: Add sender allowlist validation for Gmail ingress

- Validate GMAIL_SENDER_ALLOWLIST before processing
- Reject unauthorized senders with 403
```
Prefixes: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `style`, `revert`. No period at end of summary. Branch naming: `feature/<slug>` or `fix/<slug>`.

**PRs** use the same prefix in the title. Body requires **Overview** and **Changes** sections; **Test Content** and **Related Issues** are recommended.

## MCP fast-filesystem — absolute paths required

- **All `fast_*` tools** (`fast_read_file`, `fast_search_files`, `fast_get_directory_tree`, `fast_list_directory`, `fast_read_multiple_files`, `fast_write_file`) require an **absolute path** under `/home/kidpixel/`.
- **Forbidden**: `"."`, `"./..."`, `"../..."`, or any relative path. The `fast-filesystem` daemon is shared across projects; a relative path is resolved against its own `cwd`, not this repository, and may silently read another project.
- **Targeted edits**: use `filesystem-agent.edit_file` (a separate server), not `fast-filesystem`, with an absolute path.
- **Sanity check**: if a `fast_*` result appears to come from another repository, stop, inspect the `path` field, and retry with an absolute path.
- **Expected errors**: `-32602 RELATIVE_PATH_UNSUPPORTED`, `-32602 RELATIVE_PATH_ESCAPES_WORKSPACE`, `-32000 PATH_OUTSIDE_ALLOWED_ROOT`.
