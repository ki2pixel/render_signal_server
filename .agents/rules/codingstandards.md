---
trigger: model_decision
description: Core engineering standards, architecture invariants, security rules, and conventions for render_signal_server
globs: 
---

# render_signal_server – Antigravity Rules (v2026-01)

These rules are the single source of truth for backend (Flask), frontend (modular ES6), and legacy tooling. Apply them to every change unless an explicit exception is documented.

## Architecture & State Invariants
- **Backend Architecture:** Python 3.11, Flask application factory (`create_app()` in `app_render.py`). Services are **singletons** (`ConfigService`, `IngressService`, `AuthService`, `DeduplicationService`, `R2TransferService`, `MagicLinkService`, `RuntimeFlagsService`). Read/write via service getters, never mutate module globals.
- **Config & Redis Source of Truth:** Redis is the source of truth for `routing_rules`, `webhook_config`, `processing_prefs`, and `magic_link_tokens`. Read/write via `ConfigService` every time; never edit `debug/*.json` directly at runtime.
- **Secrets Management:** Secrets must come from ENV (`_get_required_env()` in `config/settings.py` enforces mandatory variables: `FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`).

## Backend Code Style & Security
- **Functions & Types:** Functions < 40 lines. Mandatory Python type hints (e.g., `Response | tuple[Response, int]`). Use dataclasses/`TypedDict`. Clean code: comments state *why*, never *how*.
- **Boundary Validation & Open Redirects:** Input validation lives at route boundaries. Raise `ValueError`/`BadRequest` with explicit messages; let Flask serialize. Strictly validate all redirect targets to prevent Open Redirects.
- **PII Scrubbing & Logging:** All logging routes through `app_logging/`. Systematically scrub PII (emails, tokens, names) using `mask_sensitive_data` before logging. Never log raw email bodies or expose `PROCESS_API_TOKEN`.

## Gmail Push Ingress & R2 Offload
- **Ingress Flow:** `POST /api/ingress/gmail` requires Bearer token auth (`AuthService.verify_api_key_from_request()`).
- **Processing:** Validate sender allowlist via `GMAIL_SENDER_ALLOWLIST`. Enforce idempotence via `DeduplicationService` (Redis TTL hash). Apply pattern matching (Media Solution/DESABO) and time windows before webhook trigger.
- **R2 Guard:** Validate domain allowlist (`is_allowed_domain()`) and inject `X-R2-FETCH-TOKEN`. Fallback gracefully to original URL if transfer fails.

## Frontend Standards (ES6 & UI)
- **Modularity:** ES6 modules with named exports only. `dashboard.js` orchestrates services and components.
- **Modern JS & DOM:** Use `Object.hasOwn(obj, key)` exclusively (ban `hasOwnProperty`). Ban global absolute IDs and `innerHTML`; use `DOMHelper` with `[data-target="..."]`.
- **UX & Accessibility:** WCAG AA compliance (keyboard focus, ARIA roles). Auto-save uses debounced `ApiService` calls (2-3s) with optimistic UI + rollback on failure; intercept `beforeunload`. Maintain Status Banner, Timeline Canvas, and collapsible Webhook panels. Use lazy rendering for large datasets.

## Tooling, Testing & Skills Policy
- **Skill Priority:** Always invoke workspace-scoped skills (`.agents/skills/`) before global catalog (`~/.gemini/antigravity/skills/`).
- **Tests:** Environment: `/mnt/venv_ext4/venv_render_signal_server`. Tests require `# Given / # When / # Then` blocks, isolated mocks (`mock_redis` fixture), failure cases $\ge$ normal cases, target 100% branch coverage. Run via `pytest -m "redis or r2 or resilience"`.
- **Shell Scripts:** Use `[[ ]]` strictly for all conditions in bash scripts (ban legacy `[ ]` or `test`).
- **Documentation:** Apply `.agents/skills/documentation/SKILL.md` (TL;DR first, problem-first opening, trade-offs).

## Anti-Patterns (Strictly Prohibited)
- Hardcode secrets, tokens, or fallback credentials in code.
- Reintroduce `innerHTML` or inline event handlers in frontend.
- Bypass Redis Config Store (e.g. editing `debug/*.json` at runtime).
- Disable auth on `/api/ingress/gmail` or log unscrubbed email bodies.
- Trust raw user input for redirects (Open Redirect vulnerability).
- Restart IMAP polling or use legacy IMAP variables outside isolated test environments.
