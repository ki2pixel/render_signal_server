"""
Logging helpers for webhook events with Redis and file fallbacks.

- append_webhook_log: push a log entry (keeps last N entries)
- fetch_webhook_logs: retrieve recent logs with optional day window and limit

Design:
- Accept redis_client and logger as injected dependencies
- File path and redis key are passed in by the caller
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
    # Try Redis first
    try:
        if redis_client is not None:
            redis_client.rpush(redis_list_key, json.dumps(log_entry, ensure_ascii=False))
            # Trim to last max_entries
            redis_client.ltrim(redis_list_key, -max_entries, -1)
            return
    except Exception as e:
        if logger:
            logger.error(f"WEBHOOK_LOG: redis write error: {e}")
    # Fallback to file
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            except Exception:
                logs = []
        logs.append(log_entry)
        if len(logs) > max_entries:
            logs = logs[-max_entries:]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        if logger:
            logger.error(f"WEBHOOK_LOG: file write error: {e}")


def fetch_webhook_logs(
    *,
    redis_client,
    logger,
    file_path: Path,
    redis_list_key: str,
    days: int = 7,
    limit: int = 50,
) -> dict[str, Any]:
    # Validate days bounds
    days = max(1, min(30, int(days)))

    # Try Redis first
    all_logs = None
    try:
        if redis_client is not None:
            items = redis_client.lrange(redis_list_key, 0, -1)
            all_logs = []
            for it in items:
                try:
                    s = it if isinstance(it, str) else it.decode("utf-8")
                    all_logs.append(json.loads(s))
                except Exception:
                    pass
    except Exception as e:
        if logger:
            logger.error(f"WEBHOOK_LOG: redis read error: {e}")

    # Fallback to file
    if all_logs is None:
        if not file_path.exists():
            return {"success": True, "logs": [], "count": 0, "days_filter": days}
        with open(file_path, "r", encoding="utf-8") as f:
            all_logs = json.load(f)

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

    # Limit to last N and reverse to newest first
    filtered_logs = filtered_logs[-limit:]
    filtered_logs.reverse()

    return {
        "success": True,
        "logs": filtered_logs,
        "count": len(filtered_logs),
        "days_filter": days,
    }
