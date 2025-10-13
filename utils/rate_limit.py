"""
utils.rate_limit
~~~~~~~~~~~~~~~~

Generic helpers for rate-limiting using a sliding one-hour window.
Designed to be injected with a deque instance by callers.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque


def prune_and_allow_send(event_queue: Deque[float], limit_per_hour: int, now: float | None = None) -> bool:
    """Return True if a new send is allowed given a per-hour limit.

    - event_queue: deque of timestamps (float epoch seconds) of past send attempts
    - limit_per_hour: 0 disables limiting; otherwise max events in last 3600s
    - now: override current time for testing
    """
    if limit_per_hour <= 0:
        return True
    t_now = now if now is not None else time.time()
    # prune events older than 1 hour
    while event_queue and (t_now - event_queue[0]) > 3600:
        event_queue.popleft()
    return len(event_queue) < limit_per_hour


def record_send_event(event_queue: Deque[float], ts: float | None = None) -> None:
    """Append a send event timestamp to the queue."""
    event_queue.append(ts if ts is not None else time.time())
