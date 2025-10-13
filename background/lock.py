"""
background.lock
~~~~~~~~~~~~~~~~

Singleton file lock utility to prevent multiple background pollers across processes.
"""
from __future__ import annotations

import fcntl
import os

# Keep a global reference so the lock is held for the process lifetime
BG_LOCK_FH = None


def acquire_singleton_lock(lock_path: str) -> bool:
    """Try to acquire an exclusive, non-blocking lock on a file.

    Returns True if the lock is acquired, False otherwise.
    """
    global BG_LOCK_FH
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
