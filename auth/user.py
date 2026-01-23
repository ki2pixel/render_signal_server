"""
auth.user
~~~~~~~~~

Gestion des utilisateurs et authentification Flask-Login pour le dashboard.
"""

from flask_login import LoginManager, UserMixin
from config.settings import TRIGGER_PAGE_USER, TRIGGER_PAGE_PASSWORD


# CLASSE USER

class User(UserMixin):
    """Représente un utilisateur simple, identifié par son username."""

    def __init__(self, username: str):
        self.id = username


# CONFIGURATION FLASK-LOGIN

login_manager = None


def init_login_manager(app, login_view: str = 'dashboard.login'):
    """Initialise Flask-Login pour l'application et configure user_loader.

    Args:
        app: Flask application
        login_view: endpoint name to redirect unauthenticated users
    Returns:
        Configured LoginManager
    """
    global login_manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = login_view

    @login_manager.user_loader
    def _load_user(user_id: str):
        return User(user_id) if user_id == TRIGGER_PAGE_USER else None

    return login_manager


# HELPERS D'AUTHENTIFICATION

def verify_credentials(username: str, password: str) -> bool:
    """
    Vérifie les credentials pour la connexion au dashboard.
    
    Args:
        username: Nom d'utilisateur
        password: Mot de passe
    
    Returns:
        True si credentials valides, False sinon
    """
    return username == TRIGGER_PAGE_USER and password == TRIGGER_PAGE_PASSWORD


def create_user_from_credentials(username: str, password: str) -> User | None:
    """
    Crée une instance User si les credentials sont valides.
    
    Args:
        username: Nom d'utilisateur
        password: Mot de passe
    
    Returns:
        Instance User si valide, None sinon
    """
    if verify_credentials(username, password):
        return User(username)
    return None
