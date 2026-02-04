"""
Tests d'intégration pour les blueprints routes/
"""
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests pour /health"""
    
    def test_health_endpoint_returns_200(self, flask_client):
        """Test que /health retourne 200"""
        response = flask_client.get('/health')
        assert response.status_code == 200
    
    def test_health_endpoint_returns_json(self, flask_client):
        """Test que /health retourne du JSON"""
        response = flask_client.get('/health')
        data = response.get_json()
        assert data is not None
        assert 'status' in data


@pytest.mark.integration
class TestDashboardEndpoints:
    """Tests pour les endpoints du dashboard"""
    
    def test_dashboard_requires_auth(self, flask_client):
        """Test que le dashboard nécessite une authentification"""
        response = flask_client.get('/')
        # Devrait rediriger vers login ou retourner 401
        assert response.status_code in [302, 401]
    
    def test_login_page_accessible(self, flask_client):
        """Test que la page de login est accessible"""
        response = flask_client.get('/login')
        assert response.status_code == 200
    
    def test_dashboard_accessible_when_authenticated(self, authenticated_flask_client):
        """Test que le dashboard est accessible quand authentifié"""
        response = authenticated_flask_client.get('/')
        assert response.status_code == 200


@pytest.mark.integration
class TestWebhooksConfigEndpoints:
    """Tests pour les endpoints de configuration webhooks"""
    
    def test_get_webhooks_config_requires_auth(self, flask_client):
        """Test que GET /api/webhooks/config nécessite une authentification"""
        response = flask_client.get('/api/webhooks/config')
        assert response.status_code in [302, 401]
    
    def test_update_webhooks_config_requires_auth(self, flask_client):
        """Test que POST /api/webhooks/config nécessite une authentification"""
        response = flask_client.post(
            '/api/webhooks/config',
            json={'webhook_url': 'https://example.com/hook'}
        )
        assert response.status_code in [302, 401]
    
    def test_get_webhooks_config_when_authenticated(self, authenticated_flask_client, temp_file):
        """Test GET /api/webhooks/config quand authentifié"""
        with patch('routes.api_webhooks.WEBHOOK_CONFIG_FILE', temp_file):
            response = authenticated_flask_client.get('/api/webhooks/config')
            assert response.status_code == 200
            data = response.get_json()
            assert 'success' in data
            assert 'config' in data
    
    def test_update_webhooks_config_validation(self, authenticated_flask_client, temp_file):
        """Test validation lors de la mise à jour de la config webhooks"""
        with patch('routes.api_webhooks.WEBHOOK_CONFIG_FILE', temp_file):
            # URL invalide (non HTTPS)
            response = authenticated_flask_client.post(
                '/api/webhooks/config',
                json={'webhook_url': 'http://example.com/hook'},
                content_type='application/json'
            )
            assert response.status_code == 400
            
            # URL valide (HTTPS)
            response = authenticated_flask_client.post(
                '/api/webhooks/config',
                json={'webhook_url': 'https://example.com/hook'},
                content_type='application/json'
            )
            assert response.status_code == 200

@pytest.mark.integration
class TestProcessingPreferencesEndpoints:
    """Tests pour les endpoints de préférences de traitement"""
    
    def test_get_processing_prefs_requires_auth(self, flask_client):
        """Test que GET /api/processing_prefs nécessite une authentification"""
        response = flask_client.get('/api/processing_prefs')
        assert response.status_code in [302, 401]
    
    def test_update_processing_prefs_requires_auth(self, flask_client):
        """Test que POST /api/processing_prefs nécessite une authentification"""
        response = flask_client.post(
            '/api/processing_prefs',
            json={'exclude_keywords_recadrage': ['test']}
        )
        assert response.status_code in [302, 401]
    
    def test_get_processing_prefs_returns_defaults(self, authenticated_flask_client, temp_file):
        """Test que GET retourne des valeurs par défaut"""
        with patch('routes.api_processing.PROCESSING_PREFS_FILE', temp_file):
            response = authenticated_flask_client.get('/api/processing_prefs')
            assert response.status_code == 200
            data = response.get_json()
            assert 'success' in data
            assert 'prefs' in data
    
    def test_update_processing_prefs_validation(self, authenticated_flask_client, temp_file):
        """Test validation des préférences de traitement"""
        with patch('routes.api_processing.PROCESSING_PREFS_FILE', temp_file):
            # Valeurs valides
            response = authenticated_flask_client.post(
                '/api/processing_prefs',
                json={
                    'exclude_keywords_recadrage': ['spam', 'test'],
                    'exclude_keywords_autorepondeur': ['demo']
                },
                content_type='application/json'
            )
            assert response.status_code == 200
            
            # Valeur invalide (pas une liste)
            response = authenticated_flask_client.post(
                '/api/processing_prefs',
                json={'exclude_keywords_recadrage': 'not-a-list'},
                content_type='application/json'
            )
            assert response.status_code == 400


@pytest.mark.integration
class TestWebhookLogsEndpoints:
    """Tests pour les endpoints de logs webhooks"""
    
    def test_webhook_logs_requires_auth(self, flask_client):
        """Test que GET /api/webhook_logs nécessite une authentification"""
        response = flask_client.get('/api/webhook_logs')
        assert response.status_code in [302, 401]
    
    def test_webhook_logs_returns_empty_when_no_logs(self, authenticated_flask_client, temp_file):
        """Test retour de liste vide quand pas de logs"""
        # Supprimer le fichier s'il existe
        if temp_file.exists():
            temp_file.unlink()
        
        with patch('app_render.WEBHOOK_LOGS_FILE', temp_file):
            response = authenticated_flask_client.get('/api/webhook_logs')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['logs'] == []
            assert data['count'] == 0
    
    def test_webhook_logs_filters_by_days(self, authenticated_flask_client, temp_file):
        """Test filtrage des logs par nombre de jours"""
        from datetime import datetime, timezone, timedelta
        
        now = datetime.now(timezone.utc)
        logs = [
            {
                'timestamp': (now - timedelta(days=10)).isoformat(),
                'type': 'custom',
                'status': 'success'
            },
            {
                'timestamp': (now - timedelta(days=2)).isoformat(),
                'type': 'makecom',
                'status': 'success'
            }
        ]
        temp_file.write_text(json.dumps(logs))
        
        with patch('app_render.WEBHOOK_LOGS_FILE', temp_file):
            # Filtrer sur les 7 derniers jours
            response = authenticated_flask_client.get('/api/webhook_logs?days=7')
            assert response.status_code == 200
            data = response.get_json()
            # Seul le log de 2 jours devrait être inclus
            assert data['count'] == 1


@pytest.mark.integration
class TestAPIUtilityEndpoints:
    """Tests pour les endpoints utilitaires"""
    
    def test_ping_endpoint(self, flask_client):
        """Test que /api/ping retourne pong"""
        response = flask_client.get('/api/ping')
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data or 'pong' in str(data).lower()
