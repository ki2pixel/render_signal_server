"""
Tests for config/webhook_config.py
"""
from pathlib import Path

import pytest

from config import webhook_config as wc


@pytest.mark.unit
def test_load_webhook_config_returns_empty_for_missing_or_invalid(tmp_path):
    p = tmp_path / "webhook_config.json"
    out = wc.load_webhook_config(p)
    assert out == {}

    # Invalid JSON should return {}
    p.write_text("invalid{" , encoding="utf-8")
    out2 = wc.load_webhook_config(p)
    assert out2 == {}


@pytest.mark.unit
def test_save_and_load_webhook_config_roundtrip(tmp_path):
    p = tmp_path / "webhook_config.json"
    data = {
        "webhook_url": "https://example.com/hook"
    }
    ok = wc.save_webhook_config(p, data)
    assert ok is True
    loaded = wc.load_webhook_config(p)
    assert loaded == data
