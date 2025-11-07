"""
background.polling_thread
~~~~~~~~~~~~~~~~~~~~~~~~~~

Polling thread loop extracted from app_render for Step 6.
The loop logic is pure and driven by injected dependencies to avoid cycles.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Iterable


def background_email_poller_loop(
    *,
    logger,
    tz_for_polling,
    get_active_days: Callable[[], Iterable[int]],
    get_active_start_hour: Callable[[], int],
    get_active_end_hour: Callable[[], int],
    inactive_sleep_seconds: int,
    active_sleep_seconds: int,
    is_in_vacation: Callable[[datetime], bool],
    is_ready_to_poll: Callable[[], bool],
    run_poll_cycle: Callable[[], int],
    max_consecutive_errors: int = 5,
) -> None:
    """Generic polling loop.

    Args:
        logger: Logger-like object with .info/.warning/.error/.critical
        tz_for_polling: timezone for scheduling (datetime.tzinfo)
        get_active_days: returns list of active weekday indices (0=Mon .. 6=Sun)
        get_active_start_hour: returns hour (0..23) start inclusive
        get_active_end_hour: returns hour (0..23) end exclusive
        inactive_sleep_seconds: sleep duration when outside active window
        active_sleep_seconds: base sleep duration after successful active cycle
        is_in_vacation: func(now_dt) -> bool to disable polling in vacation window
        is_ready_to_poll: func() -> bool to ensure config is valid before polling
        run_poll_cycle: func() -> int that executes a poll cycle and returns number of triggered actions
        max_consecutive_errors: circuit breaker to stop loop on repeated failures
    """
    logger.info(
        "BG_POLLER: Email polling loop started. TZ for schedule is configured."
    )
    consecutive_error_count = 0
    # Avoid spamming logs when schedule is not active; log diagnostic once
    outside_period_diag_logged = False

    while True:
        try:
            now_in_tz = datetime.now(tz_for_polling)

            # Vacation window check
            if is_in_vacation(now_in_tz):
                logger.info("BG_POLLER: Vacation window active. Polling suspended.")
                time.sleep(inactive_sleep_seconds)
                continue

            active_days = set(get_active_days())
            start_hour = get_active_start_hour()
            end_hour = get_active_end_hour()

            is_active_day = now_in_tz.weekday() in active_days
            # Support windows that cross midnight
            h = now_in_tz.hour
            if 0 <= start_hour <= 23 and 0 <= end_hour <= 23:
                if start_hour < end_hour:
                    is_active_time = (start_hour <= h < end_hour)
                elif start_hour > end_hour:
                    # Wrap-around (e.g., 23 -> 0 or 22 -> 6)
                    is_active_time = (h >= start_hour) or (h < end_hour)
                else:
                    # start == end => empty window
                    is_active_time = False
            else:
                is_active_time = False

            if is_active_day and is_active_time:
                logger.info("BG_POLLER: In active period. Starting poll cycle.")

                if not is_ready_to_poll():
                    logger.warning(
                        "BG_POLLER: Essential config for polling is incomplete. Waiting 60s."
                    )
                    time.sleep(60)
                    continue

                triggered = run_poll_cycle()
                logger.info(
                    f"BG_POLLER: Active poll cycle finished. {triggered} webhook(s) triggered."
                )
                # Update last poll cycle timestamp in main module if available
                try:
                    import sys, time as _t
                    _mod = sys.modules.get("app_render")
                    if _mod is not None:
                        setattr(_mod, "LAST_POLL_CYCLE_TS", int(_t.time()))
                except Exception:
                    pass
                consecutive_error_count = 0
                sleep_duration = active_sleep_seconds
            else:
                logger.info("BG_POLLER: Outside active period. Sleeping.")
                if not outside_period_diag_logged:
                    try:
                        logger.info(
                            "BG_POLLER: DIAG outside period — now=%s, active_days=%s, start_hour=%s, end_hour=%s, is_active_day=%s, is_active_time=%s",
                            now_in_tz.isoformat(),
                            sorted(list(active_days)),
                            start_hour,
                            end_hour,
                            is_active_day,
                            is_active_time,
                        )
                    except Exception:
                        pass
                    outside_period_diag_logged = True
                sleep_duration = inactive_sleep_seconds

            time.sleep(sleep_duration)

        except Exception as e:  # pragma: no cover - defensive
            consecutive_error_count += 1
            logger.error(
                f"BG_POLLER: Unhandled error in polling loop (Error #{consecutive_error_count}): {e}",
                exc_info=True,
            )
            if consecutive_error_count >= max_consecutive_errors:
                logger.critical(
                    "BG_POLLER: Max consecutive errors reached. Stopping thread."
                )
                break
