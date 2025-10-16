"""
config.app_config_store
~~~~~~~~~~~~~~~~~~~~~~~~

Key-Value configuration store with optional MySQL backend and JSON file fallback.
- Provides get_config_json()/set_config_json() for dict payloads.
- Uses env vars: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
- If MySQL is unavailable or not configured, falls back to per-key JSON files provided by callers.

Security: no secrets are logged; errors are swallowed and caller can fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _mysql_configured() -> bool:
    return bool(
        os.environ.get("MYSQL_HOST")
        and os.environ.get("MYSQL_USER")
        and os.environ.get("MYSQL_PASSWORD")
        and os.environ.get("MYSQL_DATABASE")
    )


def _get_mysql_connection():
    """Return a mysql-connector connection or None if not available/configured."""
    if not _mysql_configured():
        return None
    try:
        import mysql.connector  # type: ignore

        return mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST"),
            user=os.environ.get("MYSQL_USER"),
            password=os.environ.get("MYSQL_PASSWORD"),
            database=os.environ.get("MYSQL_DATABASE"),
            port=int(os.environ.get("MYSQL_PORT" or 3306)),
            autocommit=True,
        )
    except Exception:
        return None


def _ensure_table_exists(conn) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_config (
                  config_key VARCHAR(191) PRIMARY KEY,
                  config_value JSON,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
            )
        return True
    except Exception:
        return False


def get_config_json(key: str, *, file_fallback: Optional[Path] = None) -> Dict[str, Any]:
    """Fetch config dict for a key from MySQL, with optional file fallback.
    Returns empty dict on any error.
    """
    # Try MySQL first
    conn = _get_mysql_connection()
    if conn is not None:
        try:
            _ensure_table_exists(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT config_value FROM app_config WHERE config_key=%s", (key,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    # mysql-connector returns str for JSON by default
                    val = row[0]
                    if isinstance(val, (bytes, bytearray)):
                        val = val.decode("utf-8", errors="ignore")
                    if isinstance(val, str):
                        data = json.loads(val)
                    else:
                        data = val  # already decoded by driver
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # Fallback to file
    if file_fallback and file_fallback.exists():
        try:
            with open(file_fallback, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                if isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}


def set_config_json(key: str, value: Dict[str, Any], *, file_fallback: Optional[Path] = None) -> bool:
    """Persist config dict for a key into MySQL, fallback to file if needed."""
    # Try MySQL
    conn = _get_mysql_connection()
    if conn is not None:
        try:
            _ensure_table_exists(conn)
            payload = json.dumps(value, ensure_ascii=False)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_config (config_key, config_value) VALUES (%s, %s)\n                     ON DUPLICATE KEY UPDATE config_value=VALUES(config_value)",
                    (key, payload),
                )
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    # Fallback to file
    if file_fallback is not None:
        try:
            file_fallback.parent.mkdir(parents=True, exist_ok=True)
            with open(file_fallback, "w", encoding="utf-8") as f:
                json.dump(value, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    return False
