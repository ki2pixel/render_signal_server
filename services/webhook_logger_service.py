"""
services.webhook_logger_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service centralisé gérant les logs des webhooks.
Encapsule l'appel à app_logging.webhook_logger et la dépendance Redis.
"""

from __future__ import annotations
import os
import logging
from typing import Optional, Any
from pathlib import Path

from app_logging.webhook_logger import append_webhook_log


class WebhookLoggerService:
    _instance: Optional[WebhookLoggerService] = None

    def __init__(
        self,
        redis_client: Any = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if WebhookLoggerService._instance is not None:
            raise RuntimeError("WebhookLoggerService is a singleton. Use get_instance().")
        base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
        self.file_path = base_dir / "debug" / "webhook_logs.json"
        self.redis_list_key = "webhook_logs"
        self._redis_client = redis_client
        self._logger = logger

    def configure(self, redis_client: Any = None, logger: Optional[logging.Logger] = None) -> None:
        if redis_client is not None:
            self._redis_client = redis_client
        if logger is not None:
            self._logger = logger

    @classmethod
    def get_instance(cls) -> WebhookLoggerService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def append_log(self, log_entry: dict) -> None:
        rc = self._redis_client
        logger = self._logger

        if rc is None or logger is None:
            try:
                import sys
                app_module = sys.modules.get("app_render")
                if app_module:
                    if rc is None and hasattr(app_module, "redis_client"):
                        rc = app_module.redis_client
                    if logger is None and hasattr(app_module, "app"):
                        logger = app_module.app.logger
            except Exception:
                pass

        append_webhook_log(
            log_entry,
            redis_client=rc,
            logger=logger,
            file_path=self.file_path,
            redis_list_key=self.redis_list_key,
        )
