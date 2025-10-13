"""
Tests for background/lock.py
"""
import os
from pathlib import Path

from background import lock


def test_acquire_singleton_lock_creates_and_writes_pid(temp_dir):
    lock_file = temp_dir / "poller.lock"
    # Ensure file does not exist initially
    assert not lock_file.exists()

    ok = lock.acquire_singleton_lock(str(lock_file))
    assert ok is True

    # File should exist and contain the pid line
    assert lock_file.exists()
    content = lock_file.read_text()
    assert f"pid={os.getpid()}" in content
