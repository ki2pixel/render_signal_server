"""
Happy-path tests for routes/api_config.py to increase coverage on valid flows.
"""
import json
from unittest.mock import patch

import pytest


@pytest.mark.integration
def test_update_polling_config_happy_flow(authenticated_flask_client, tmp_path):
    # Patch config file path to temp
    from routes import api_config as api_cfg
    cfg_path = tmp_path / 'polling.json'
    with patch.object(api_cfg, 'POLLING_CONFIG_FILE', cfg_path):
        # Provide multiple fields with mixed formats
        payload = {
            "active_days": "0,1,1,2,6,9",  # includes duplicate and out-of-range -> 9 ignored
            "active_start_hour": 8,
            "active_end_hour": 19,
            "enable_subject_group_dedup": True,
            "sender_of_interest_for_polling": ["USER@EXAMPLE.COM", " user@example.com ", "bad"],
            "vacation_start": "2025-10-13",
            "vacation_end": "2025-10-15",
        }
        r = authenticated_flask_client.post('/api/update_polling_config', json=payload, content_type='application/json')
        assert r.status_code == 200
        data = r.get_json(); assert data["success"] is True
        conf = data["config"]
        assert conf["active_days"] == [0, 1, 2, 6]
        assert conf["active_start_hour"] == 8
        assert conf["active_end_hour"] == 19
        assert conf["enable_subject_group_dedup"] is True
        # emails normalized lower and deduped, invalid ignored
        assert conf["sender_of_interest_for_polling"] == ["user@example.com"]
        assert conf["vacation_start"] == "2025-10-13"
        assert conf["vacation_end"] == "2025-10-15"
        # file should be written
        saved = json.loads(cfg_path.read_text(encoding='utf-8'))
        assert saved["active_start_hour"] == 8


@pytest.mark.integration
def test_get_polling_config_reflects_runtime_vars(authenticated_flask_client, tmp_path):
    # Adjust runtime vars in settings via patch to make deterministic response
    from config import settings
    with patch.object(settings, 'POLLING_ACTIVE_DAYS', [1, 3, 5]), \
         patch.object(settings, 'POLLING_ACTIVE_START_HOUR', 7), \
         patch.object(settings, 'POLLING_ACTIVE_END_HOUR', 17), \
         patch.object(settings, 'ENABLE_SUBJECT_GROUP_DEDUP', False), \
         patch.object(settings, 'POLLING_TIMEZONE_STR', 'Europe/Paris'):
        # Ensure vacation dates None at module polling_config
        from config import polling_config
        polling_config.POLLING_VACATION_START_DATE = None
        polling_config.POLLING_VACATION_END_DATE = None
        r = authenticated_flask_client.get('/api/get_polling_config')
        assert r.status_code == 200
        data = r.get_json(); assert data["success"] is True
        cfg = data["config"]
        assert cfg["active_days"] == [1, 3, 5]
        assert cfg["active_start_hour"] == 7
        assert cfg["active_end_hour"] == 17
        assert cfg["enable_subject_group_dedup"] is False
        assert cfg["timezone"] == 'Europe/Paris'
        assert cfg["vacation_start"] is None and cfg["vacation_end"] is None


@pytest.mark.integration
def test_runtime_flags_get_defaults_when_file_missing(authenticated_flask_client, tmp_path):
    from routes import api_config as api_cfg
    # Point to non-existing path, should load defaults and succeed
    with patch.object(api_cfg, 'RUNTIME_FLAGS_FILE', tmp_path / 'flags.json'):
        r = authenticated_flask_client.get('/api/get_runtime_flags')
        assert r.status_code == 200
        flags = r.get_json()["flags"]
        assert "disable_email_id_dedup" in flags
        assert "allow_custom_webhook_without_links" in flags
