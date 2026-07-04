"""
utils/storage_backend.py

Resilient storage backend with Redis -> JSON File -> Memory fallbacks.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_with_fallback(
    *,
    redis_client: Any,
    redis_key: str | None,
    file_path: Path,
    defaults: dict[str, Any],
    logger: Any = None,
) -> dict[str, Any]:
    """Loads a JSON object/dict with fallbacks: Redis -> File -> Memory (defaults)."""
    # 1. Try Redis
    if redis_client is not None and redis_key:
        try:
            raw = redis_client.get(redis_key)
            if raw:
                data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
                if isinstance(data, dict):
                    return {**defaults, **data}
        except Exception as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: redis load error for {redis_key}: {e}")

    # 2. Try File
    if file_path:
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {**defaults, **data}
        except (OSError, json.JSONDecodeError) as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: file load error for {file_path}: {e}")

    # 3. Fallback to memory
    return dict(defaults)


def save_json_with_fallback(
    data: dict[str, Any],
    *,
    redis_client: Any,
    redis_key: str | None,
    file_path: Path,
    logger: Any = None,
) -> bool:
    """Saves a JSON object/dict with fallbacks: Redis -> File."""
    # 1. Try Redis first
    if redis_client is not None and redis_key:
        try:
            redis_client.set(redis_key, json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: redis save error for {redis_key}: {e}")

    # 2. Fallback to File
    if file_path:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except OSError as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: file save error for {file_path}: {e}")
    return False


def append_list_with_fallback(
    item: dict[str, Any],
    *,
    redis_client: Any,
    redis_list_key: str | None,
    file_path: Path,
    max_entries: int,
    logger: Any = None,
) -> None:
    """Appends an item to a list stored in Redis or File fallback."""
    # 1. Try Redis first
    if redis_client is not None and redis_list_key:
        try:
            redis_client.rpush(redis_list_key, json.dumps(item, ensure_ascii=False))
            redis_client.ltrim(redis_list_key, -max_entries, -1)
            return
        except Exception as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: redis rpush/ltrim error for {redis_list_key}: {e}")

    # 2. Fallback to File
    if file_path:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logs = []
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                except (OSError, json.JSONDecodeError):
                    logs = []
            logs.append(item)
            if len(logs) > max_entries:
                logs = logs[-max_entries:]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        except OSError as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: file append error for {file_path}: {e}")


def fetch_list_with_fallback(
    *,
    redis_client: Any,
    redis_list_key: str | None,
    file_path: Path,
    logger: Any = None,
) -> list[dict[str, Any]]:
    """Fetches list items from Redis or File fallback."""
    # 1. Try Redis first
    if redis_client is not None and redis_list_key:
        try:
            items = redis_client.lrange(redis_list_key, 0, -1)
            all_logs = []
            for it in items:
                try:
                    s = it if isinstance(it, str) else it.decode("utf-8")
                    all_logs.append(json.loads(s))
                except Exception:
                    pass
            return all_logs
        except Exception as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: redis read error for {redis_list_key}: {e}")

    # 2. Fallback to File
    if file_path:
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    all_logs = json.load(f)
                    if isinstance(all_logs, list):
                        return all_logs
        except (OSError, json.JSONDecodeError) as e:
            if logger:
                logger.error(f"STORAGE_BACKEND: file read error for {file_path}: {e}")

    return []
