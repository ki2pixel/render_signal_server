"""
utils.limiter
~~~~~~~~~~~~

Rate limiting global pour l'application Flask.

Features:
- Stockage Redis en production (si REDIS_URL défini), mémoire en fallback
- Clé de rate limiting basée sur l'adresse IP distante
- Instance globale réutilisable injectée dans les blueprints
- Graceful fallback to memory if Redis is unreachable

Usage:
    from utils.limiter import limiter

    @limiter.limit("5 per 5 minutes")
    def my_route():
        ...
"""

from __future__ import annotations
import os
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

_logger = logging.getLogger(__name__)

_redis_url = os.environ.get("REDIS_URL", "").strip()

if _redis_url:
    try:
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=_redis_url,
            default_limits=[],
        )
    except Exception:
        _logger.warning(
            "LIMITER: Failed to connect to Redis at %s, falling back to memory storage", _redis_url
        )
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri="memory://",
            default_limits=[],
        )
else:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        default_limits=[],
    )
