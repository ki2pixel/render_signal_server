# Operational Guide: Render Free Behavior, Restarts, and Monitoring

## Overview
- **Purpose**: Explain Render Free wake-up/sleep behavior, how Gunicorn worker recycling interacts with platform restarts, and recommended monitoring settings to keep the service responsive.
- **Scope**: `render_signal_server` deployed on Render with Gunicorn and Flask.

## Render Free Tier Behavior
- **Idle sleep**: Services can be suspended when no traffic occurs. They wake on the next request (health check, user, or uptime monitor).
- **Restarts vs recycling**:
  - Gunicorn options like `--max-requests` recycle workers in-process. They do not force a platform restart.
  - Platform restarts can occur on deploys, maintenance, resource pressure, or plan constraints.
- **Implication**: After a SIGTERM (platform shutdown), the app may not immediately restart unless there is incoming traffic/health probe.

## Recommended Gunicorn Settings
- Set `GUNICORN_CMD_ARGS` in Render environment variables:
  - `--timeout 120 --graceful-timeout 30 --keep-alive 75 --threads 2 --max-requests 15000 --max-requests-jitter 3000`
- Start command example:
  - `gunicorn --workers 1 --bind 0.0.0.0:$PORT app_render:app`

## Health Checks and Uptime Monitoring
- **Render Health Check**
  - Path: `/health` (provided by `routes/health.py`)
  - Keep default intervals/timeouts appropriate to plan limits.
- **External Monitor (UptimeRobot)**
  - Prefer monitoring `https://<your-service>.onrender.com/health` for consistency with Render.
  - Set frequency to **≤ 5 minutes** (lower if your plan allows). This keeps the service warm and ensures rapid wake-up after idle.
  - Alternative endpoint: `/api/ping` (JSON pong). Either works; `/health` aligns with Render.

## Expected Logs
- On boot:
  - Gunicorn banner ("Starting gunicorn …", "Booting worker …").
  - Application startup logs (config summaries).
  - Background threads:
    - `BG_POLLER: Singleton lock acquired …` when started.
    - `HEARTBEAT: alive (threads: {count} active, {daemon} daemon)` - Sent every 5 minutes to confirm background threads are running.
    - `MAKE_WATCHER: background thread started (vacation-aware ON/OFF)` - Only if both `ENABLE_BACKGROUND_TASKS` and `MAKECOM_API_KEY` are set.
- On platform stop:
  - `PROCESS: SIGTERM received; shutting down gracefully (platform restart/deploy).`
  - `MAKE_WATCHER: Applying desired=False (enable_ui=…, in_vacation=…)` - If Make watcher was running.
- During inactive hours:
  - `BG_POLLER: Outside active period. Sleeping.` every `POLLING_INACTIVE_CHECK_INTERVAL_SECONDS`.
  - `HEARTBEAT: alive (threads: {count} active, {daemon} daemon)` - Continues during inactive periods.

## Configuration Checklist
- Render → Image-based service:
  - Utilise l’image `ghcr.io/<owner>/<repo>:latest` poussée via GitHub Actions.
  - Le Dockerfile définit déjà `CMD gunicorn ... app_render:app`. Ne pas surcharger la commande de démarrage.
- Render → Environment Variables:
  - `ENABLE_BACKGROUND_TASKS=1` (uniquement sur un worker)
  - `BG_POLLER_LOCK_FILE=/tmp/render_signal_server_email_poller.lock`
  - `GUNICORN_*` (workers, threads, timeouts) si vous devez ajuster les valeurs par défaut indiquées dans le Dockerfile.
  - `WEBHOOKS_TIME_START/WEBHOOKS_TIME_END`, `CORS_ALLOWED_ORIGINS`, secrets applicatifs (`WEBHOOK_URL`, `TRIGGER_PAGE_*`, etc.)
- Render → Health Check:
  - Path `/health` (cf. `routes/health.py`)
- UptimeRobot (ou équivalent):
  - Target `/health`, interval ≤ 5 min pour maintenir le service “warm”.

## Troubleshooting
- **No restart after SIGTERM**
  - Confirm external monitor is active and polling ≤ 5 min.
  - Check Render dashboard logs for a fresh Gunicorn start sequence.
  - Ensure Start Command binds to `$PORT` and no port conflicts.
- **Poller not running after boot**
  - Verify `ENABLE_BACKGROUND_TASKS=1` and UI flag `enable_polling` (persisted) is true.
  - Check for `BG_POLLER: Singleton lock acquired` line.
- **Make watcher 401 noise**
  - Absent if `MAKECOM_API_KEY` is unset; code suppresses the watcher thread in that case.

## Notes
- Free-tier idle sleep is expected; use paid plans or frequent monitors for always-on behavior.
- Logs avoid secrets and follow the project's `codingstandards.md`.
- Pour relancer un déploiement manuellement : utiliser `/api/deploy_application` (priorité Deploy Hook → API → fallback), ou déclencher le workflow GitHub Actions “Build & Deploy Render Image”.
