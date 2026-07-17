"""
services.rate_limit_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service centralisé gérant le rate limiting avec Redis (partagé entre workers)
et fallback mémoire local.

Features:
- Redis ZSET-based sliding window (partagé entre workers Gunicorn)
- Fallback mémoire local (deque) si Redis indisponible
- Pattern Singleton

Usage:
    from services.rate_limit_service import RateLimitService

    rls = RateLimitService.get_instance()
    rls.configure(redis_client=redis_client)

    if rls.allow_send(limit_per_hour=5):
        rls.record_event()
        # send webhook...
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Optional

from utils.rate_limit import prune_and_allow_send, record_send_event

_REDIS_KEY = "r:ss:rate_limit:webhooks"


class RateLimitService:
    _instance: Optional[RateLimitService] = None

    def __init__(self) -> None:
        if RateLimitService._instance is not None:
            raise RuntimeError("RateLimitService is a singleton. Use get_instance().")
        self._webhook_send_times: deque[float] = deque()
        self._redis_client = None

    @classmethod
    def get_instance(cls) -> RateLimitService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def configure(self, redis_client=None) -> None:
        """Injecte un client Redis pour le rate limiting distribué."""
        self._redis_client = redis_client

    def allow_send(self, limit_per_hour: int) -> bool:
        """Vérifie si on peut envoyer en fonction de la limite par heure.

        Utilise Redis (ZSET) si disponible, fallback sur deque mémoire.
        """
        if self._redis_client:
            try:
                return self._allow_send_redis(limit_per_hour)
            except Exception:
                pass
        return prune_and_allow_send(self._webhook_send_times, limit_per_hour)

    def record_event(self) -> None:
        """Enregistre un envoi réussi."""
        if self._redis_client:
            try:
                self._record_event_redis()
                return
            except Exception:
                pass
        record_send_event(self._webhook_send_times)

    def _allow_send_redis(self, limit_per_hour: int) -> bool:
        now = time.time()
        one_hour_ago = now - 3600
        self._redis_client.zremrangebyscore(_REDIS_KEY, 0, one_hour_ago)
        count = self._redis_client.zcard(_REDIS_KEY)
        if count >= limit_per_hour:
            return False
        entry_id = str(uuid.uuid4())
        self._redis_client.zadd(_REDIS_KEY, {entry_id: now})
        self._redis_client.expire(_REDIS_KEY, 3900)
        return True

    def _record_event_redis(self) -> None:
        now = time.time()
        entry_id = str(uuid.uuid4())
        self._redis_client.zadd(_REDIS_KEY, {entry_id: now})
        self._redis_client.expire(_REDIS_KEY, 3900)
