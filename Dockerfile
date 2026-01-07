# syntax=docker/dockerfile:1
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

# Utilisateur non root pour l'exécution.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV PORT=8000
EXPOSE 8000

# Gunicorn écrit déjà ses logs sur stdout/stderr ;
# PYTHONUNBUFFERED assure la remontée immédiate des logs applicatifs (BG_POLLER, HEARTBEAT, etc.).
CMD gunicorn \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${GUNICORN_WORKERS:-2} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} \
    --keep-alive ${GUNICORN_KEEP_ALIVE:-75} \
    --max-requests ${GUNICORN_MAX_REQUESTS:-15000} \
    --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-3000} \
    app_render:app
