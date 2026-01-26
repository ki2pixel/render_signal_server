---
trigger: always_on
description: 
globs: 
---

---
description: Core engineering standards and enforced conventions for render_signal_server
globs:
  - "**/*.py"
  - "static/**/*.js"
  - "dashboard.html"
  - "docs/**/*.md"
alwaysApply: true
---

# render_signal_server – Cursor Rules (v2026-01)

These rules are the single source of truth for backend (Flask), frontend (modular ES6), and legacy PHP/R2 tooling. Apply them to every change unless an explicit exception is documented here.

## Tech Stack
- **Backend:** Python 3.11, Flask app in `app_render.py`, services under `services/`, routes under `routes/`.
- **Background jobs:** IMAP poller (`background/polling_thread.py`) guarded by Redis lock + fcntl fallback.
- **Frontend:** `dashboard.html` + ES6 modules under `static/` (`services/`, `components/`, `utils/`, `dashboard.js`).
- **Storage:** Redis-first config store (`config/app_config_store.py`) with JSON fallback; Cloudflare R2 offload via `R2TransferService`.
- **Legacy helpers:** Minimal PHP footprint (Render deployment helpers + webhook receiver) adhering to PSR-12.
- **Tooling:** `black` (88 cols) + `isort` for Python, `Prettier` + `ESLint` for JS, `pytest` with custom markers, Docker + Render for deployment.

## Code Style & Structure
### Backend (Python)
- **Clean Code:** Delete commented-out dead code immediately (no confirmation needed). Comments must state the *why* (intent/business context), never re-describe implementation details.
- Services are **singletons with typed public methods** (see `PollingConfigService`, `WebhookConfigService`). Never mutate module-level globals at runtime; read via service getters each time.
- Keep functions short (<40 logical lines) and typed. Use `TypedDict` / dataclasses for structured payloads (e.g., `email_processing/orchestrator.py`).
- Input validation lives at route boundaries. Raise `ValueError`/`BadRequest` with explicit messages; let Flask error handlers serialize.
- Logging goes through `app_logging/` helpers. Always scrub PII with `mask_sensitive_data`.

### Frontend (JS/HTML)
- Use **modules + named exports** only. `dashboard.js` orchestrates modules; do not reintroduce global script tags.
- DOM updates must avoid `innerHTML`. Build elements, set `textContent`, and attach listeners declaratively.
- Respect WCAG AA: keyboard focus states, ARIA roles (`tablist`, `tabpanel`, `aria-expanded`).
- Auto-save flows use debounced `ApiService` calls (2–3s) with optimistic UI + rollback on failure.

### Legacy / Infra
- PHP utilities stay PSR-12, UTF-8 LF, no short tags. File writes must be atomic (temp file + rename) guarded by `flock` or Python-side `RLock`.
- Cloudflare Workers: keep headers explicit (`X-R2-FETCH-TOKEN`), enforce allowlists.

## Architecture Decisions to Enforce
### Configuration & Secrets
- Secrets (passwords, tokens) **must come from ENV**. `_get_required_env()` in `config/settings.py` already enforces the eight mandatory variables—do not bypass it.
- Redis is the **source of truth** for `polling_config`, `webhook_config`, `processing_prefs`, and `magic_link_tokens`. Any API or background logic must read via `AppConfigStore` every time.

### Background Poller
- Acquire Redis lock key `render_signal:poller_lock` (TTL 300s) before starting the IMAP loop; fallback to file lock only when Redis unavailable.
- Refresh dynamic config before each cycle by calling `PollingConfigService.get_*` methods. Never cache sender lists or dedup flags between cycles.
- HTML payload parsing is capped at `MAX_HTML_BYTES = 1_000_000`. Truncate and log a single WARNING when exceeded to avoid OOM.

### Frontend Experience
- Maintain the dashboard’s **Status Banner + Timeline Canvas + collapsible Webhook panels**. These are non-negotiable UX baselines.
- All destructive or long-running UI actions require visible feedback: ripple on buttons, toast via `MessageHelper`, and disabled states while waiting for the API.

## Patterns & Examples
### API Routes (Flask)
```python
@api_config_bp.route("/api/processing_prefs", methods=["POST"])
@login_required
def update_processing_prefs() -> Response:
    payload = ProcessingPrefsSchema().load(request.json or {})
    app_config_store.set_config_json("processing_prefs", payload)
    return jsonify({"status": "ok"})
```
- **Pattern:** Load schema, validate, persist via store, return JSON. Never write to `settings` globals.

### IMAP Poller Wrapper
```python
def check_new_emails_and_trigger_webhook():
    sender_whitelist = polling_config_service.get_sender_whitelist()
    dedup_enabled = polling_config_service.is_subject_group_dedup_enabled()
    return orchestrator.process_inbox(sender_whitelist, dedup_enabled)
```
- Call getters each run. Do not share mutable state between cycles; rely on service caches with TTL or no cache at all.

