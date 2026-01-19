from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import app_config_store as store
from config import settings


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_dict(path: Path) -> Optional[dict[str, Any]]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _first_existing(paths: list[Path]) -> Optional[Path]:
    for p in paths:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None


def _write_config(key: str, payload: dict[str, Any], *, dry_run: bool, require_redis: bool) -> bool:
    if dry_run:
        return True

    if require_redis:
        try:
            return bool(store._redis_set_json(key, payload))  # type: ignore[attr-defined]
        except Exception:
            return False

    try:
        return bool(store.set_config_json(key, payload))
    except Exception:
        return False


def _read_back(key: str) -> Optional[dict[str, Any]]:
    try:
        data = store.get_config_json(key)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--require-redis", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Repeatable. One of: magic_link_tokens, polling_config, processing_prefs, webhook_config",
    )

    args = parser.parse_args(argv)

    allowed = {"magic_link_tokens", "polling_config", "processing_prefs", "webhook_config"}
    only = [v for v in (args.only or []) if v in allowed]
    if args.only and not only:
        print("No valid values provided for --only", file=sys.stderr)
        return 2

    debug_dir = Path(settings.DEBUG_DIR)

    targets: list[tuple[str, str, Optional[Path]]] = [
        (
            "magic_link_tokens",
            "magic_link_tokens",
            _first_existing(
                [
                    Path(settings.MAGIC_LINK_TOKENS_FILE),
                    debug_dir / "magic_link_tokens.json",
                    debug_dir / "magic_links.json",
                ]
            ),
        ),
        ("polling_config", "polling_config", Path(settings.POLLING_CONFIG_FILE)),
        ("processing_prefs", "processing_prefs", Path(settings.PROCESSING_PREFS_FILE)),
        ("webhook_config", "webhook_config", Path(settings.WEBHOOK_CONFIG_FILE)),
    ]

    selected = [t for t in targets if not only or t[0] in only]

    any_failed = False
    for label, key, source_path in selected:
        if source_path is None:
            print(f"{label}: source file not found; skip")
            continue

        payload = _load_json_dict(source_path)
        if payload is None:
            print(f"{label}: invalid or missing JSON at {source_path}; skip")
            continue

        if label != "magic_link_tokens" and "_updated_at" not in payload:
            payload["_updated_at"] = _utc_now_iso()

        ok = _write_config(key, payload, dry_run=args.dry_run, require_redis=args.require_redis)
        if not ok:
            any_failed = True

        msg = "DRY" if args.dry_run else ("OK" if ok else "FAILED")
        print(f"{label}: {msg} (source={source_path})")

        if args.verify and not args.dry_run and ok:
            read_back = _read_back(key)
            if not isinstance(read_back, dict):
                any_failed = True
                print(f"{label}: VERIFY FAILED (could not read back)")
            else:
                print(f"{label}: VERIFY OK")

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
