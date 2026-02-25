"""
Deduplication helpers using Redis with safe fallbacks.

This module centralizes per-email and per-subject-group dedup logic.
Functions are side-effect free besides interacting with Redis.

Design choices:
- Keep functions generic and injectable: take redis_client and logger as parameters.
- Subject-group scoping by month is handled here when enable_monthly_scope is True.
- Provide graceful fallbacks when redis_client is None or raises errors.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def is_email_id_processed(
    redis_client,
    email_id: str,
    logger,
    processed_ids_key: str,
) -> bool:
    if not email_id:
        return False
    if redis_client is None:
        return False
    try:
        return bool(redis_client.sismember(processed_ids_key, email_id))
    except Exception as e:
        if logger:
            logger.error(f"REDIS_DEDUP: Error checking email ID '{email_id}': {e}. Assuming NOT processed.")
        return False

def mark_email_id_processed(
    redis_client,
    email_id: str,
    logger,
    processed_ids_key: str,
) -> bool:
    if not email_id or redis_client is None:
        return False
    try:
        redis_client.sadd(processed_ids_key, email_id)
        return True
    except Exception as e:
        if logger:
            logger.error(f"REDIS_DEDUP: Error adding email ID '{email_id}': {e}")
        return False


def acquire_email_inflight_lock(
    redis_client,
    email_id: str,
    logger,
    lock_key_prefix: str,
    ttl_seconds: int,
) -> bool:
    """Acquire an in-flight lock for a given email_id.

    Returns:
        bool:
            - True  => lock acquired OR lock system unavailable (fail-open)
            - False => lock already held by another in-flight processing

    Design:
    - Redis SET key value NX EX for atomic acquisition.
    - Fail-open if Redis isn't configured or errors occur (avoid dropping emails).
    """
    if not email_id:
        return True
    if redis_client is None:
        return True

    prefix = lock_key_prefix or ""
    key = f"{prefix}{email_id}"
    try:
        ttl = int(ttl_seconds) if ttl_seconds is not None else 0
    except Exception:
        ttl = 0
    if ttl <= 0:
        ttl = 900

    try:
        acquired = bool(redis_client.set(key, "1", nx=True, ex=ttl))
        if not acquired:
            try:
                logger.info("DEDUP_INFLIGHT: Skipping already in-flight email_id=%s", email_id)
            except Exception:
                pass
        return acquired
    except Exception as e:
        try:
            logger.warning(
                "REDIS_DEDUP: Failed to acquire in-flight lock for email_id=%s: %s (fail-open)",
                email_id,
                e,
            )
        except Exception:
            pass
        return True


def release_email_inflight_lock(
    redis_client,
    email_id: str,
    logger,
    lock_key_prefix: str,
) -> bool:
    """Release an in-flight lock for email_id (best-effort)."""
    if not email_id:
        return True
    if redis_client is None:
        return True

    prefix = lock_key_prefix or ""
    key = f"{prefix}{email_id}"
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        try:
            logger.warning(
                "REDIS_DEDUP: Failed to release in-flight lock for email_id=%s: %s",
                email_id,
                e,
            )
        except Exception:
            pass
        return False


def _monthly_scope_group_id(group_id: str, tz) -> str:
    try:
        now_local = datetime.now(tz) if tz else datetime.now()
    except Exception:
        now_local = datetime.now()
    month_prefix = now_local.strftime("%Y-%m")
    return f"{month_prefix}:{group_id}"


def is_subject_group_processed(
    redis_client,
    group_id: str,
    logger,
    ttl_seconds: int,
    ttl_prefix: str,
    groups_key: str,
    enable_monthly_scope: bool,
    tz,
    memory_set: Optional[set] = None,
) -> bool:
    if not group_id:
        return False
    scoped_id = _monthly_scope_group_id(group_id, tz) if enable_monthly_scope else group_id
    if redis_client is not None:
        try:
            if ttl_seconds and ttl_seconds > 0:
                ttl_key = ttl_prefix + scoped_id
                val = redis_client.get(ttl_key)
                if val is not None:
                    return True
            return bool(redis_client.sismember(groups_key, scoped_id))
        except Exception as e:
            if logger:
                logger.error(
                    f"REDIS_DEDUP: Error checking subject group '{group_id}': {e}. Assuming NOT processed."
                )
            # Continue to memory fallback instead of returning False here

    if memory_set is not None:
        return scoped_id in memory_set
    return False


def mark_subject_group_processed(
    redis_client,
    group_id: str,
    logger,
    ttl_seconds: int,
    ttl_prefix: str,
    groups_key: str,
    enable_monthly_scope: bool,
    tz,
    memory_set: Optional[set] = None,
) -> bool:
    if not group_id:
        return False
    scoped_id = _monthly_scope_group_id(group_id, tz) if enable_monthly_scope else group_id
    if redis_client is not None:
        try:
            if ttl_seconds and ttl_seconds > 0:
                ttl_key = ttl_prefix + scoped_id
                # value content is irrelevant; only presence matters
                redis_client.set(ttl_key, 1, ex=ttl_seconds)
            redis_client.sadd(groups_key, scoped_id)
            return True
        except Exception as e:
            if logger:
                logger.error(f"REDIS_DEDUP: Error marking subject group '{group_id}': {e}")
            # Continue to memory fallback instead of returning False here
    
    if memory_set is not None:
        try:
            memory_set.add(scoped_id)
            return True
        except Exception:
            return False
    return False
