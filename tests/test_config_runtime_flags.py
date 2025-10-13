"""
Tests for config/runtime_flags.py
"""
from pathlib import Path

import pytest

from config import runtime_flags as rf


@pytest.mark.unit
def test_load_runtime_flags_missing_file_returns_defaults(tmp_path):
    p = tmp_path / "flags.json"
    defaults = {"a": False, "b": True}
    out = rf.load_runtime_flags(p, defaults)
    assert out == defaults


@pytest.mark.unit
def test_load_runtime_flags_merges_defaults_and_file(tmp_path):
    p = tmp_path / "flags.json"
    p.write_text('{"a": true}', encoding="utf-8")
    defaults = {"a": False, "b": True}
    out = rf.load_runtime_flags(p, defaults)
    assert out["a"] is True  # from file
    assert out["b"] is True  # from defaults


@pytest.mark.unit
def test_save_runtime_flags_writes_json(tmp_path):
    p = tmp_path / "flags.json"
    data = {"x": True, "y": False}
    ok = rf.save_runtime_flags(p, data)
    assert ok is True
    # Roundtrip
    loaded = rf.load_runtime_flags(p, {"x": False, "y": False})
    assert loaded["x"] is True
    assert loaded["y"] is False
