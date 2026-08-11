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
        "webhook_url": "https://webhook.kidpixel.fr/index.php"
    }
    ok = wc.save_webhook_config(p, data)
    assert ok is True
    loaded = wc.load_webhook_config(p)
    # _updated_at est injecté automatiquement à la sauvegarde
    assert loaded["webhook_url"] == data["webhook_url"]
    assert isinstance(loaded.get("_updated_at"), str)
    assert loaded["_updated_at"]


@pytest.mark.unit
def test_save_webhook_config_preserves_existing_updated_at(tmp_path):
    p = tmp_path / "webhook_config.json"
    data = {
        "webhook_url": "https://webhook.kidpixel.fr/index.php",
        "_updated_at": "2026-01-01T00:00:00Z",
    }
    ok = wc.save_webhook_config(p, data)
    assert ok is True
    loaded = wc.load_webhook_config(p)
    # La valeur existante n'est pas écrasée
    assert loaded["_updated_at"] == "2026-01-01T00:00:00Z"
