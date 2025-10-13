"""
Tests for app_logging/webhook_logger.py
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from app_logging import webhook_logger as wl


@pytest.mark.unit
def test_append_and_fetch_with_redis(mock_redis, mock_logger):
    key = "r:ss:webhook_logs:v1"
    tmp = Path("/tmp/webhook_logs.json")  # won't be used because Redis provided

    # Append a few entries IN CHRONOLOGICAL ORDER (oldest -> newest)
    now = datetime.now(timezone.utc)
    for i in [2, 1, 0]:
        wl.append_webhook_log(
            {
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "type": "custom",
                "email_id": f"e{i}",
            },
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=tmp,
            redis_list_key=key,
            max_entries=10,
        )

    res = wl.fetch_webhook_logs(
        redis_client=mock_redis,
        logger=mock_logger,
        file_path=tmp,
        redis_list_key=key,
        days=7,
        limit=5,
    )
    assert res["success"] is True
    # Newest first, limited
    assert res["count"] == 3
    assert res["logs"][0]["email_id"] == "e0"


@pytest.mark.unit
def test_append_and_fetch_file_fallback(temp_file, mock_logger):
    key = "r:ss:webhook_logs:v1"

    # No redis provided -> file path is used
    wl.append_webhook_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "custom",
            "email_id": "e-file",
        },
        redis_client=None,
        logger=mock_logger,
        file_path=temp_file,
        redis_list_key=key,
        max_entries=2,
    )
    # Add one more to test trimming
    wl.append_webhook_log(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "custom",
            "email_id": "e-file-2",
        },
        redis_client=None,
        logger=mock_logger,
        file_path=temp_file,
        redis_list_key=key,
        max_entries=2,
    )

    res = wl.fetch_webhook_logs(
        redis_client=None,
        logger=mock_logger,
        file_path=temp_file,
        redis_list_key=key,
        days=7,
        limit=10,
    )
    assert res["success"] is True
    assert res["count"] == 2
    # newest first
    ids = [log["email_id"] for log in res["logs"]]
    assert ids[0] == "e-file-2"
