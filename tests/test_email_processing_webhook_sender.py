"""
Tests for email_processing/webhook_sender.py
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from email_processing import webhook_sender as ws


@pytest.mark.unit
def test_send_makecom_webhook_retries_and_succeeds_on_second_try():
    with patch("email_processing.webhook_sender.requests.post") as mock_post:
        # First fails, second succeeds
        r_fail = Mock(); r_fail.status_code = 500; r_fail.text = "Server Error"
        r_ok = Mock(); r_ok.status_code = 200; r_ok.text = "OK"
        mock_post.side_effect = [r_fail, r_ok]

        log_hook = MagicMock()
        result = ws.send_makecom_webhook(
            subject="S",
            delivery_time="10h30",
            sender_email="a@b.c",
            email_id="id1",
            logger=MagicMock(),
            log_hook=log_hook,
            override_webhook_url="https://hook.eu2.make.com/abc"
        )
        assert result is True
        assert mock_post.call_count == 2
        # log_hook should have been called twice (one error, one success)
        assert log_hook.call_count == 2


@pytest.mark.unit
def test_send_makecom_webhook_no_url_returns_false():
    # Force empty URL by overriding settings in the module
    with patch.object(ws.settings, "RECADRAGE_MAKE_WEBHOOK_URL", None):
        ok = ws.send_makecom_webhook(
            subject="S",
            delivery_time=None,
            sender_email=None,
            email_id="id2",
            logger=MagicMock(),
        )
        assert ok is False
