"""CLI utilitaire pour vérifier les configurations stockées dans Redis.

Usage:
    python -m scripts.check_config_store --keys processing_prefs webhook_config
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable, Sequence, Tuple

from config import app_config_store

KEY_CHOICES: Tuple[str, ...] = (
    "magic_link_tokens",
    "polling_config",
    "processing_prefs",
    "webhook_config",
)


def _validate_payload(key: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload is not a dict"
    if not payload:
        return False, "payload is empty"
    if key != "magic_link_tokens" and "_updated_at" not in payload:
        return False, "missing _updated_at"
    return True, "ok"


def _summarize_dict(payload: Dict[str, Any]) -> str:
    parts: list[str] = []
    updated_at = payload.get("_updated_at")
    if isinstance(updated_at, str):
        parts.append(f"_updated_at={updated_at}")

    dict_sizes = {
        k: len(v) for k, v in payload.items() if isinstance(v, dict)
    }
    if dict_sizes:
        formatted = ", ".join(f"{k}:{size}" for k, size in sorted(dict_sizes.items()))
        parts.append(f"dict_sizes={formatted}")

    list_sizes = {
        k: len(v) for k, v in payload.items() if isinstance(v, list)
    }
    if list_sizes:
        formatted = ", ".join(f"{k}:{size}" for k, size in sorted(list_sizes.items()))
        parts.append(f"list_sizes={formatted}")

    if not parts:
        parts.append(f"keys={len(payload)}")
    return "; ".join(parts)


def _format_payload(payload: Dict[str, Any], raw: bool) -> str:
    if raw:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return _summarize_dict(payload)


def _fetch(key: str) -> Dict[str, Any]:
    return app_config_store.get_config_json(key)


def _run(keys: Sequence[str], raw: bool) -> int:
    exit_code = 0
    for key in keys:
        payload = _fetch(key)
        valid, reason = _validate_payload(key, payload)
        status = "OK" if valid else f"INVALID ({reason})"
        formatted = _format_payload(payload, raw) if payload else "<vide>"
        print(f"{key}: {status}")
        print(formatted)
        print("-" * 40)
        if not valid:
            exit_code = 1
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspecter les configs persistées dans Redis."
    )
    parser.add_argument(
        "--keys",
        nargs="+",
        choices=KEY_CHOICES,
        default=KEY_CHOICES,
        help="Liste des clés à vérifier.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Afficher le JSON complet (indent=2).",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return _run(tuple(args.keys), args.raw)


if __name__ == "__main__":
    sys.exit(main())
