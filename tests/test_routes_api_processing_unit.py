"""
Unit tests focusing on internal validators and IO helpers in routes/api_processing.py
to raise coverage above the 70% target for routes/.
"""
import json
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_load_processing_prefs_missing_file(tmp_path):
    from routes import api_processing as mod

    with patch.object(mod, "PROCESSING_PREFS_FILE", tmp_path / "prefs.json"):
        # File does not exist -> defaults returned
        prefs = mod._load_processing_prefs()
        assert isinstance(prefs, dict)
        # default keys present
        assert "exclude_keywords" in prefs
        assert prefs["retry_delay_sec"] == 2


@pytest.mark.unit
def test_load_processing_prefs_malformed_json(tmp_path):
    from routes import api_processing as mod

    bad = tmp_path / "prefs.json"
    bad.write_text("{not-json}", encoding="utf-8")
    with patch.object(mod, "PROCESSING_PREFS_FILE", bad):
        prefs = mod._load_processing_prefs()
        # Malformed -> fall back to defaults
        assert prefs["retry_count"] == 0
        assert prefs["exclude_keywords"] == []


@pytest.mark.unit
def test_validate_processing_prefs_errors_and_success(tmp_path):
    from routes import api_processing as mod

    # Use isolated file so validator starts from defaults
    with patch.object(mod, "PROCESSING_PREFS_FILE", tmp_path / "prefs.json"):
        # Invalid: exclude_keywords_recadrage must be list[str]
        ok, msg, out = mod._validate_processing_prefs({"exclude_keywords_recadrage": "oops"})
        assert ok is False
        assert "liste" in msg.lower()

        # Invalid: sender_priority must be mapping with allowed levels
        ok, msg, out = mod._validate_processing_prefs({"sender_priority": ["bad"]})
        assert ok is False
        assert "objet" in msg.lower()

        # Invalid: retry_count out of bounds
        ok, msg, out = mod._validate_processing_prefs({"retry_count": 99})
        assert ok is False
        assert "hors limites" in msg.lower()

        # Happy-path with normalization and bounds
        payload = {
            "exclude_keywords": ["  spam  ", ""],
            "exclude_keywords_recadrage": ["  A  "],
            "exclude_keywords_autorepondeur": ["B"],
            "max_email_size_mb": 5,
            "sender_priority": {"User@Example.com": "High"},
            "retry_count": 1,
            "retry_delay_sec": 10,
            "webhook_timeout_sec": 60,
            "rate_limit_per_hour": 0,
            "notify_on_failure": True,
        }
        ok, msg, out = mod._validate_processing_prefs(payload)
        assert ok is True
        assert out["exclude_keywords"] == ["spam"]
        assert out["exclude_keywords_recadrage"] == ["A"]
        assert out["exclude_keywords_autorepondeur"] == ["B"]
        assert out["max_email_size_mb"] == 5
        assert out["sender_priority"] == {"user@example.com": "high"}
        assert out["retry_count"] == 1
        assert out["retry_delay_sec"] == 10
        assert out["webhook_timeout_sec"] == 60
        assert out["rate_limit_per_hour"] == 0
        assert out["notify_on_failure"] is True

        # Save should write a file
        assert mod._save_processing_prefs(out) is True
        saved = json.loads((tmp_path / "prefs.json").read_text(encoding="utf-8"))
        assert saved["retry_count"] == 1
