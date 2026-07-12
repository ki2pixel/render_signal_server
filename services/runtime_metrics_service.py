"""
services.runtime_metrics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Singleton service tracking runtime metrics: process start time and last poll cycle.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional


class RuntimeMetricsService:
    _instance: Optional[RuntimeMetricsService] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        if RuntimeMetricsService._instance is not None:
            raise RuntimeError("RuntimeMetricsService is a singleton. Use get_instance().")
        self._process_start_time: Optional[datetime] = datetime.now(timezone.utc)
        self._last_poll_cycle_ts: Optional[int] = None

    @classmethod
    def get_instance(cls) -> RuntimeMetricsService:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def get_process_start_time(self) -> Optional[datetime]:
        return self._process_start_time

    def set_process_start_time(self, dt: datetime) -> None:
        self._process_start_time = dt

    def get_last_poll_cycle_ts(self) -> Optional[int]:
        return self._last_poll_cycle_ts

    def set_last_poll_cycle_ts(self, ts: int) -> None:
        self._last_poll_cycle_ts = ts
