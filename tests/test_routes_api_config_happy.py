"""
Happy-path tests for routes/api_config.py to increase coverage on valid flows.
"""
import os
import json
from unittest.mock import patch

import pytest


@pytest.mark.integration
def test_update_polling_config_happy_flow(authenticated_flask_client, tmp_path):
    # Given: a temp polling config file and a deterministic store path (file fallback)
    # Patch config file path to temp
    from routes import api_config as api_cfg
    cfg_path = tmp_path / 'polling.json'
    with patch.object(api_cfg, 'POLLING_CONFIG_FILE', cfg_path), patch.dict(
        os.environ,
        {
            "CONFIG_STORE_DISABLE_REDIS": "1",
            "EXTERNAL_CONFIG_BASE_URL": "",
            "CONFIG_API_TOKEN": "",
        },
        clear=False,
    ):
        # Provide multiple fields with mixed formats
        # When: we POST a valid mixed-format payload
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
        # Then: response is normalized and file fallback is written
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
def test_get_polling_config_defaults_to_settings_when_store_empty(authenticated_flask_client):
    # Given: store returns empty dict and settings are patched
    from routes import api_config as api_cfg
    from config import settings
    from config import polling_config
    import importlib
    import os

    # Force reload of polling_config to pick up patched settings
    importlib.reload(polling_config)
    
    with patch.object(api_cfg._store, 'get_config_json', return_value={}), patch.object(
        settings, 'POLLING_ACTIVE_DAYS', [1, 3, 5]
    ), patch.object(settings, 'POLLING_ACTIVE_START_HOUR', 7), patch.object(
        settings, 'POLLING_ACTIVE_END_HOUR', 17
    ), patch.object(settings, 'ENABLE_SUBJECT_GROUP_DEDUP', False), patch.object(
        settings, 'POLLING_TIMEZONE_STR', 'Europe/Paris'
    ), patch.object(settings, 'POLLING_ACTIVE_DAYS_RAW', '1,3,5'), patch.dict(
        os.environ, {'POLLING_ACTIVE_DAYS_RAW': '1,3,5'}, clear=True
    ):
        # Ensure vacation dates None at module polling_config (fallback path)
        polling_config.POLLING_VACATION_START_DATE = None
        polling_config.POLLING_VACATION_END_DATE = None

        # Force reload of api_config to pick up patched settings
        importlib.reload(api_cfg)

        # When: GET polling config
        r = authenticated_flask_client.get('/api/get_polling_config')
        # Then: API reflects settings defaults
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
def test_get_polling_config_prefers_store_values_over_settings(authenticated_flask_client):
    # Given: store has persisted values and settings differ
    from routes import api_config as api_cfg
    from config import settings

    persisted = {
        "active_days": [0, 2, 4],
        "active_start_hour": 9,
        "active_end_hour": 18,
        "enable_subject_group_dedup": True,
        "sender_of_interest_for_polling": ["user@example.com"],
        "vacation_start": None,
        "vacation_end": None,
        "enable_polling": False,
    }

    with patch.object(api_cfg._store, 'get_config_json', return_value=persisted), patch.object(
        settings, 'POLLING_ACTIVE_DAYS', [1, 3, 5]
    ), patch.object(settings, 'POLLING_ACTIVE_START_HOUR', 7), patch.object(
        settings, 'POLLING_ACTIVE_END_HOUR', 17
    ), patch.object(settings, 'ENABLE_SUBJECT_GROUP_DEDUP', False), patch.object(
        settings, 'POLLING_TIMEZONE_STR', 'Europe/Paris'
    ):
        # When: GET polling config
        r = authenticated_flask_client.get('/api/get_polling_config')

        # Then: API reflects store values (timezone remains from settings)
        assert r.status_code == 200
        data = r.get_json(); assert data["success"] is True
        cfg = data["config"]
        assert cfg["active_days"] == [0, 2, 4]
        assert cfg["active_start_hour"] == 9
        assert cfg["active_end_hour"] == 18
        assert cfg["enable_subject_group_dedup"] is True
        assert cfg["sender_of_interest_for_polling"] == ["user@example.com"]
        assert cfg["enable_polling"] is False
        assert cfg["timezone"] == 'Europe/Paris'


@pytest.mark.integration
def test_runtime_flags_get_defaults_when_file_missing(authenticated_flask_client, tmp_path):
    # Given: runtime flags file missing
    from routes import api_config as api_cfg
    # Point to non-existing path, should load defaults and succeed
    with patch.object(api_cfg, 'RUNTIME_FLAGS_FILE', tmp_path / 'flags.json'):
        # When: GET runtime flags
        r = authenticated_flask_client.get('/api/get_runtime_flags')
        # Then: defaults are present
        assert r.status_code == 200
        flags = r.get_json()["flags"]
        assert "disable_email_id_dedup" in flags
        assert "allow_custom_webhook_without_links" in flags
