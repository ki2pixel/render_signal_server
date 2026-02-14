# AGENTS.md - Guide pour Agents de Codage

> **AI Agent Context**: This document provides essential information for AI coding agents working on `render_signal_server`. It acts as the primary operating system for Kimi Code.

---

## Vue d'Ensemble

**render_signal_server** est un middleware d'ingestion email haute performance.
- **Flux Principal** : Gmail Push (Webhooks) → Traitement (Regex/Routing) → Webhooks sortants (Make/Zapier).
- **Stockage** : Redis (Production) avec Fallback JSON (Dev/Rescue).
- **Frontend** : Dashboard Single-Page App (Vanilla JS ES6) pour la configuration dynamique.

## 🧠 Operational Skills & Runbooks (The Router)

You **MUST** route requests to the specialized skills in `.sixthskills/` to ensure configuration integrity and proper testing.

### Skill Invocation Policy (Priority Order)
- **Priority order:** always invoke workspace-scoped skills under `.sixthskills/` before falling back to the global catalog in `/home/kidpixel/.codeium/skills`. The local skills encapsulate project-specific scripts, environments, and templates that enforce these coding standards.
- **Global skills usage:** reach for `/home/kidpixel/.codeium/skills/*` only when a needed capability (e.g., PDF tooling, algorithmic art, Postgres expertise) is absent from the workspace set. Document why the global skill was preferred if the task overlaps existing local skills.
- **Exclusions & workflows:** do not call global scaffolding/testing skills when local equivalents exist, and when executing the `/enhance` workflow or any prompt-engineering task, ensure the resulting plan still honors this priority and explicitly names the skill to be invoked.

| User Intent / Context | Target Skill File (load with @) | Key Focus |
|:---|:---|:---|
| **Config / Redis / Persistence** | `.sixthskills/redis-config-guardian/SKILL.md` | **CRITICAL**. Audit sync Redis ↔ JSON. |
| **Tests / Pytest / CI** | `.sixthskills/testing-matrix-navigator/SKILL.md` | Select unit vs integration vs resilience suites. |
| **Routing / Rules / Engine** | `.sixthskills/routing-rules-orchestrator/SKILL.md` | Logical operators, schema validation, orchestration. |
| **R2 / Files / Offload** | `.sixthskills/r2-transfer-service-playbook/SKILL.md` | Cloudflare Workers headers, allowlists. |
| **Auth / Magic Links** | `.sixthskills/magic-link-auth-companion/SKILL.md` | Token revocation, HMAC signature. |
| **UI / Dashboard / UX** | `.sixthskills/webhook-dashboard-ux-maintainer/SKILL.md` | Autosave, WCAG, ES6 Modules. |
| **Debug / Crash / Error** | `.sixthskills/debugging-strategies/SKILL.md` | Log analysis pattern, scientific method. |
| **Docs / Audit** | `.sixthskills/docs-sync-automaton/SKILL.md` | Codebase metrics (radon/cloc) to docs sync. |
| **Check Config** | `.sixthskills/check-config/SKILL.md` | Vérifie l'état du Config Store (Redis/Fichier) via les scripts utilitaires. |
| **Run Tests** | `.sixthskills/run-tests/SKILL.md` | Exécute la suite de tests (unitaires, résilience, couverture) en utilisant l'environnement virtuel spécifique du projet. |
| **Scaffold JS Module** | `.sixthskills/scaffold-js-module/SKILL.md` | Crée un nouveau module ou service JavaScript (ES6) pour le frontend static. |
| **Scaffold Service** | `.sixthskills/scaffold-service/SKILL.md` | Génère un nouveau Service Python (Singleton) respectant l'architecture et les coding standards du projet. |
| **Documentation** | `.sixthskills/documentation/SKILL.md` | Technical writing, README guidelines, and punctuation rules. Use when writing documentation, READMEs, technical articles, or any prose that should avoid AI-generated feel. |

**Protocol:** If the user asks "Why is the config not saving?", consult `.sixthskills/redis-config-guardian/SKILL.md` immediately to run the audit script.

---

## 🛡️ Critical Implementation Rules (Non-Negotiable)

### 1. Redis-First Authority
- **Source of Truth**: Redis is the master for `routing_rules`, `webhook_config`, `processing_prefs`.
- **Forbidden**: NEVER edit `debug/*.json` files directly at runtime. Use `AppConfigStore.set_config_json()` or the dashboard API.
- **Failover**: The JSON files are only for bootstrap/fallback when Redis is down.

### 2. Ingestion Discipline
- **Gmail Push Only**: The active ingress is `POST /api/ingress/gmail` (Bearer Token).
- **Legacy Retired**: Do NOT work on `imap_client.py` or polling threads unless explicitly asked for migration purposes.
- **Security**: Raw email bodies must NEVER be logged. Use `app_logging.mask_sensitive_data`.

### 3. Environment & Venv
- **Strict Venv**: Always use `/mnt/venv_ext4/venv_render_signal_server/bin/python`.
- **Required ENV list** (must be set in Render dashboard and local `.env`):
  - `FLASK_SECRET_KEY`
  - `TRIGGER_PAGE_PASSWORD`
  - `PROCESS_API_TOKEN`
  - `WEBHOOK_URL`
- **Optional legacy IMAP variables** (not used by Gmail Push, kept for tests only):
  - `EMAIL_ADDRESS`
  - `EMAIL_PASSWORD`
  - `IMAP_SERVER`

### 4. Frontend Standards
- **No Frameworks**: Pure ES6 Modules in `static/`.
- **No innerHTML**: Use `document.createElement` or `textContent`.
- **Autosave**: UI must handle `saving` -> `saved`/`error` states with debounce.

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

