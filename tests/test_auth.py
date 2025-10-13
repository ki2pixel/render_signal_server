"""
Tests unitaires pour auth/ (user.py et helpers.py)
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from auth import user as auth_user
from auth import helpers as auth_helpers


class TestUser:
    """Tests pour la classe User"""
    
    @pytest.mark.unit
    def test_user_creation(self):
        """Test création d'un utilisateur"""
        user = auth_user.User("testuser")
        assert user.id == "testuser"
    
    @pytest.mark.unit
    def test_user_is_usermixin(self):
        """Test que User hérite de UserMixin"""
        from flask_login import UserMixin
        user = auth_user.User("testuser")
        assert isinstance(user, UserMixin)


class TestVerifyCredentials:
    """Tests pour verify_credentials()"""
    
    @pytest.mark.unit
    def test_verify_valid_credentials(self):
        """Test vérification avec credentials valides"""
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            with patch('auth.user.TRIGGER_PAGE_PASSWORD', 'secret123'):
                result = auth_user.verify_credentials('admin', 'secret123')
                assert result is True
    
    @pytest.mark.unit
    def test_verify_invalid_username(self):
        """Test vérification avec username invalide"""
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            with patch('auth.user.TRIGGER_PAGE_PASSWORD', 'secret123'):
                result = auth_user.verify_credentials('wronguser', 'secret123')
                assert result is False
    
    @pytest.mark.unit
    def test_verify_invalid_password(self):
        """Test vérification avec mot de passe invalide"""
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            with patch('auth.user.TRIGGER_PAGE_PASSWORD', 'secret123'):
                result = auth_user.verify_credentials('admin', 'wrongpass')
                assert result is False
    
    @pytest.mark.unit
    def test_verify_empty_credentials(self):
        """Test vérification avec credentials vides"""
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            with patch('auth.user.TRIGGER_PAGE_PASSWORD', 'secret123'):
                result = auth_user.verify_credentials('', '')
                assert result is False


class TestCreateUserFromCredentials:
    """Tests pour create_user_from_credentials()"""
    
    @pytest.mark.unit
    def test_create_user_valid_credentials(self):
        """Test création utilisateur avec credentials valides"""
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            with patch('auth.user.TRIGGER_PAGE_PASSWORD', 'secret123'):
                user = auth_user.create_user_from_credentials('admin', 'secret123')
                assert user is not None
                assert user.id == 'admin'
    
    @pytest.mark.unit
    def test_create_user_invalid_credentials(self):
        """Test création utilisateur avec credentials invalides"""
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            with patch('auth.user.TRIGGER_PAGE_PASSWORD', 'secret123'):
                user = auth_user.create_user_from_credentials('wrong', 'wrong')
                assert user is None


class TestInitLoginManager:
    """Tests pour init_login_manager()"""
    
    @pytest.mark.unit
    def test_init_login_manager(self):
        """Test initialisation de LoginManager"""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            manager = auth_user.init_login_manager(app)
            
            assert manager is not None
            assert manager.login_view == 'dashboard.login'
    
    @pytest.mark.unit
    def test_init_login_manager_custom_view(self):
        """Test initialisation avec vue de login personnalisée"""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        
        manager = auth_user.init_login_manager(app, login_view='custom.login')
        
        assert manager.login_view == 'custom.login'
    
    @pytest.mark.unit
    def test_user_loader_valid_user(self):
        """Test que user_loader charge correctement un utilisateur valide"""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            auth_user.init_login_manager(app)
            
            # Simuler le chargement d'un utilisateur
            with app.test_request_context():
                user = auth_user.login_manager.user_callback('admin')
                assert user is not None
                assert user.id == 'admin'
    
    @pytest.mark.unit
    def test_user_loader_invalid_user(self):
        """Test que user_loader retourne None pour un utilisateur invalide"""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        
        with patch('auth.user.TRIGGER_PAGE_USER', 'admin'):
            auth_user.init_login_manager(app)
            
            # Simuler le chargement d'un utilisateur invalide
            with app.test_request_context():
                user = auth_user.login_manager.user_callback('hacker')
                assert user is None


class TestTestAPIAuthorized:
    """Tests pour testapi_authorized()"""
    
    @pytest.mark.unit
    def test_authorized_with_valid_key(self):
        """Test autorisation avec clé API valide"""
        mock_req = Mock()
        mock_req.headers = {'X-API-Key': 'valid-key-123'}
        
        with patch.dict(os.environ, {'TEST_API_KEY': 'valid-key-123'}):
            result = auth_helpers.testapi_authorized(mock_req)
            assert result is True
    
    @pytest.mark.unit
    def test_unauthorized_with_invalid_key(self):
        """Test autorisation avec clé API invalide"""
        mock_req = Mock()
        mock_req.headers = {'X-API-Key': 'wrong-key'}
        
        with patch.dict(os.environ, {'TEST_API_KEY': 'valid-key-123'}):
            result = auth_helpers.testapi_authorized(mock_req)
            assert result is False
    
    @pytest.mark.unit
    def test_unauthorized_without_key(self):
        """Test autorisation sans clé API"""
        mock_req = Mock()
        mock_req.headers = {}
        
        with patch.dict(os.environ, {'TEST_API_KEY': 'valid-key-123'}):
            result = auth_helpers.testapi_authorized(mock_req)
            assert result is False
    
    @pytest.mark.unit
    def test_unauthorized_when_no_env_key(self):
        """Test autorisation quand TEST_API_KEY n'est pas définie"""
        mock_req = Mock()
        mock_req.headers = {'X-API-Key': 'some-key'}
        
        with patch.dict(os.environ, {}, clear=True):
            result = auth_helpers.testapi_authorized(mock_req)
            assert result is False


class TestAPIKeyRequiredDecorator:
    """Tests pour le décorateur api_key_required"""
    
    @pytest.mark.unit
    def test_decorator_allows_valid_request(self):
        """Test que le décorateur autorise une requête valide"""
        app = Flask(__name__)
        
        @app.route('/test')
        @auth_helpers.api_key_required
        def test_endpoint():
            return {'success': True}
        
        with app.test_request_context(
            '/test',
            headers={'X-API-Key': 'valid-key-123'}
        ):
            with patch.dict(os.environ, {'TEST_API_KEY': 'valid-key-123'}):
                from flask import request
                response = test_endpoint()
                assert response == {'success': True}
    
    @pytest.mark.unit
    def test_decorator_blocks_invalid_request(self):
        """Test que le décorateur bloque une requête invalide"""
        app = Flask(__name__)
        
        @app.route('/test')
        @auth_helpers.api_key_required
        def test_endpoint():
            return {'success': True}
        
        with app.test_request_context(
            '/test',
            headers={'X-API-Key': 'wrong-key'}
        ):
            with patch.dict(os.environ, {'TEST_API_KEY': 'valid-key-123'}):
                response, status = test_endpoint()
                assert status == 401
                assert 'error' in response.json
    
    @pytest.mark.unit
    def test_decorator_preserves_function_name(self):
        """Test que le décorateur préserve le nom de la fonction"""
        @auth_helpers.api_key_required
        def my_function():
            pass
        
        assert my_function.__name__ == 'my_function'
