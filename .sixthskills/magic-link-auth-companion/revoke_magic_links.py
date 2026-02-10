#!/usr/bin/env python3
"""
Utility script to revoke magic links in bulk or individually.
Usage: python revoke_magic_links.py --all  # revoke all tokens
       python revoke_magic_links.py --token <uuid>  # revoke specific token
"""

import argparse
import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

from services.magic_link_service import MagicLinkService


def revoke_all(service: MagicLinkService) -> int:
    """Revoke all magic links."""
    try:
        service.revoke_all_tokens()
        print("[info] All magic links revoked.")
        return 0
    except Exception as exc:
        print(f"[error] Failed to revoke all tokens: {exc}")
        return 1


def revoke_token(service: MagicLinkService, token_uuid: str) -> int:
    """Revoke a specific token."""
    try:
        if service.revoke_token(token_uuid):
            print(f"[info] Token {token_uuid} revoked.")
            return 0
        else:
            print(f"[warn] Token {token_uuid} not found.")
            return 1
    except Exception as exc:
        print(f"[error] Failed to revoke token {token_uuid}: {exc}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Revoke magic links")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Revoke all tokens")
    group.add_argument("--token", help="Revoke specific token UUID")
    
    args = parser.parse_args()
    
    service = MagicLinkService.get_instance()
    
    if args.all:
        return revoke_all(service)
    elif args.token:
        return revoke_token(service, args.token)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
