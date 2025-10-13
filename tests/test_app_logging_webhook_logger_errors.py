"""
Error-path tests for app_logging/webhook_logger.py
"""
from datetime import datetime, timezone

import pytest

from app_logging import webhook_logger as wl


@pytest.mark.unit
def test_fetch_fallback_when_redis_read_error_and_unparsable_timestamp(temp_file, mock_logger):
    # Prepare file with one unparsable timestamp and one valid recent
    temp_file.write_text('[{"timestamp": "not-a-date", "email_id": "x"}, {"timestamp": "' + datetime.now(timezone.utc).isoformat() + '", "email_id": "y"}]', encoding='utf-8')

    class BadRedis:
        def lrange(self, *a, **k):
            raise RuntimeError("conn error")
    res = wl.fetch_webhook_logs(
        redis_client=BadRedis(),
        logger=mock_logger,
        file_path=temp_file,
        redis_list_key="r:ss:webhook_logs:v1",
        days=7,
        limit=10,
    )
    assert res["success"] is True
    # Both entries should be included; unparsable timestamp is kept per compatibility
    assert res["count"] == 2


@pytest.mark.unit
def test_append_redis_write_error_falls_back_to_file(temp_file, mock_logger):
    class BadRedis:
        def rpush(self, *a, **k):
            raise RuntimeError("write error")
        def ltrim(self, *a, **k):
            pass
    wl.append_webhook_log(
        {"timestamp": datetime.now(timezone.utc).isoformat(), "email_id": "z"},
        redis_client=BadRedis(),
        logger=mock_logger,
        file_path=temp_file,
        redis_list_key="r:ss:webhook_logs:v1",
        max_entries=5,
    )
    # Should have fallen back to file and written one entry
    content = temp_file.read_text(encoding='utf-8')
    assert '"email_id": "z"' in content
