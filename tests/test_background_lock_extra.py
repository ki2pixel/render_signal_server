"""
Extra tests for background/lock.py failure branches
"""
import builtins
from unittest.mock import MagicMock

import pytest

from background import lock


@pytest.mark.unit
def test_acquire_singleton_lock_blockingioerror(monkeypatch, tmp_path):
    # Monkeypatch fcntl.flock to raise BlockingIOError
    class FakeFcntl:
        LOCK_EX = 2
        LOCK_NB = 4
        @staticmethod
        def flock(fd, flags):
            raise BlockingIOError()
    monkeypatch.setattr(lock, 'fcntl', FakeFcntl)

    lock_file = tmp_path / "poller.lock"
    ok = lock.acquire_singleton_lock(str(lock_file))
    assert ok is False


@pytest.mark.unit
def test_acquire_singleton_lock_generic_exception(monkeypatch, tmp_path):
    # Monkeypatch open to raise generic exception
    def bad_open(*args, **kwargs):
        raise RuntimeError("disk error")
    monkeypatch.setattr(builtins, 'open', bad_open)

    lock_file = tmp_path / "poller.lock"
    ok = lock.acquire_singleton_lock(str(lock_file))
    assert ok is False
