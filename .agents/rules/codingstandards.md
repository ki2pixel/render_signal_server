---
trigger: always_on
description: Core engineering standards and enforced conventions for render_signal_server
globs: 
---

# render_signal_server – Antigravity Rules (v2026-01)

These rules are the single source of truth for backend (Flask), frontend (modular ES6), and legacy PHP/R2 tooling. Apply them to every change unless an explicit exception is documented here.

## Tech Stack
- **Backend:** Python 3.11, Flask app (`app_render.py`), services (`services/`), routes (`routes/`).
- **Ingestion:** Idempotent Gmail Push API (`POST /api/ingress/gmail`) via `IngressService` & `DeduplicationService` (Redis TTL hash).
- **Frontend:** `dashboard.html` + ES6 modules (`static/`) bundlés avec **Vite** (fallback automatique en dev).
- **Storage:** Redis-first config store via `ConfigService` avec JSON fallback; Cloudflare R2 offload via `R2TransferService`.
- **Legacy helpers:** Minimal PHP footprint (Render deployment helpers + webhook receiver) adhering to PSR-12.
- **Tooling:** `black` (88 cols) + `isort` for Python, `Prettier` + `ESLint` + `Vite` for JS, `pytest` with custom markers, Docker + Render for deployment.

## Code Style & Structure
### Backend (Python)
- **Clean Code:** Delete dead code immediately. Comments state the *why*, never the *how*. Keep cognitive complexity strictly low (extract logic into smaller helpers).
- Services are **singletons** (`ConfigService`, `IngressService`). Read via service getters, never mutate module globals.
- Keep functions short (<40 lines). Type hints are mandatory (e.g., `from flask import Response`, `-> Response | tuple[Response, int]`). Use `TypedDict`/dataclasses.
- Input validation lives at route boundaries. Raise `ValueError`/`BadRequest` with explicit messages; let Flask error handlers serialize. Prevent Open Redirects by strictly validating all redirect targets.
- **PII & Logging:** Logging goes through `app_logging/` helpers. You **must** systematically scrub PII (emails, tokens, names) using `mask_sensitive_data` before logging.

