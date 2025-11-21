"""
Tests for the presence pause functionality.

Tests presence pause toggle and day-based blocking of webhook sending.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import json
from pathlib import Path


class TestPresencePauseAPI:
    """Tests for presence pause API endpoints."""
    
    def test_get_webhook_config_includes_presence_fields(self, authenticated_flask_client):
        """Test that GET /api/webhooks/config returns presence fields."""
        response = authenticated_flask_client.get('/api/webhooks/config')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'presence_pause_enabled' in data['config']
        assert 'presence_pause_days' in data['config']
        assert isinstance(data['config']['presence_pause_days'], list)
    
    def test_update_presence_pause_enabled(self, authenticated_flask_client, temp_webhook_config):
        """Test updating presence_pause_enabled via API."""
        payload = {
            'presence_pause_enabled': True,
            'presence_pause_days': ['monday', 'friday']
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
        assert data['config']['presence_pause_enabled'] is True
        assert 'monday' in data['config']['presence_pause_days']
        assert 'friday' in data['config']['presence_pause_days']
    
    def test_validate_presence_days_invalid(self, authenticated_flask_client):
        """Test that invalid day names are rejected."""
        payload = {
            'presence_pause_enabled': True,
            'presence_pause_days': ['monday', 'invalidday']
        }
        response = authenticated_flask_client.post('/api/webhooks/config',
                              json=payload,
                              content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'invalides' in data['message'].lower()
    
    def test_validate_presence_enabled_without_days(self, authenticated_flask_client):
        """Test that enabling presence without selecting days is rejected."""
        payload = {
            'presence_pause_enabled': True,
            'presence_pause_days': []
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
            'presence_pause_enabled': True,
            'presence_pause_days': ['Monday', 'FRIDAY', 'Wednesday']
        }
        response = authenticated_flask_client.post('/api/webhooks/config',
                              json=payload,
                              content_type='application/json')
        assert response.status_code == 200
        
        # Verify normalized
        response = authenticated_flask_client.get('/api/webhooks/config')
        data = response.get_json()
        days = data['config']['presence_pause_days']
        assert 'monday' in days
        assert 'friday' in days
        assert 'wednesday' in days
        # Ensure no uppercase
        assert 'Monday' not in days
        assert 'FRIDAY' not in days


class TestPresencePauseService:
    """Tests for WebhookConfigService presence pause methods."""
    
    def test_get_presence_pause_enabled_default(self):
        """Test default value for presence_pause_enabled is False."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            assert service.get_presence_pause_enabled() is False
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_set_presence_pause_enabled(self):
        """Test setting presence_pause_enabled."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            assert service.set_presence_pause_enabled(True) is True
            assert service.get_presence_pause_enabled() is True
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_set_presence_pause_days(self):
        """Test setting presence_pause_days with validation."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            success, msg = service.set_presence_pause_days(['monday', 'wednesday'])
            assert success is True
            days = service.get_presence_pause_days()
            assert 'monday' in days
            assert 'wednesday' in days
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_set_presence_pause_days_invalid(self):
        """Test that invalid days are rejected."""
        from services.webhook_config_service import WebhookConfigService
        from pathlib import Path
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            temp_path = Path(f.name)
        
        try:
            service = WebhookConfigService(temp_path)
            success, msg = service.set_presence_pause_days(['monday', 'badday'])
            assert success is False
            assert 'invalides' in msg.lower()
        finally:
            temp_path.unlink(missing_ok=True)


class TestPresencePauseOrchestrator:
    """Tests for presence pause logic in orchestrator."""
    
    @patch('email_processing.orchestrator.datetime')
    def test_webhook_blocked_on_presence_day(self, mock_datetime):
        """Test that webhooks are blocked when presence pause is active for current day."""
        # Mock today as Monday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Monday'
        mock_datetime.now.return_value = mock_now
        
        # Mock config with presence pause for monday
        config_data = {
            'presence_pause_enabled': True,
            'presence_pause_days': ['monday', 'friday'],
            'webhook_sending_enabled': True
        }
        
        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            
            from email_processing.orchestrator import _is_webhook_sending_enabled
            
            # Should return False because today (Monday) is in pause days
            assert _is_webhook_sending_enabled() is False
    
    @patch('email_processing.orchestrator.datetime')
    def test_webhook_allowed_on_non_presence_day(self, mock_datetime):
        """Test that webhooks are allowed when current day is not in presence pause."""
        # Mock today as Tuesday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Tuesday'
        mock_datetime.now.return_value = mock_now
        
        # Mock config with presence pause for monday only
        config_data = {
            'presence_pause_enabled': True,
            'presence_pause_days': ['monday'],
            'webhook_sending_enabled': True
        }
        
        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            
            from email_processing.orchestrator import _is_webhook_sending_enabled
            
            # Should return True because today (Tuesday) is not in pause days
            assert _is_webhook_sending_enabled() is True
    
    @patch('email_processing.orchestrator.datetime')
    def test_webhook_allowed_when_presence_disabled(self, mock_datetime):
        """Test that webhooks are allowed when presence pause is disabled."""
        # Mock today as Monday
        mock_now = MagicMock()
        mock_now.astimezone.return_value.strftime.return_value = 'Monday'
        mock_datetime.now.return_value = mock_now
        
        # Mock config with presence pause disabled
        config_data = {
            'presence_pause_enabled': False,
            'presence_pause_days': ['monday'],
            'webhook_sending_enabled': True
        }
        
        with patch('email_processing.orchestrator.Path') as mock_path, \
             patch('config.app_config_store.get_config_json', return_value=config_data):
            
            from email_processing.orchestrator import _is_webhook_sending_enabled
            
            # Should return True because presence pause is disabled
            assert _is_webhook_sending_enabled() is True


@pytest.fixture
def temp_webhook_config(tmp_path):
    """Create a temporary webhook config file."""
    config_file = tmp_path / "webhook_config.json"
    config_file.write_text(json.dumps({}))
    return config_file
