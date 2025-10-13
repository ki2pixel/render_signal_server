"""
Bounded-loop tests for background/polling_thread.py
"""
from datetime import timezone, datetime
from unittest.mock import MagicMock

import pytest

from background import polling_thread as pt


@pytest.mark.unit
def test_poller_inactive_sleep_once_and_exit(monkeypatch):
    logger = MagicMock()
    tz = timezone.utc

    # Configure as inactive window
    get_active_days = lambda: [0]  # Monday only
    get_start = lambda: 9
    get_end = lambda: 17

    # Monday 10:00? The loop uses now(), so patch datetime
    class FakeDT:
        @classmethod
        def now(cls, tzinfo=None):
            # Saturday
            return datetime(2025, 10, 11, 10, 0, tzinfo=tzinfo)
    monkeypatch.setattr(pt, "datetime", FakeDT)

    # Replace time.sleep to raise an error; with max_consecutive_errors=1 this will break the loop
    def fake_sleep(_seconds):
        raise RuntimeError("sleep-break")
    monkeypatch.setattr(pt, "time", type("T", (), {"sleep": staticmethod(fake_sleep)}))

    # Run: no exception should escape (loop catches), it should stop after logging critical
    pt.background_email_poller_loop(
        logger=logger,
        tz_for_polling=tz,
        get_active_days=get_active_days,
        get_active_start_hour=get_start,
        get_active_end_hour=get_end,
        inactive_sleep_seconds=1,
        active_sleep_seconds=1,
        is_in_vacation=lambda _dt: False,
        is_ready_to_poll=lambda: True,
        run_poll_cycle=lambda: 0,
        max_consecutive_errors=1,
    )

    # Should have logged outside active period
    logger.info.assert_any_call("BG_POLLER: Outside active period. Sleeping.")


@pytest.mark.unit
def test_poller_error_breaks_when_threshold_reached(monkeypatch):
    logger = MagicMock()
    tz = timezone.utc

    # Active window
    class FakeDT:
        @classmethod
        def now(cls, tzinfo=None):
            # Monday during active hours
            return datetime(2025, 10, 13, 10, 0, tzinfo=tzinfo)
    monkeypatch.setattr(pt, "datetime", FakeDT)

    # run_poll_cycle throws to simulate unhandled error inside try
    def faulty_cycle():
        raise RuntimeError("boom")

    # Patch time.sleep to no-op to avoid delays
    monkeypatch.setattr(pt, "time", type("T", (), {"sleep": staticmethod(lambda _s: None)}))

    # max_consecutive_errors=1 should break after first exception
    pt.background_email_poller_loop(
        logger=logger,
        tz_for_polling=tz,
        get_active_days=lambda: [0,1,2,3,4,5,6],
        get_active_start_hour=lambda: 0,
        get_active_end_hour=lambda: 23,
        inactive_sleep_seconds=0,
        active_sleep_seconds=0,
        is_in_vacation=lambda _dt: False,
        is_ready_to_poll=lambda: True,
        run_poll_cycle=faulty_cycle,
        max_consecutive_errors=1,
    )
    # Critical logged on stop
    logger.critical.assert_called_with("BG_POLLER: Max consecutive errors reached. Stopping thread.")


@pytest.mark.unit
def test_poller_is_ready_to_poll_false_path(monkeypatch):
    logger = MagicMock()
    tz = timezone.utc

    # Active window to enter the active branch
    class FakeDT:
        @classmethod
        def now(cls, tzinfo=None):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tzinfo)
    monkeypatch.setattr(pt, "datetime", FakeDT)

    # Make time.sleep raise to break loop after the branch executes
    monkeypatch.setattr(pt, "time", type("T", (), {"sleep": staticmethod(lambda _s: (_ for _ in ()).throw(RuntimeError("break")))}))

    ran = {"called": False}
    def never_run():
        ran["called"] = True
        return 0

    # Run with is_ready_to_poll=False; loop catches error from sleep and stops due to max errors=1
    pt.background_email_poller_loop(
        logger=logger,
        tz_for_polling=tz,
        get_active_days=lambda: [0,1,2,3,4,5,6],
        get_active_start_hour=lambda: 0,
        get_active_end_hour=lambda: 23,
        inactive_sleep_seconds=0,
        active_sleep_seconds=0,
        is_in_vacation=lambda _dt: False,
        is_ready_to_poll=lambda: False,
        run_poll_cycle=never_run,
        max_consecutive_errors=1,
    )

    # Assert warning was logged about incomplete config and that run_poll_cycle was never called
    logger.warning.assert_any_call("BG_POLLER: Essential config for polling is incomplete. Waiting 60s.")
    assert ran["called"] is False


@pytest.mark.unit
def test_poller_startup_info_log(monkeypatch):
    logger = MagicMock()
    tz = timezone.utc

    class FakeDT:
        @classmethod
        def now(cls, tzinfo=None):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tzinfo)
    monkeypatch.setattr(pt, "datetime", FakeDT)

    # Force immediate break via sleep
    monkeypatch.setattr(pt, "time", type("T", (), {"sleep": staticmethod(lambda _s: (_ for _ in ()).throw(RuntimeError("break")))}))

    try:
        pt.background_email_poller_loop(
            logger=logger,
            tz_for_polling=tz,
            get_active_days=lambda: [0,1,2,3,4,5,6],
            get_active_start_hour=lambda: 0,
            get_active_end_hour=lambda: 23,
            inactive_sleep_seconds=0,
            active_sleep_seconds=0,
            is_in_vacation=lambda _dt: True,  # will hit vacation branch then break
            is_ready_to_poll=lambda: True,
            run_poll_cycle=lambda: 0,
            max_consecutive_errors=1,
        )
    except Exception:
        pass

    logger.info.assert_any_call("BG_POLLER: Email polling loop started. TZ for schedule is configured.")


@pytest.mark.unit
def test_poller_vacation_true_path(monkeypatch):
    logger = MagicMock()
    tz = timezone.utc

    # Any date, ensure vacation returns True to hit that branch
    class FakeDT:
        @classmethod
        def now(cls, tzinfo=None):
            return datetime(2025, 10, 13, 10, 0, tzinfo=tzinfo)
    monkeypatch.setattr(pt, "datetime", FakeDT)

    # Make time.sleep raise to break after first call
    monkeypatch.setattr(pt, "time", type("T", (), {"sleep": staticmethod(lambda _s: (_ for _ in ()).throw(RuntimeError("break")))}))

    ran = {"called": False}
    def never_run():
        ran["called"] = True
        return 0

    # Run with vacation True; loop catches error from sleep and stops due to error threshold
    pt.background_email_poller_loop(
        logger=logger,
        tz_for_polling=tz,
        get_active_days=lambda: [0,1,2,3,4,5,6],
        get_active_start_hour=lambda: 0,
        get_active_end_hour=lambda: 23,
        inactive_sleep_seconds=0,
        active_sleep_seconds=0,
        is_in_vacation=lambda _dt: True,
        is_ready_to_poll=lambda: True,
        run_poll_cycle=never_run,
        max_consecutive_errors=1,
    )

    # Assert vacation log and no poll cycle execution
    logger.info.assert_any_call("BG_POLLER: Vacation window active. Polling suspended.")
    assert ran["called"] is False
