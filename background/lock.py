"""
background.lock
~~~~~~~~~~~~~~~~

Singleton file lock utility to prevent multiple background pollers across processes.
"""
from __future__ import annotations

import fcntl
import logging
import os

# Keep a global reference so the lock is held for the process lifetime
BG_LOCK_FH = None
REDIS_LOCK_CLIENT = None
REDIS_LOCK_TOKEN = None

_REDIS_LOCK_KEY = "render_signal:poller_lock"
_REDIS_LOCK_TTL_SECONDS = 300


def acquire_singleton_lock(lock_path: str) -> bool:
    """Try to acquire an exclusive, non-blocking lock on a file.

    Returns True if the lock is acquired, False otherwise.
    """
    global BG_LOCK_FH
    global REDIS_LOCK_CLIENT
    global REDIS_LOCK_TOKEN

    logger = logging.getLogger(__name__)

    redis_url = os.environ.get("REDIS_URL")
    if isinstance(redis_url, str) and redis_url.strip():
        try:
            import redis

            client = redis.Redis.from_url(redis_url)
            token = f"pid={os.getpid()}"
            acquired = bool(
                client.set(
                    _REDIS_LOCK_KEY,
                    token,
                    nx=True,
                    ex=_REDIS_LOCK_TTL_SECONDS,
                )
            )
            if acquired:
                REDIS_LOCK_CLIENT = client
                REDIS_LOCK_TOKEN = token
            return acquired
        except Exception:
            pass

    logger.warning("Using file-based lock (unsafe for multi-container deployments)")
    try:
        BG_LOCK_FH = open(lock_path, "a+")
        fcntl.flock(BG_LOCK_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        BG_LOCK_FH.write(f"pid={os.getpid()}\n")
        BG_LOCK_FH.flush()
        return True
    except BlockingIOError:
        try:
            if BG_LOCK_FH:
                BG_LOCK_FH.close()
        finally:
            BG_LOCK_FH = None
        return False
    except Exception:
        try:
            if BG_LOCK_FH:
                BG_LOCK_FH.close()
        finally:
            BG_LOCK_FH = None
        return False
