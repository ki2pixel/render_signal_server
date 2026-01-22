"""
E2E test proving polling configuration changes in Redis are reflected without restart.
Given/When/Then format per test strategy.
"""
import json
import time
from unittest.mock import patch, MagicMock
import pytest

from config import app_config_store
from config.polling_config import PollingConfigService


@pytest.mark.integration
def test_polling_config_dynamic_reload_without_restart():
    """
    Given: PollingConfigService reads from Redis/store dynamically
    When: Store is updated between two reads
    Then: Service returns updated values immediately without restart
    """
    # Given: a mock store returning initial config
    initial_cfg = {
        "active_days": [0, 1, 2],
        "active_start_hour": 8,
        "active_end_hour": 18,
        "enable_subject_group_dedup": False,
        "sender_of_interest_for_polling": ["old@example.com"],
        "vacation_start": None,
        "vacation_end": None,
        "enable_polling": True,
    }
    mock_store = MagicMock()
    mock_store.get_config_json.return_value = initial_cfg.copy()

    service = PollingConfigService(config_store=mock_store)

    # When: first read
    assert service.get_active_days() == [0, 1, 2]
    assert service.get_active_start_hour() == 8
    assert service.get_active_end_hour() == 18
    assert service.is_subject_group_dedup_enabled() is False
    assert service.get_sender_list() == ["old@example.com"]
    assert service.get_enable_polling(True) is True

    # When: store is updated
    updated_cfg = {
        "active_days": [3, 4, 5],
        "active_start_hour": 9,
        "active_end_hour": 19,
        "enable_subject_group_dedup": True,
        "sender_of_interest_for_polling": ["new@example.com", "another@example.com"],
        "vacation_start": "2025-12-01",
        "vacation_end": "2025-12-31",
        "enable_polling": False,
    }
    mock_store.get_config_json.return_value = updated_cfg.copy()

    # Then: subsequent reads reflect new values immediately
    assert service.get_active_days() == [3, 4, 5]
    assert service.get_active_start_hour() == 9
    assert service.get_active_end_hour() == 19
    assert service.is_subject_group_dedup_enabled() is True
    assert service.get_sender_list() == ["new@example.com", "another@example.com"]
    assert service.get_enable_polling(True) is False


@pytest.mark.integration
def test_polling_config_fallback_to_settings_when_store_empty():
    """
    Given: Store returns empty dict
    When: Service reads config
    Then: Defaults from settings are returned
    """
    # Given: empty store and patched settings
    from config import settings
    mock_store = MagicMock()
    mock_store.get_config_json.return_value = {}

    with patch.object(settings, 'POLLING_ACTIVE_DAYS', [1, 3, 5]), \
         patch.object(settings, 'POLLING_ACTIVE_START_HOUR', 7), \
         patch.object(settings, 'POLLING_ACTIVE_END_HOUR', 17), \
         patch.object(settings, 'ENABLE_SUBJECT_GROUP_DEDUP', True), \
         patch.object(settings, 'SENDER_LIST_FOR_POLLING', ["fallback@example.com"]):

        service = PollingConfigService(config_store=mock_store)

        # When: reading config
        # Then: settings defaults are used
        assert service.get_active_days() == [1, 3, 5]
        assert service.get_active_start_hour() == 7
        assert service.get_active_end_hour() == 17
        assert service.is_subject_group_dedup_enabled() is True
        assert service.get_sender_list() == ["fallback@example.com"]
        assert service.get_enable_polling(True) is True


@pytest.mark.integration
def test_polling_config_vacation_parsing_and_is_in_vacation():
    """
    Given: Store contains vacation dates
    When: Checking is_in_vacation for dates inside/outside range
    Then: Correct boolean returned
    """
    from datetime import date, datetime, timezone

    mock_store = MagicMock()
    mock_store.get_config_json.return_value = {
        "vacation_start": "2025-12-20",
        "vacation_end": "2025-12-31",
    }

    service = PollingConfigService(config_store=mock_store)

    # When: checking dates inside vacation
    inside = date(2025, 12, 25)
    assert service.is_in_vacation(inside) is True

    # When: checking dates outside vacation
    before = date(2025, 12, 19)
    after = date(2026, 1, 1)
    assert service.is_in_vacation(before) is False
    assert service.is_in_vacation(after) is False

    # When: checking datetime objects
    dt_inside = datetime(2025, 12, 25, 10, 30, tzinfo=timezone.utc)
    assert service.is_in_vacation(dt_inside) is True


@pytest.mark.integration
def test_polling_config_sender_list_normalization_and_dedup():
    """
    Given: Store contains malformed sender list
    When: Reading sender list
    Then: Normalized, deduped, valid emails returned
    """
    mock_store = MagicMock()
    mock_store.get_config_json.return_value = {
        "sender_of_interest_for_polling": [
            "VALID@EXAMPLE.COM",
            " valid@example.com ",
            "invalid-email",
            "another@example.com",
            "VALID@EXAMPLE.COM",  # duplicate
            "",
            "   ",
        ],
    }

    service = PollingConfigService(config_store=mock_store)

    # When: reading sender list
    senders = service.get_sender_list()

    # Then: normalized, deduped, valid emails only
    expected = ["valid@example.com", "another@example.com"]
    assert senders == expected


@pytest.mark.integration
def test_polling_config_enable_polling_string_parsing():
    """
    Given: Store contains enable_polling as various string types
    When: Reading enable_polling
    Then: Correct boolean parsing
    """
    mock_store = MagicMock()

    # Test truthy strings
    for truthy in ["1", "true", "yes", "y", "on"]:
        mock_store.get_config_json.return_value = {"enable_polling": truthy}
        service = PollingConfigService(config_store=mock_store)
        assert service.get_enable_polling(False) is True

    # Test falsy strings
    for falsy in ["0", "false", "no", "n", "off"]:
        mock_store.get_config_json.return_value = {"enable_polling": falsy}
        service = PollingConfigService(config_store=mock_store)
        assert service.get_enable_polling(True) is False

    # Test boolean types
    mock_store.get_config_json.return_value = {"enable_polling": True}
    service = PollingConfigService(config_store=mock_store)
    assert service.get_enable_polling(False) is True

    mock_store.get_config_json.return_value = {"enable_polling": False}
    service = PollingConfigService(config_store=mock_store)
    assert service.get_enable_polling(True) is False

    # Test missing key (fallback to default)
    mock_store.get_config_json.return_value = {}
    service = PollingConfigService(config_store=mock_store)
    assert service.get_enable_polling(True) is True
    assert service.get_enable_polling(False) is False
