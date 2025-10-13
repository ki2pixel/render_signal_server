"""
Tests for config/webhook_time_window.py
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config import webhook_time_window as wtw


@pytest.mark.unit
def test_update_clear_and_get_info(tmp_path, monkeypatch):
    # Point the override file to a temp path to avoid touching real disk
    override = tmp_path / "webhook_time_window.json"
    monkeypatch.setattr(wtw, "TIME_WINDOW_OVERRIDE_FILE", override, raising=False)

    # Initialize with no constraints
    wtw.initialize_webhook_time_window("", "")
    ok, msg = wtw.update_time_window("", "")  # clear
    assert ok is True
    info = wtw.get_time_window_info()
    assert info["active"] is False
    assert info["start"] == ""
    assert info["end"] == ""

    # Set valid window
    ok2, msg2 = wtw.update_time_window("09h00", "17:30")
    assert ok2 is True
    info2 = wtw.get_time_window_info()
    assert info2["active"] is True
    assert info2["start"] == "09h00" or info2["start"] == "09:00"
    assert info2["end"].startswith("17")


@pytest.mark.unit
def test_reload_time_window_from_disk_and_check(tmp_path, monkeypatch):
    override = tmp_path / "webhook_time_window.json"
    monkeypatch.setattr(wtw, "TIME_WINDOW_OVERRIDE_FILE", override, raising=False)

    # Write an override simulating a previous UI change
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text('{"start": "09:00", "end": "17h00"}', encoding="utf-8")

    # Ensure module forgets previous values, then reload
    wtw.initialize_webhook_time_window("", "")
    assert wtw.WEBHOOKS_TIME_START is None and wtw.WEBHOOKS_TIME_END is None

    # check_within_time_window triggers reload and evaluation
    within = wtw.check_within_time_window(datetime(2025, 10, 13, 10, 0, tzinfo=timezone.utc))
    assert within is True
    outside = wtw.check_within_time_window(datetime(2025, 10, 13, 18, 0, tzinfo=timezone.utc))
    assert outside is False


@pytest.mark.unit
def test_update_time_window_validation(tmp_path, monkeypatch):
    override = tmp_path / "webhook_time_window.json"
    monkeypatch.setattr(wtw, "TIME_WINDOW_OVERRIDE_FILE", override, raising=False)

    # Missing one bound should fail
    ok, msg = wtw.update_time_window("09h00", "")
    assert ok is False and "Both" in msg

    # Invalid format should fail
    ok2, msg2 = wtw.update_time_window("invalid", "17h00")
    assert ok2 is False and "Invalid" in msg2
