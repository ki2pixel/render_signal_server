"""
services.auth_service
~~~~~~~~~~~~~~~~~~~~~

Service centralisé pour toute l'authentification (dashboard + API).

Combine:
- Authentification dashboard (username/password via Flask-Login)
- Authentification API (X-API-Key pour Make.com)
- Authentification endpoints de test (X-API-Key pour CORS)
- Gestion du LoginManager Flask-Login

Usage:
    from services import AuthService, ConfigService
    
    config = ConfigService()
    auth = AuthService(config)
    
    auth.init_flask_login(app)
    
    if auth.verify_dashboard_credentials(username, password):
        user = auth.create_user(username)
        login_user(user)
    
    # Décorateur API
    @auth.api_key_required
    def my_endpoint():
        ...
"""

from __future__ import annotations

from functools import wraps
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask, Request
    from flask_login import LoginManager
    from services.config_service import ConfigService

from flask_login import UserMixin


class User(UserMixin):
    """Classe utilisateur simple pour Flask-Login.
    
    Attributes:
        id: Identifiant de l'utilisateur (username)
    """
    
    def __init__(self, username: str):
        """Initialise un utilisateur.
        
        Args:
            username: Nom d'utilisateur
        """
        self.id = username
    
    def __repr__(self) -> str:
        return f"<User(id={self.id})>"


class AuthService:
    """Service centralisé pour l'authentification.
    
    Attributes:
        _config: Instance de ConfigService
        _login_manager: Instance de Flask-Login LoginManager
    """
    
    def __init__(self, config_service):
        """Initialise le service d'authentification.
        
        Args:
            config_service: Instance de ConfigService pour accès aux credentials
        """
        self._config = config_service
        self._login_manager: Optional[LoginManager] = None
    
    # =========================================================================
    # Authentification Dashboard (Flask-Login)
    # =========================================================================
    
    def verify_dashboard_credentials(self, username: str, password: str) -> bool:
        """Vérifie les credentials du dashboard.
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            True si credentials valides
        """
        return self._config.verify_dashboard_credentials(username, password)
    
    def create_user(self, username: str) -> User:
        """Crée une instance User pour Flask-Login.
        
        Args:
            username: Nom d'utilisateur
            
        Returns:
            Instance User
        """
        return User(username)
    
    def create_user_from_credentials(self, username: str, password: str) -> Optional[User]:
        """Crée un User si les credentials sont valides.
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            Instance User si valide, None sinon
        """
        if self.verify_dashboard_credentials(username, password):
            return User(username)
        return None
    
    def load_user(self, user_id: str) -> Optional[User]:
        """User loader pour Flask-Login.
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            Instance User si l'ID correspond à l'utilisateur configuré
        """
        expected_user = self._config.get_dashboard_user()
        if user_id == expected_user:
            return User(user_id)
        return None
    
    # =========================================================================
    # Authentification API (Make.com endpoints)
    # =========================================================================
    
    def verify_api_token(self, token: str) -> bool:
        """Vérifie un token API pour les endpoints Make.com.
        
        Args:
            token: Token à vérifier
            
        Returns:
            True si le token est valide
        """
        return self._config.verify_api_token(token)
    
    def verify_api_key_from_request(self, request: Request) -> bool:
        """Vérifie la clé API depuis les headers d'une requête Flask.
        
        Args:
            request: Objet Flask request
            
        Returns:
            True si le token dans Authorization header est valide
        """
        # Récupérer le token depuis le header Authorization
        auth_header = request.headers.get("Authorization", "")
        
        # Format attendu: "Bearer <token>" ou juste "<token>"
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header
        
        return self.verify_api_token(token)
    
    # =========================================================================
    # Authentification Test Endpoints (CORS)
    # =========================================================================
    
    def verify_test_api_key(self, key: str) -> bool:
        """Vérifie une clé API pour les endpoints de test.
        
        Args:
            key: Clé à vérifier
            
        Returns:
            True si valide
        """
        return self._config.verify_test_api_key(key)
    
    def verify_test_api_key_from_request(self, request: Request) -> bool:
        """Vérifie la clé API de test depuis une requête.
        
        Args:
            request: Objet Flask request
            
        Returns:
            True si X-API-Key header est valide
        """
        key = request.headers.get("X-API-Key", "")
        return self.verify_test_api_key(key)
    
    # =========================================================================
    # Flask-Login Integration
    # =========================================================================
    
    def init_flask_login(self, app: Flask, login_view: str = 'dashboard.login') -> LoginManager:
        """Initialise Flask-Login pour l'application.
        
        Args:
            app: Instance Flask
            login_view: Nom de la vue de login pour redirections
            
        Returns:
            Instance LoginManager configurée
        """
        from flask_login import LoginManager
        
        self._login_manager = LoginManager()
        self._login_manager.init_app(app)
        self._login_manager.login_view = login_view
        
        # Enregistrer le user_loader
        @self._login_manager.user_loader
        def _user_loader(user_id: str):
            return self.load_user(user_id)
        
        return self._login_manager
    
    def get_login_manager(self) -> Optional[LoginManager]:
        """Retourne le LoginManager configuré.
        
        Returns:
            Instance LoginManager ou None si pas initialisé
        """
        return self._login_manager
    
    # =========================================================================
    # Décorateurs
    # =========================================================================
    
    def api_key_required(self, func):
        """Décorateur pour protéger un endpoint avec authentification API token.
        
        Usage:
            @app.route('/api/protected')
            @auth_service.api_key_required
            def protected_endpoint():
                return {"status": "ok"}
        
        Args:
            func: Fonction à protéger
            
        Returns:
            Wrapper qui vérifie l'authentification
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            if not self.verify_api_key_from_request(request):
                return jsonify({"error": "Unauthorized. Valid API token required."}), 401
            
            return func(*args, **kwargs)
        
        return wrapper
    
    def test_api_key_required(self, func):
        """Décorateur pour protéger un endpoint de test avec X-API-Key.
        
        Usage:
            @app.route('/api/test/endpoint')
            @auth_service.test_api_key_required
            def test_endpoint():
                return {"status": "ok"}
        
        Args:
            func: Fonction à protéger
            
        Returns:
            Wrapper qui vérifie l'authentification
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            if not self.verify_test_api_key_from_request(request):
                return jsonify({"error": "Unauthorized. Valid X-API-Key required."}), 401
            
            return func(*args, **kwargs)
        
        return wrapper
    
    # =========================================================================
    # Fonctions Statiques (Compatibilité)
    # =========================================================================
    
    @staticmethod
    def testapi_authorized(request: Request) -> bool:
        """Fonction de compatibilité pour auth.helpers.testapi_authorized.
        
        ⚠️ Déprécié - Utiliser verify_test_api_key_from_request() à la place.
        
        Args:
            request: Objet Flask request
            
        Returns:
            True si X-API-Key est valide
        """
        import os
        expected = os.environ.get("TEST_API_KEY")
        if not expected:
            return False
        return request.headers.get("X-API-Key") == expected
    
    def __repr__(self) -> str:
        """Représentation du service."""
        login_mgr = "initialized" if self._login_manager else "not initialized"
        return f"<AuthService(login_manager={login_mgr})>"