### Gmail Push Ingress Flow
```python
@bp.route("/gmail", methods=["POST"])
def ingest_gmail():
    if not auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    # Validate required fields, check sender allowlist, apply time windows
    # Trigger orchestrator.send_custom_webhook_flow() with enriched payload
    return jsonify({"success": True, "status": "processed"}), 200
```
- **Pattern:** Authenticate → Validate → Enrich → Send webhook. Never bypass `AuthService` or log raw email content.

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

## Code Style & Structure
### Backend (Python)
- **Clean Code:** Delete commented-out dead code immediately (no confirmation needed). Comments must state the *why* (intent/business context), never re-describe implementation details.
- Services are **singletons with typed public methods** (see `RoutingRulesService`, `WebhookConfigService`). Never mutate module-level globals at runtime; read via service getters each time.
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
- Secrets (passwords, tokens) **must come from ENV**. `_get_required_env()` in `config/settings.py` enforces the four mandatory variables—do not bypass it.
- Redis is the **source of truth** for `routing_rules`, `webhook_config`, `processing_prefs`, and `magic_link_tokens`. Any API or background logic must read via `AppConfigStore` every time.

### Gmail Push Ingress
- All email ingestion occurs via `POST /api/ingress/gmail` with Bearer token authentication (`AuthService.verify_api_key_from_request()`).
- Validate required fields (sender, body) and enforce sender allowlist via `GMAIL_SENDER_ALLOWLIST`.
- Apply pattern matching (Media Solution/DESABO) and time window rules before triggering webhook flow.
- Enrich delivery links with R2 offload when enabled; fallback gracefully on R2 failures.

### Frontend Experience
- Maintain the dashboard’s **Status Banner + Timeline Canvas + collapsible Webhook panels**. These are non-negotiable UX baselines.
- All destructive or long-running UI actions require visible feedback: ripple on buttons, toast via `MessageHelper`, and disabled states while waiting for the API.

## 🔧 Tooling & Testing Standards

### Code Formatters
- **Python**: `black` (88 cols) + `isort`.
- **JavaScript**: `Prettier` + `ESLint`.
- **PHP**: PSR-12 compliance.

### Testing
- Use `/mnt/venv_ext4/venv_render_signal_server` for parity with CI.
- Commands:
  - `pytest --cov=.` (full suite)
  - `pytest -m "redis or r2 or resilience" --cov=.` (resilience focus)
  - `python -m scripts.check_config_store` (Redis JSON sanity)
- Add tests alongside functionality: routes in `tests/routes/`, services in `tests/services/`, ingress logic in dedicated integration modules.
- Favor Given/When/Then naming and explicit fixtures.

## 🚫 Anti-Patterns (Never Do)
- Write secrets or config fallbacks directly in code.
- Reintroduce `innerHTML` assignments or inline event handlers in the dashboard.
- Bypass Redis store by editing `debug/*.json` files directly at runtime.
- Disable authentication on `/api/ingress/gmail` or expose PROCESS_API_TOKEN in logs.
- Log raw email bodies or personally identifiable information from Gmail payloads.
- Attempt to restart IMAP polling services (retired).

---

## 🛠️ Execution & Diagnostics

### Starting the App
```bash
# Production/Dev standard launch
/mnt/venv_ext4/venv_render_signal_server/bin/python app_render.py
```

### Diagnostic Scripts (Run via CLI)
*All scripts must use the project venv.*

- **Audit Config (Redis vs File)**:
  `./.sixthskills/redis-config-guardian/audit_redis_configs.sh`
- **Revoke Magic Links**:
  `/mnt/venv_ext4/venv_render_signal_server/bin/python .sixthskills/magic-link-auth-companion/revoke_magic_links.py --all`
- **Run Full Test Suite**:
  `./.sixthskills/run-tests/run_tests.sh`

### Health Checks
```bash
# App Health
curl http://localhost:5000/health

# Redis Consistency Check
/mnt/venv_ext4/venv_render_signal_server/bin/python -m scripts.check_config_store --keys routing_rules
```

---

## Structure du Projet

```
render_signal_server/
├── app_render.py              # Point d'entrée Flask
├── config/                    # Configuration & Store
│   ├── app_config_store.py    # Le cœur Redis/JSON
│   └── settings.py            # Vars d'env
├── services/                  # Logique métier (Singletons)
│   ├── routing_rules_service.py
│   ├── r2_transfer_service.py
│   └── ...
├── routes/                    # Endpoints (Minces)
├── email_processing/          # Moteur de règles
│   └── orchestrator.py        # Chef d'orchestre Ingress -> Webhook
├── static/                    # Frontend ES6
├── tests/                     # Pytest suite
└── .sixthskills/              # Specialized Agent Skills
```

---

## 💾 Memory Bank Protocol

1. **Start of Task**: Read `memory-bank/activeContext.md` to understand current focus (e.g., "Migrating to R2").
2. **Configuration Changes**: If you modify a setting structure, you MUST update:
   - `memory-bank/systemPatterns.md` (Schema definition)
   - `memory-bank/decisionLog.md` (Why the change?)
3. **End of Task**: Update `memory-bank/progress.md` with the outcome.

---

## 📝 Documentation Workflow

Whenever you update documentation (`docs/`), you **must** apply the methodology defined in `.sixthskills/documentation/SKILL.md`:
- **TL;DR** at the top.
- **Problem-first** approach.
- **❌/✅ blocks** for trade-offs.
- **Trade-offs** table for architectural choices.
- **Golden Rule** summary.

Treat this skill file as the authoritative checklist before writing.