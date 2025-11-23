"""
Tests for the absence pause functionality.

Tests absence pause toggle and day-based blocking of webhook sending.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import json
from pathlib import Path


class TestAbsencePauseAPI:
    """Tests for absence pause API endpoints."""
    
    def test_get_webhook_config_includes_absence_fields(self, authenticated_flask_client):
        """Test that GET /api/webhooks/config returns absence fields."""
        response = authenticated_flask_client.get('/api/webhooks/config')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'absence_pause_enabled' in data['config']
        assert 'absence_pause_days' in data['config']
        assert isinstance(data['config']['absence_pause_days'], list)
    
    def test_update_absence_pause_enabled(self, authenticated_flask_client, temp_webhook_config):
        """Test updating absence_pause_enabled via API."""
        payload = {
            'absence_pause_enabled': True,
            'absence_pause_days': ['monday', 'friday']
        }
        response = authenticated_flask_client.post('/api/webhooks/config',
                              json=payload,
                              content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify saved
        response = authenticated_flask_client.get('/api/webhooks/config')
        data = response.get_json()
        assert data['config']['absence_pause_enabled'] is True
        assert 'monday' in data['config']['absence_pause_days']
        assert 'friday' in data['config']['absence_pause_days']
    
    def test_validate_absence_days_invalid(self, authenticated_flask_client):
        """Test that invalid day names are rejected."""
        payload = {
            'absence_pause_enabled': True,
            'absence_pause_days': ['monday', 'invalidday']
        }
        response = authenticated_flask_client.post('/api/webhooks/config',
                              json=payload,
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'invalides' in data['message'].lower()
    
    def test_validate_absence_enabled_without_days(self, authenticated_flask_client):
        """Test that enabling absence without selecting days is rejected."""
        payload = {
            'absence_pause_enabled': True,
            'absence_pause_days': []
        }
        response = authenticated_flask_client.post('/api/webhooks/config',
                              json=payload,
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'au moins un jour' in data['message'].lower()
    
    def test_normalize_day_names(self, authenticated_flask_client, temp_webhook_config):
        """Test that day names are normalized to lowercase."""
        payload = {
            'absence_pause_enabled': True,
            'absence_pause_days': ['Monday', 'FRIDAY', 'Wednesday']
        }
        response = authenticated_flask_client.post('/api/webhooks/config',
                              json=payload,
                              content_type='application/json')
        assert response.status_code == 200
        
        # Verify normalized
        response = authenticated_flask_client.get('/api/webhooks/config')
        data = response.get_json()
        days = data['config']['absence_pause_days']
        assert 'monday' in days
        assert 'friday' in days
        assert 'wednesday' in days
        # Ensure no uppercase
        assert 'Monday' not in days
        assert 'FRIDAY' not in days


class TestAbsencePauseService:
    """Tests for WebhookConfigService absence pause methods."""
    
    def test_get_absence_pause_enabled_default(self):
        """Test default value for absence_pause_enabled is False."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            assert service.get_absence_pause_enabled() is False
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_set_absence_pause_enabled(self):
        """Test setting absence_pause_enabled."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            assert service.set_absence_pause_enabled(True) is True
            assert service.get_absence_pause_enabled() is True
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_set_absence_pause_days(self):
        """Test setting absence_pause_days with validation."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            success, msg = service.set_absence_pause_days(['monday', 'wednesday'])
            assert success is True
            days = service.get_absence_pause_days()
            assert 'monday' in days
            assert 'wednesday' in days
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_set_absence_pause_days_invalid(self):
        """Test that invalid days are rejected."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            success, msg = service.set_absence_pause_days(['monday', 'badday'])
            assert success is False
            assert 'invalides' in msg.lower()
        finally:
            temp_path.unlink(missing_ok=True)


class TestAbsencePauseOrchestrator:
    """Tests for absence pause logic in orchestrator."""
    
    @patch('email_processing.orchestrator.datetime')
    def test_webhook_blocked_on_absence_day(self, mock_datetime):
        """Test that webhooks are blocked when absence pause is active for current day."""
        # Mock today as Monday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Monday'
        mock_datetime.now.return_value = mock_now
        
        # Mock config with absence pause for monday
        config_data = {
            'absence_pause_enabled': True,
            'absence_pause_days': ['monday', 'friday'],
            'webhook_sending_enabled': True
        }
        
        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            
            from email_processing.orchestrator import _is_webhook_sending_enabled
            
            # Should return False because today (Monday) is in pause days
            assert _is_webhook_sending_enabled() is False
    
    @patch('email_processing.orchestrator.datetime')
    def test_webhook_allowed_on_non_absence_day(self, mock_datetime):
        """Test that webhooks are allowed when current day is not in absence pause."""
        # Mock today as Tuesday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Tuesday'
        mock_datetime.now.return_value = mock_now
        
        # Mock config with absence pause for monday only
        config_data = {
            'absence_pause_enabled': True,
            'absence_pause_days': ['monday'],
            'webhook_sending_enabled': True
        }
        
        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            
            from email_processing.orchestrator import _is_webhook_sending_enabled
            
            # Should return True because today (Tuesday) is not in pause days
            assert _is_webhook_sending_enabled() is True

    @patch('email_processing.orchestrator.datetime')
    def test_webhook_blocked_with_case_and_spaces(self, mock_datetime):
        """Days with casing/whitespace are normalized and block sending."""
        # Mock today as Saturday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Saturday'
        mock_datetime.now.return_value = mock_now

        # Config returns mixed-case and spaced day names
        config_data = {
            'absence_pause_enabled': True,
            'absence_pause_days': [' Saturday ', 'FRIDAY'],
            'webhook_sending_enabled': True,
        }

        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            from email_processing.orchestrator import _is_webhook_sending_enabled
            # Should return False because 'Saturday' matches after normalization
            assert _is_webhook_sending_enabled() is False

    def test_cycle_guard_skips_when_absence_active(self, monkeypatch):
        """Integration guard: entire cycle exits early when absence is active today."""
        # Prepare a stub app_render with a minimal logger interface
        import types
        class _Logger:
            def info(self, *args, **kwargs):
                return None
            def error(self, *args, **kwargs):
                return None
        stub_ar = types.SimpleNamespace(app=types.SimpleNamespace(logger=_Logger()))

        # Ensure orchestrator will import our stub 'app_render'
        import sys
        sys.modules['app_render'] = stub_ar

        # Force _is_webhook_sending_enabled to return False (absence active)
        from email_processing import orchestrator as orch
        monkeypatch.setattr(orch, '_is_webhook_sending_enabled', lambda: False)

        # Run: should return 0 without attempting IMAP connection (early exit)
        assert orch.check_new_emails_and_trigger_webhook() == 0
    
    @patch('email_processing.orchestrator.datetime')
    def test_webhook_allowed_when_absence_disabled(self, mock_datetime):
        """Test that webhooks are allowed when absence pause is disabled."""
        # Mock today as Monday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Monday'
        mock_datetime.now.return_value = mock_now
        
        # Mock config with absence pause disabled
        config_data = {
            'absence_pause_enabled': False,
            'absence_pause_days': ['monday'],
            'webhook_sending_enabled': True
        }
        
        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            
            from email_processing.orchestrator import _is_webhook_sending_enabled
            
            # Should return True because absence pause is disabled
            assert _is_webhook_sending_enabled() is True


@pytest.fixture
def temp_webhook_config(tmp_path):
    """Create a temporary webhook config file."""
    config_file = tmp_path / "webhook_config.json"
    config_file.write_text(json.dumps({}))
    return config_file
