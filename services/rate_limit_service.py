"""
services.rate_limit_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service centralisé gérant le rate limiting.
Encapsule l'état global et abstrait utils.rate_limit.
"""

from __future__ import annotations
from collections import deque
from typing import Optional
from utils.rate_limit import prune_and_allow_send, record_send_event

class RateLimitService:
    _instance: Optional[RateLimitService] = None

    def __init__(self) -> None:
        if RateLimitService._instance is not None:
            raise RuntimeError("RateLimitService is a singleton. Use get_instance().")
        self._webhook_send_times: deque[float] = deque()

    @classmethod
    def get_instance(cls) -> RateLimitService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Utile pour les tests."""
        cls._instance = None

    def allow_send(self, limit_per_hour: int) -> bool:
        """Vérifie si on peut envoyer en fonction de la limite par heure."""
        return prune_and_allow_send(self._webhook_send_times, limit_per_hour)

    def record_event(self) -> None:
        """Enregistre un envoi réussi."""
        record_send_event(self._webhook_send_times)

