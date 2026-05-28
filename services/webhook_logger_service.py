"""
services.webhook_logger_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Service centralisé gérant les logs des webhooks.
Encapsule l'appel à app_logging.webhook_logger et la dépendance Redis.
"""

from __future__ import annotations
from typing import Optional, Any
from pathlib import Path

from app_logging.webhook_logger import append_webhook_log

class WebhookLoggerService:
    _instance: Optional[WebhookLoggerService] = None

    def __init__(self) -> None:
        if WebhookLoggerService._instance is not None:
            raise RuntimeError("WebhookLoggerService is a singleton. Use get_instance().")
        
        # Le file_path des logs
        import os
        base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
        self.file_path = base_dir / "debug" / "webhook_logs.json"
        self.redis_list_key = "webhook_logs"

    @classmethod
    def get_instance(cls) -> WebhookLoggerService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def append_log(self, log_entry: dict) -> None:
        """Enregistre le log via Redis ou fichier en fallback."""
        # On évite l'import circulaire en important redis_client localement
        # ou en l'injectant, mais ici app_render est le principal possesseur.
        # En fait, redis_client est global dans l'app, ou dans DeduplicationService?
        # En legacy, app_render stocke redis_client en global.
        import sys
        rc = None
        try:
            app_module = sys.modules.get("app_render")
            if app_module and hasattr(app_module, "redis_client"):
                rc = app_module.redis_client
        except Exception:
            pass

        # Pour le logger (app.logger)
        logger = None
        try:
            if app_module and hasattr(app_module, "app"):
                logger = app_module.app.logger
        except Exception:
            pass
        
        append_webhook_log(
            log_entry,
            redis_client=rc,
            logger=logger,
            file_path=self.file_path,
            redis_list_key=self.redis_list_key
        )
