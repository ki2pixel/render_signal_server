# syntax=docker/dockerfile:1

# --- Étape 1 : Build du Frontend (Node.js) ---
FROM node:22-slim AS frontend-builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY vite.config.js ./
COPY static ./static
RUN npm run build

# --- Étape 2 : Image Finale (Python) ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Les dépendances Python actuelles n'exigent pas de bibliothèques système exotiques,
# mais on installe les utilitaires essentiels pour sécuriser les builds futurs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

# Récupérer les assets minifiés compilés par Vite depuis l'étape 1
COPY --from=frontend-builder /app/static/dist ./static/dist

# Utilisateur non root pour l'exécution.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV PORT=8000 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=120 \
    GUNICORN_GRACEFUL_TIMEOUT=30 \
    GUNICORN_KEEP_ALIVE=75 \
    GUNICORN_MAX_REQUESTS=15000 \
    GUNICORN_MAX_REQUESTS_JITTER=3000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health')" || exit 1

# Gunicorn écrit déjà ses logs sur stdout/stderr ;
# PYTHONUNBUFFERED assure la remontée immédiate des logs applicatifs (BG_POLLER, HEARTBEAT, etc.).
CMD gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers $GUNICORN_WORKERS \
    --threads $GUNICORN_THREADS \
    --timeout $GUNICORN_TIMEOUT \
    --graceful-timeout $GUNICORN_GRACEFUL_TIMEOUT \
    --keep-alive $GUNICORN_KEEP_ALIVE \
    --max-requests $GUNICORN_MAX_REQUESTS \
    --max-requests-jitter $GUNICORN_MAX_REQUESTS_JITTER \
    app_render:app
