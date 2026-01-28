"""
Tests for webhook logs Redis persistence.

Ensures that:
1. Logs are stored in Redis list r:ss:webhook_logs:v1 when Redis is available
2. Logs survive app restarts (persistence)
3. Fallback to file works when Redis is unavailable
4. API returns logs from Redis first, then file fallback
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app_logging.webhook_logger import append_webhook_log, fetch_webhook_logs


@pytest.fixture
def mock_redis():
    """Mock Redis client with list operations."""
    client = MagicMock()
    client.rpush.return_value = 1
    client.ltrim.return_value = True
    client.lrange.return_value = []
    return client


@pytest.fixture
def sample_log_entry():
    """Sample webhook log entry."""
    return {
        "id": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "webhook_id": "test-webhook-123",
        "webhook_url": "https://example.com/webhook",
        "status_code": 200,
        "response": "OK",
        "duration_ms": 150,
    }


@pytest.fixture
def temp_log_file(tmp_path):
    """Temporary webhook logs file."""
    return tmp_path / "webhook_logs.json"


class TestWebhookLogsRedisPersistence:
    """Test webhook logs persistence with Redis."""

    def test_append_log_to_redis_success(self, mock_redis, sample_log_entry, temp_log_file):
        """Test that logs are appended to Redis list when Redis is available."""
        mock_logger = MagicMock()

        append_webhook_log(
            log_entry=sample_log_entry,
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            max_entries=500,
        )

        # Verify Redis operations were called
        mock_redis.rpush.assert_called_once_with(
            "r:ss:webhook_logs:v1", json.dumps(sample_log_entry, ensure_ascii=False)
        )
        mock_redis.ltrim.assert_called_once_with("r:ss:webhook_logs:v1", -500, -1)
        
        # Verify no file operations
        assert not temp_log_file.exists()

    def test_append_log_fallback_to_file_on_redis_error(self, sample_log_entry, temp_log_file):
        """Test that logs fall back to file when Redis fails."""
        mock_redis = MagicMock()
        mock_redis.rpush.side_effect = Exception("Redis connection failed")
        mock_logger = MagicMock()

        append_webhook_log(
            log_entry=sample_log_entry,
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            max_entries=500,
        )

        # Verify error was logged
        mock_logger.error.assert_called_once()
        
        # Verify file was created and contains the log
        assert temp_log_file.exists()
        with open(temp_log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
        assert len(logs) == 1
        assert logs[0]["id"] == sample_log_entry["id"]

    def test_fetch_logs_from_redis_success(self, mock_redis, sample_log_entry, temp_log_file):
        """Test that logs are fetched from Redis when available."""
        # Setup Redis mock to return our sample log
        mock_redis.lrange.return_value = [json.dumps(sample_log_entry, ensure_ascii=False)]
        mock_logger = MagicMock()

        result = fetch_webhook_logs(
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            days=7,
            limit=50,
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["days_filter"] == 7
        assert len(result["logs"]) == 1
        assert result["logs"][0]["id"] == sample_log_entry["id"]

        # Verify Redis was called
        mock_redis.lrange.assert_called_once_with("r:ss:webhook_logs:v1", 0, -1)

    def test_fetch_logs_fallback_to_file_on_redis_error(self, sample_log_entry, temp_log_file):
        """Test that logs fall back to file when Redis fails."""
        # Setup file with sample log
        temp_log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_log_file, "w", encoding="utf-8") as f:
            json.dump([sample_log_entry], f, indent=2, ensure_ascii=False)

        mock_redis = MagicMock()
        mock_redis.lrange.side_effect = Exception("Redis connection failed")
        mock_logger = MagicMock()

        result = fetch_webhook_logs(
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            days=7,
            limit=50,
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["logs"]) == 1
        assert result["logs"][0]["id"] == sample_log_entry["id"]

        # Verify error was logged
        mock_logger.error.assert_called_once()

    def test_fetch_logs_with_no_redis_client(self, sample_log_entry, temp_log_file):
        """Test that logs work when redis_client is None."""
        # Setup file with sample log
        temp_log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_log_file, "w", encoding="utf-8") as f:
            json.dump([sample_log_entry], f, indent=2, ensure_ascii=False)

        mock_logger = MagicMock()

        result = fetch_webhook_logs(
            redis_client=None,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            days=7,
            limit=50,
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["logs"]) == 1
        assert result["logs"][0]["id"] == sample_log_entry["id"]

    def test_fetch_logs_filter_by_days(self, mock_redis, temp_log_file):
        """Test that logs are filtered by days parameter."""
        # Create logs with different timestamps
        now = datetime.now(timezone.utc)
        old_log = {
            "id": 1,
            "timestamp": (now - timedelta(days=10)).isoformat(),
            "webhook_id": "old-webhook",
        }
        recent_log = {
            "id": 2,
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "webhook_id": "recent-webhook",
        }

        mock_redis.lrange.return_value = [
            json.dumps(old_log, ensure_ascii=False),
            json.dumps(recent_log, ensure_ascii=False),
        ]
        mock_logger = MagicMock()

        # Test with 7 days filter - should only return recent log
        result = fetch_webhook_logs(
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            days=7,
            limit=50,
        )

        assert result["success"] is True
        assert result["count"] == 1
        assert result["days_filter"] == 7
        assert len(result["logs"]) == 1
        assert result["logs"][0]["id"] == 2  # Only recent log

    def test_fetch_logs_limit_and_reverse_order(self, mock_redis, temp_log_file):
        """Test that logs are limited and returned in reverse order."""
        now = datetime.now(timezone.utc)
        logs = []
        for i in range(10):
            logs.append({
                "id": i + 1,
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
                "webhook_id": f"webhook-{i+1}",
            })

        mock_redis.lrange.return_value = [
            json.dumps(log, ensure_ascii=False) for log in logs
        ]
        mock_logger = MagicMock()

        result = fetch_webhook_logs(
            redis_client=mock_redis,
            logger=mock_logger,
            file_path=temp_log_file,
            redis_list_key="r:ss:webhook_logs:v1",
            days=7,
            limit=5,
        )

        assert result["success"] is True
        assert result["count"] == 5
        assert len(result["logs"]) == 5
        
        # Should be in reverse order (newest first) and limited to 5
        expected_ids = [10, 9, 8, 7, 6]  # Last 5 logs, reversed
        actual_ids = [log["id"] for log in result["logs"]]
        assert actual_ids == expected_ids


@pytest.mark.redis
class TestWebhookLogsIntegration:
    """Integration tests with real Redis (if available)."""

    @pytest.fixture(autouse=True)
    def setup_redis_check(self):
        """Skip these tests if Redis is not available."""
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL not set")
        
        try:
            import redis
            client = redis.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
        except Exception:
            pytest.skip("Redis not available")

    def test_real_redis_persistence(self, sample_log_entry, tmp_path):
        """Test with real Redis instance."""
        import redis
        
        redis_url = os.environ.get("REDIS_URL")
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        temp_file = tmp_path / "webhook_logs.json"
        mock_logger = MagicMock()
        
        redis_key = "test:r:ss:webhook_logs:v1"
        
        # Clean up any existing test data
        client.delete(redis_key)
        
        try:
            # Append log to Redis
            append_webhook_log(
                log_entry=sample_log_entry,
                redis_client=client,
                logger=mock_logger,
                file_path=temp_file,
                redis_list_key=redis_key,
                max_entries=500,
            )
            
            # Verify it's in Redis
            assert client.exists(redis_key)
            assert client.llen(redis_key) == 1
            
            # Fetch from Redis
            result = fetch_webhook_logs(
                redis_client=client,
                logger=mock_logger,
                file_path=temp_file,
                redis_list_key=redis_key,
                days=7,
                limit=50,
            )
            
            assert result["success"] is True
            assert result["count"] == 1
            assert len(result["logs"]) == 1
            assert result["logs"][0]["id"] == sample_log_entry["id"]
            
        finally:
            # Clean up test data
            client.delete(redis_key)
