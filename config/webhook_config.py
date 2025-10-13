"""
config.webhook_config
~~~~~~~~~~~~~~~~~~~~~~

Helpers to load/save webhook configuration JSON with minimal validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


def load_webhook_config(file_path: Path) -> Dict[str, Any]:
    """Load persisted webhook configuration if available, else empty dict."""
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                cfg = json.load(f) or {}
                if isinstance(cfg, dict):
                    return cfg
    except Exception:
        pass
    return {}


def save_webhook_config(file_path: Path, cfg: Dict[str, Any]) -> bool:
    """Persist webhook configuration to JSON file."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False
