"""
Logging helpers for webhook events with Redis and file fallbacks.

- append_webhook_log: push a log entry (keeps last N entries)
- fetch_webhook_logs: retrieve recent logs with optional day window and limit

Design:
- Accept redis_client and logger as injected dependencies
- File path and redis key are passed in by the caller
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from utils.storage_backend import append_list_with_fallback, fetch_list_with_fallback

DEFAULT_MAX_ENTRIES = 500


def append_webhook_log(
    log_entry: dict,
    *,
    redis_client,
    logger,
    file_path: Path,
    redis_list_key: str,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> None:
    append_list_with_fallback(
        item=log_entry,
        redis_client=redis_client,
        redis_list_key=redis_list_key,
        file_path=file_path,
        max_entries=max_entries,
        logger=logger,
    )


def fetch_webhook_logs(
    *,
    redis_client,
    logger,
    file_path: Path,
    redis_list_key: str,
    days: int = 7,
    limit: int = 50,
) -> dict[str, Any]:
    days = max(1, min(30, int(days)))

    all_logs = fetch_list_with_fallback(
        redis_client=redis_client,
        redis_list_key=redis_list_key,
        file_path=file_path,
        logger=logger,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered_logs = []
    for log in all_logs:
        try:
            log_time = datetime.fromisoformat(log.get("timestamp", ""))
            if log_time >= cutoff:
                filtered_logs.append(log)
        except Exception:
            # If timestamp unparsable, include the entry for backward-compat
            filtered_logs.append(log)

    filtered_logs = filtered_logs[-limit:]
    filtered_logs.reverse()

    return {
        "success": True,
        "logs": filtered_logs,
        "count": len(filtered_logs),
        "days_filter": days,
    }
