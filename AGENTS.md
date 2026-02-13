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