### Frontend Panel Save Flow
```javascript
import { ApiService } from "./services/ApiService.js";
import { updatePanelStatus } from "./dashboard.js";

async function saveWebhookPanel(panelId, collectData) {
  updatePanelStatus(panelId, "saving");
  const payload = collectData();
  await ApiService.post("/api/webhooks/config", payload);
  updatePanelStatus(panelId, "saved");
}
```
- Each collapsible panel owns a `collect*Data()` helper. Status chips mirror `saving`, `saved`, `error` states with timestamps.

### R2 Transfer Service Guard
```python
def upload_to_r2(source_url: str) -> R2UploadResult:
    if not is_allowed_domain(source_url):
        raise ValueError("Domain not in allowlist")
    return r2_client.transfer(source_url, headers={"X-R2-FETCH-TOKEN": token})
```
- Always run allowlist validation + token injection before offloading. Fallback gracefully to original URL when transfer fails.

## Testing & Tooling
- Use `/mnt/venv_ext4/venv_render_signal_server` for parity with CI. Commands:
  - `pytest --cov=.` (full suite)
  - `pytest -m "redis or r2 or resilience" --cov=.` (resilience focus)
  - `python -m scripts.check_config_store` (Redis JSON sanity)
- Add tests alongside functionality: routes in `tests/routes/`, services in `tests/services/`, poller logic in dedicated integration modules.
- Favor Given/When/Then naming and explicit fixtures (see `tests/test_polling_dynamic_reload.py`).

### Skill Invocation Policy (Workspace vs Global)
- **Priority order:** always invoke workspace-scoped skills under `.windsurf/skills/` before falling back to the global catalog in `/home/kidpixel/.codeium/skills`. The local skills encapsulate project-specific scripts, environments, and templates that enforce these coding standards.
  - `redis-config-guardian` remplace/complète le skill `check-config` pour tout audit de `processing_prefs`, `polling_config`, `webhook_config`, `magic_link_tokens`. Il orchestre le script CLI + l’API dashboard.
  - `routing-rules-orchestrator`, `webhook-dashboard-ux-maintainer`, `background-poller-resilience-lab`, `r2-transfer-service-playbook`, `magic-link-auth-companion`, `docs-sync-automaton`, `testing-matrix-navigator` doivent être utilisés dès qu’une tâche touche leur domaine respectif avant de recourir à des ressources globales.
  - `debugging-strategies` est obligatoire pour toute tâche de débogage (bugs, incidents de performances, comportements inattendus) avant d’envisager le moindre recours aux skills globaux ou à des ressources externes.
  - Le skill `run-tests` reste la porte d’entrée canonique pour `pytest`; `scaffold-js-module` et `scaffold-service` demeurent obligatoires pour les nouveaux modules/services.
- **Global skills usage:** reach for `/home/kidpixel/.codeium/skills/*` only when a needed capability (e.g., PDF tooling, algorithmic art, Postgres expertise) is absent from the workspace set. Document why the global skill was preferred if the task overlaps existing local skills.
- **Exclusions & workflows:** do not call global scaffolding/testing skills when local equivalents exist, and when executing the `/enhance` workflow or any prompt-engineering task, ensure the resulting plan still honors this priority and explicitly names the skill to be invoked.

## Deployment & Environment
- Branch naming: `feature/<slug>` or `fix/<slug>`; commits follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`).
- Docker image built via `.github/workflows/render-image.yml`, deployed to Render. Keep Dockerfile multistage and logs on stdout/stderr.
- Required ENV list (must be set in Render dashboard and local `.env`): `FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`, `MAKECOM_API_KEY`.

## Anti-Patterns (Never Do)
- Write secrets or config fallbacks directly in code.
- Reintroduce `innerHTML` assignments or inline event handlers in the dashboard.
- Bypass Redis store by editing `debug/*.json` directly during runtime.
- Start multiple poller instances in the same deployment; always respect locks and `ENABLE_BACKGROUND_TASKS`.
- Log raw email bodies or personally identifiable information.

## Common Tasks Reference
### Adding a New Service
1. Create `services/<name>_service.py` with singleton pattern (`_instance`, `get_instance()` helper).
2. Inject dependencies via constructor, not globals.
3. Expose typed methods; cache with TTL only when necessary.
4. Register usage where needed (routes, background jobs) without circular imports.

### Extending Dashboard Panels
1. Add markup inside `dashboard.html` within the appropriate `.section-panel`.
2. Create or extend a collector function (`collect<Panel>Data`) and persistence helper.
3. Use `ApiService` for network calls, `MessageHelper` for feedback, `TabManager` for accessibility wiring.
4. Update CSS tokens (colors, transitions) to maintain the established visual language—no ad hoc styles.

By following these Cursor-ready rules, any new engineer or AI assistant can contribute safely without regressing resilience, UX, or security guarantees.