"""
Tests for config/polling_config.py
"""
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from config import polling_config


@pytest.mark.unit
def test_initialize_polling_timezone_valid_paris(monkeypatch):
    logger = MagicMock()
    # Force a valid TZ string on the symbol used by polling_config
    monkeypatch.setattr(polling_config, "POLLING_TIMEZONE_STR", "Europe/Paris", raising=False)
    tz = polling_config.initialize_polling_timezone(logger)
    assert tz is not None
    # ZoneInfo may vary by platform; ensure not UTC when valid
    assert tz != timezone.utc


@pytest.mark.unit
def test_initialize_polling_timezone_invalid_falls_back_to_utc(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(polling_config, "POLLING_TIMEZONE_STR", "Invalid/Zone", raising=False)
    tz = polling_config.initialize_polling_timezone(logger)
    assert tz is not None
    # When invalid, fallback logged and UTC returned
    assert tz == timezone.utc


@pytest.mark.unit
def test_vacation_period_and_is_in_vacation(monkeypatch):
    logger = MagicMock()
    # Ensure TZ initialized for deterministic date handling
    monkeypatch.setattr(polling_config, "POLLING_TIMEZONE_STR", "UTC", raising=False)
    polling_config.initialize_polling_timezone(logger)

    start = date(2025, 10, 10)
    end = date(2025, 10, 12)
    polling_config.set_vacation_period(start, end, logger)

    assert polling_config.is_in_vacation_period(date(2025, 10, 9)) is False
    assert polling_config.is_in_vacation_period(date(2025, 10, 10)) is True
    assert polling_config.is_in_vacation_period(date(2025, 10, 11)) is True
    assert polling_config.is_in_vacation_period(date(2025, 10, 12)) is True
    assert polling_config.is_in_vacation_period(date(2025, 10, 13)) is False


@pytest.mark.unit
def test_is_polling_active_day_time_and_vacation(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr(polling_config, "POLLING_TIMEZONE_STR", "UTC", raising=False)
    tz = polling_config.initialize_polling_timezone(logger)

    # Monday 10:00 UTC
    monday_dt = datetime(2025, 10, 13, 10, 0, 0, tzinfo=tz)
    active_days = [0, 1, 2, 3, 4]  # Mon-Fri
    assert polling_config.is_polling_active(monday_dt, active_days, 9, 17) is True
    # Outside hour
    assert polling_config.is_polling_active(monday_dt.replace(hour=18), active_days, 9, 17) is False
    # Weekend day
    saturday_dt = datetime(2025, 10, 11, 10, 0, 0, tzinfo=tz)
    assert polling_config.is_polling_active(saturday_dt, active_days, 9, 17) is False

    # Enable vacation: should override to False even if within window
    polling_config.set_vacation_period(monday_dt.date(), monday_dt.date(), logger)
    assert polling_config.is_polling_active(monday_dt, active_days, 9, 17) is False
