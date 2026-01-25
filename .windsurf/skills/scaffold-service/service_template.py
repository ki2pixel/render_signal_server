"""
services.new_service
~~~~~~~~~~~~~~~~~~~~

Service description here.

Features:
- Pattern Singleton
- Thread-safe
"""
from __future__ import annotations

import logging
import threading
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.config_service import ConfigService
    from config.app_config_store import AppConfigStore

class NewService:
    """Service description alignée avec l'architecture services + Redis-first.

    Attributes:
        _instance: Instance singleton
        _config: Service de configuration (ENV)
        _store: AppConfigStore Redis-first
        _logger: Logger centralisé
    """

    _instance: Optional[NewService] = None
    _lock = threading.RLock()

    def __init__(
        self,
        config_service: Optional[ConfigService] = None,
        app_config_store: Optional[AppConfigStore] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialise le service (utiliser get_instance() de préférence)."""
        self._config = config_service
        self._store = app_config_store
        self._logger = logger or logging.getLogger(__name__)

    @classmethod
    def get_instance(
        cls,
        config_service: Optional[ConfigService] = None,
        app_config_store: Optional[AppConfigStore] = None,
    ) -> NewService:
        """Récupère ou crée l'instance singleton."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config_service, app_config_store)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Réinitialise l'instance (pour tests)."""
        with cls._lock:
            cls._instance = None

    def perform_action(self) -> bool:
        """Exemple de méthode métier avec stratégie Always Fallback."""
        try:
            payload = self._read_from_store()
            if payload is None:
                return self._fallback_value()
            self._logger.info("SVC: Action performed with payload")
            return True
        except Exception as exc:
            self._logger.warning("SVC: fallback after error: %s", exc)
            return self._fallback_value()

    def _read_from_store(self) -> Optional[dict]:
        """Lit les données métier depuis AppConfigStore (Redis-first)."""
        if not self._store:
            return None
        return self._store.get_config_json("new_service")

    def _fallback_value(self) -> bool:
        """Retourne une valeur sûre lorsque Redis ou la logique échoue."""
        self._logger.info("SVC: returning safe default value")
        return False
