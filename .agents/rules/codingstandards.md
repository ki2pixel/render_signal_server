---
trigger: model_decision
description: Core engineering standards, architecture invariants, security rules, and conventions for render_signal_server
globs: 
---

# render_signal_server – Antigravity Rules (v2026-01)

These rules are the single source of truth for backend (Flask), frontend (modular ES6), and legacy tooling. Apply them to every change unless an explicit exception is documented.

## Architecture & State Invariants
- **Backend Architecture:** Python 3.11, Flask application factory (`create_app()` in `app_render.py`). Singleton services: `IngressService`, `DeduplicationService`, `WebhookConfigService`, `RoutingRulesService`, `R2TransferService`, `MagicLinkService`, `RuntimeFlagsService`, `RateLimitService`, `RuntimeMetricsService`, `WebhookLoggerService`. `ConfigService` and `AuthService` are non-singleton services instantiated by the composition root. Read/write via the owning service. The globals in `app_render.py` (`_config_service`, `_ingress_service`, etc.) are the historical composition exception: do not add new ones in business code.
- **Config & Redis Source of Truth:** The config store (Redis-first, JSON fallback via `config/app_config_store.py`) is the source of truth for `routing_rules`, `webhook_config`, `processing_prefs`, and `magic_link_tokens`. Write through the owning service (`RoutingRulesService`, `WebhookConfigService`, `preferences/processing_prefs.py` + `routes/api_processing.py`, `MagicLinkService`), never through `ConfigService` (which only reads environment variables) or by editing `debug/*.json` at runtime.
- **Secrets Management:** Secrets must come from ENV (`_get_required_env()` in `config/settings.py` enforces mandatory variables: `FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`).

## Backend Code Style & Security
- **Functions & Types:** Functions < 40 lines. Mandatory Python type hints (e.g., `Response | tuple[Response, int]`). Use dataclasses/`TypedDict`. Clean code: comments state *why*, never *how*.
- **Boundary Validation & Open Redirects:** Input validation lives at route boundaries. Return explicit 4xx JSON errors (or raise `ValueError` in services and translate it at the boundary); never let a validation failure fall through to the generic 500 handler. Strictly validate all redirect targets to prevent Open Redirects.
- **PII Scrubbing & Logging:** Webhook logs go through `app_logging/webhook_logger.py` (via `WebhookLoggerService`); application logs go through `app.logger`. In both cases, scrub PII (emails, tokens, names) with `mask_sensitive_data` before writing. Never log raw email bodies or expose `PROCESS_API_TOKEN`.

## Gmail Push Ingress & R2 Offload
- **Ingress Flow:** `POST /api/ingress/gmail` requires Bearer token auth (`AuthService.verify_api_key_from_request()`).
- **Processing:** Validate sender allowlist via `GMAIL_SENDER_ALLOWLIST`. Enforce idempotence via `DeduplicationService`: a Redis set of processed IDs, scoped TTL keys, and a per-email in-flight `SET NX EX` lock. Apply pattern matching (Media Solution/DESABO) and time windows before webhook trigger.
- **R2 Guard:** Validate the host against `ALLOWED_REMOTE_FETCH_DOMAINS` via `_validate_remote_fetch_domain()` and inject `X-R2-FETCH-TOKEN`. Fallback gracefully to original URL if transfer fails.

## Frontend Standards (ES6 & UI)
- **Modularity:** ES6 modules with named exports only. `dashboard.js` orchestrates services and components.
- **Modern JS & DOM:** Use `Object.hasOwn(obj, key)` exclusively (ban `hasOwnProperty`). Prefer `DOMHelper` with `[data-target="..."]` for lookups; remaining `getElementById` calls (toasts, dialog, remote UI) are legacy to migrate. No `innerHTML` for dynamic or user data; only the static `ConfirmDialog` template is exempt.
- **UX & Accessibility:** WCAG AA compliance (keyboard focus, ARIA roles). Auto-save uses debounced `ApiService` calls (2-3s) with optimistic UI + rollback on failure; intercept `beforeunload`. Maintain Status Banner, Timeline Canvas, and collapsible Webhook panels. Use lazy rendering for large datasets (JsonViewer).

## Tooling, Testing & Skills Policy
- **Skill Priority:** Always invoke workspace-scoped skills (`.agents/skills/`) before global catalog (`~/.gemini/antigravity/skills/`).
- **Tests:** Environment: `/mnt/venv_ext4/venv_render_signal_server`. New or modified tests require `# Given / # When / # Then` blocks, isolated mocks (`mock_redis` fixture), failure cases $\ge$ normal cases, target 100% branch coverage. Available markers: `unit`, `integration`, `e2e`, `slow`, `redis`, `imap` (`pytest -m "redis or imap"`). R2 and resilience suites are selected by file: `pytest tests/test_r2_transfer_service.py tests/test_r2_resilience.py -v`.
- **Shell Scripts:** Use `[[ ]]` strictly for all conditions in bash scripts (ban legacy `[ ]` or `test`).
- **Documentation:** Apply `.agents/skills/documentation/SKILL.md` (TL;DR first, problem-first opening, trade-offs).

## Anti-Patterns (Strictly Prohibited)
- Hardcode secrets, tokens, or fallback credentials in code.
- Reintroduce `innerHTML` for dynamic data or inline event handlers in frontend.
- Bypass Redis Config Store (e.g. editing `debug/*.json` at runtime).
- Disable auth on `/api/ingress/gmail` or log unscrubbed email bodies.
- Trust raw user input for redirects (Open Redirect vulnerability).
- Restart IMAP polling or use legacy IMAP variables outside isolated test environments.
