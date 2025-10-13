"""
config.runtime_flags
~~~~~~~~~~~~~~~~~~~~~

Helper functions to load/save runtime flags from a JSON file with sane defaults.
Kept independent of Flask context for easy reuse in routes and app entrypoints.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_runtime_flags(file_path: Path, defaults: Dict[str, bool]) -> Dict[str, bool]:
    """Load runtime flags from JSON file, merging with provided defaults.

    Args:
        file_path: Path to JSON file storing flags
        defaults: Default values to apply when keys are missing or file absent
    Returns:
        dict of flags with all expected keys present
    """
    data: Dict[str, bool] = {}
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                raw = json.load(f) or {}
                if isinstance(raw, dict):
                    data.update(raw)
    except Exception:
        # On any error, fallback to empty so defaults are applied
        data = {}
    # Apply defaults for missing keys
    out = dict(defaults)
    out.update({k: bool(v) for k, v in data.items() if k in defaults})
    return out


def save_runtime_flags(file_path: Path, data: Dict[str, bool]) -> bool:
    """Persist runtime flags to JSON file.

    Args:
        file_path: Destination file
        data: Flags dict
    Returns:
        True on success, False otherwise
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