### Frontend (JS/HTML)
- Use **modules + named exports** only. `dashboard.js` orchestrates modules.
- **Modern JS:** Use `Object.hasOwn(obj, key)` exclusively for property checking. Ban legacy `obj.hasOwnProperty(key)` syntax.
- DOM updates: Bannir les IDs globaux absolus et `innerHTML`. Privilégier le découplage via `DOMHelper` (ex: `DOMHelper.getElement("myBtn")` résout `[data-target="myBtn"]`).
- Respect WCAG AA: keyboard focus states, ARIA roles (`tablist`, `tabpanel`, `aria-expanded`).
- Auto-save flows use debounced `ApiService` calls (2–3s) with optimistic UI + rollback on failure (toujours implémenter l'interception `beforeunload` pour éviter la perte de données).
- **Performance UI:** Utiliser le rendu paresseux (Lazy Rendering / Chunking) pour prévenir les gels d'interface (ex: `JsonViewer`).

### Legacy / Infra
- PHP utilities stay PSR-12, UTF-8 LF, no short tags. File writes must be atomic (temp file + rename) guarded by `flock` or Python-side `RLock`.
- Cloudflare Workers: keep headers explicit (`X-R2-FETCH-TOKEN`), enforce allowlists.

## Architecture Decisions to Enforce
### Configuration & Secrets
- Secrets (passwords, tokens) **must come from ENV**. `_get_required_env()` in `config/settings.py` enforces the four mandatory variables—do not bypass it.
- Redis is the **source of truth** for `routing_rules`, `webhook_config`, `processing_prefs`, and `magic_link_tokens`. Any API or background logic must read via `ConfigService` every time.

### Gmail Push Ingress
- All email ingestion occurs via `POST /api/ingress/gmail` with Bearer token authentication (`AuthService.verify_api_key_from_request()`).
- Validate required fields (sender, body) and enforce sender allowlist via `GMAIL_SENDER_ALLOWLIST`.
- Apply pattern matching (Media Solution/DESABO) and time window rules before triggering webhook flow.
- Enrich delivery links with R2 offload when enabled; fallback gracefully on R2 failures.

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
    _config_service.set_config_json("processing_prefs", payload)
    return jsonify({"status": "ok"})
```
- **Pattern:** Load schema, validate, persist via `ConfigService`, return JSON. Never write to `settings` globals.

### Gmail Push Ingress Flow
```python
from flask import Response, jsonify
@bp.route("/gmail", methods=["POST"])
def ingest_gmail() -> tuple[Response, int] | Response:
    if not _auth_service.verify_api_key_from_request(request): return jsonify(...), 401
    # AuthService Auth + DeduplicationService (Redis hash/ID + TTL) assurent l'idempotence
    res, code = ingress_service.process_gmail_push(request.get_json(silent=True))
    return jsonify(res), code
```
- **Pattern:** Auth → Deduplicate → Process. Never bypass `AuthService` or log raw email bodies.

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
- Environment: `/mnt/venv_ext4/venv_render_signal_server`.
- Commands: `pytest -m "redis or r2 or resilience" --cov=.`
- Add tests alongside functionality (`tests/routes/`, `tests/services/`).
- Structure tests strictly with **# Given / # When / # Then** blocks. Use explicit fixtures and ensure mock isolation.
- **Shell Scripting:** Strictly align bash syntax to use `[[ ]]` for all conditions in test and internal scripts, banishing legacy `[ ]` or `test`.

### Skill Invocation Policy (Workspace vs Global)
- **Priority order:** always invoke workspace-scoped skills under `.agents/skills/` before falling back to the global catalog in `~/.gemini/antigravity/skills`. The local skills encapsulate project-specific scripts, environments, and templates that enforce these coding standards.
  - `redis-config-guardian` remplace/complète le skill `check-config` pour tout audit de `processing_prefs`, `routing_rules`, `webhook_config`, `magic_link_tokens`. Il orchestre le script CLI + l’API dashboard.
  - `debugging-strategies` est obligatoire pour toute tâche de débogage (bugs, incidents de performances, comportements inattendus) avant d’envisager le moindre recours aux skills globaux ou à des ressources externes.
  - Le skill `run-tests` reste la porte d’entrée canonique pour `pytest`; `scaffold-js-module` et `scaffold-service` demeurent obligatoires pour les nouveaux modules/services.
  - `check-config` : Vérifie l'état du Config Store (Redis/Fichier) via les scripts utilitaires.
  - `docs-sync-automaton` : Analyse la Memory Bank, inspecte le code source impacté, et met à jour TOUTE la documentation associée.
  - `documentation` : Technical writing, README guidelines, and punctuation rules. Use when writing documentation, READMEs, technical articles, or any prose that should avoid AI-generated feel.
  - `magic-link-auth-companion` : Manage MagicLinkService changes across backend, storage (Redis/external), and dashboard UI while enforcing security, TTL, and revocation requirements.
  - `r2-transfer-service-playbook` : Manage changes to the R2 transfer pipeline (Python service, Cloudflare Workers, PHP logger) with mandatory validations, allowlists, and regression checks.
  - `routing-rules-orchestrator` : Streamline any change touching the dynamic routing rules stack (service, API, orchestrator, frontend) with mandatory validation steps and test coverage.
  - `testing-matrix-navigator` : Guide for selecting and executing the correct pytest suites (unit, redis, r2, resilience) with environment setup and coverage expectations.
  - `webhook-dashboard-ux-maintainer` : Preserve and extend the modern dashboard (dashboard.html + static modules) with WCAG-compliant UX, autosave flows, and modular ES6 patterns.
  - `render-deployment-manager` : Manage Render.com deployments and services using MCP tools for service creation, environment management, monitoring, and deployment orchestration.
  - `shrimp-task-manager` : Manage tasks and backlogs using Shrimp Task Manager.
  - `fast-filesystem-ops` : Manage file system operations using Fast Filesystem.
  - `json-query-expert` : Manage JSON queries using JSON Query Expert.
  - `sequentialthinking-logic` : Manage sequential thinking using Sequential Thinking Logic.
- **Global skills usage:** reach for `~/.gemini/antigravity/skills/*` only when a needed capability (e.g., PDF tooling, algorithmic art, Postgres expertise) is absent from the workspace set. Document why the global skill was preferred if the task overlaps existing local skills.
- **Exclusions & workflows:** do not call global scaffolding/testing skills when local equivalents exist, and when executing the `/enhance` workflow or any prompt-engineering task, ensure the resulting plan still honors this priority and explicitly names the skill to be invoked.

## Documentation Updates
- Any time you create or modify documentation (README, docs/, Markdown guides), you **must** apply the methodology defined in `.agents/skills/documentation/SKILL.md` (TL;DR first, problem-first opening, ❌/✅ blocks, trade-offs, Golden Rule). Treat this skill file as the authoritative checklist before writing.

## Deployment & Environment
- Branch naming: `feature/<slug>` or `fix/<slug>`; commits follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`).
- Docker image built via `.github/workflows/render-image.yml`, deployed to Render. Keep Dockerfile multistage and logs on stdout/stderr.
- Required ENV list (must be set in Render dashboard and local `.env`): `FLASK_SECRET_KEY`, `TRIGGER_PAGE_PASSWORD`, `PROCESS_API_TOKEN`, `WEBHOOK_URL`.
- Optional legacy IMAP variables (not used by Gmail Push): `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER` (kept for tests only).

## Anti-Patterns (Never Do)
- Write secrets or config fallbacks directly in code.
- Reintroduce `innerHTML` assignments or inline event handlers in the dashboard.
- Bypass the Redis Config Store (e.g., editing `debug/*.json` directly during runtime or hardcoding cache bypasses).
- Disable authentication on `/api/ingress/gmail` or expose PROCESS_API_TOKEN in logs.
- Log raw email bodies or personally identifiable information from Gmail payloads.
- Trust raw user input for routing/redirects (Open Redirect vulnerability).
- Attempt to restart IMAP polling services or use legacy IMAP variables (`EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`) outside of isolated test environments.

## Notes finales
- Maintenir ce document <12 000 caractères. Réviser après toute évolution majeure.
- Pour toute question, consulter les audits récents (`docs/workflow/audits/`).