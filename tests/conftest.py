"""
Configuration et fixtures partagées pour tous les tests.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Désactiver les tâches de fond pour les tests
os.environ.setdefault("DISABLE_BACKGROUND_TASKS", "1")
os.environ.setdefault("ENABLE_BACKGROUND_TASKS", "false")

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key")
os.environ.setdefault("TRIGGER_PAGE_PASSWORD", "test-dashboard-password")
os.environ.setdefault("EMAIL_ADDRESS", "test@example.com")
os.environ.setdefault("EMAIL_PASSWORD", "test-email-password")
os.environ.setdefault("IMAP_SERVER", "imap.example.com")
os.environ.setdefault("PROCESS_API_TOKEN", "test-process-api-token")
os.environ.setdefault("WEBHOOK_URL", "https://example.com/webhook")
os.environ.setdefault("MAKECOM_API_KEY", "test-makecom-api-key")


@pytest.fixture
def mock_redis():
    """Fixture pour un client Redis mocké avec fakeredis."""
    try:
        import fakeredis  # type: ignore
    except Exception:
        pytest.skip("fakeredis not installed")
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_logger():
    """Fixture pour un logger mocké."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


@pytest.fixture
def temp_file():
    """Fixture pour créer un fichier temporaire."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)
        yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def temp_dir():
    """Fixture pour créer un répertoire temporaire."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_email_body():
    """Fixture pour un corps d'email exemple."""
    return """
    Bonjour,
    
    Voici les fichiers à traiter pour 14h30.
    
    Lien de téléchargement: https://www.dropbox.com/scl/fo/abc123def456
    
    Cordialement
    """


@pytest.fixture
def sample_email_subject():
    """Fixture pour un sujet d'email exemple."""
    return "Média Solution - Missions Recadrage - Lot 42"


@pytest.fixture
def mock_imap_message():
    """Fixture pour un message IMAP mocké."""
    msg = MagicMock()
    msg.uid = "12345"
    msg.subject = "Test Email"
    msg.from_ = "sender@example.com"
    msg.date = MagicMock()
    msg.text = "Email body text"
    msg.html = "<html><body>Email body html</body></html>"
    return msg


@pytest.fixture(autouse=True)
def reset_env_vars():
    """Fixture pour réinitialiser les variables d'environnement après chaque test."""
    original_env = os.environ.copy()
    yield
    # Restaurer l'environnement original
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def flask_app():
    """Fixture pour créer une instance Flask pour les tests."""
    # Import tardif pour éviter les effets de bord
    import app_render

    app_render.app.config["TESTING"] = True
    app_render.app.config["WTF_CSRF_ENABLED"] = False
    return app_render.app


@pytest.fixture
def flask_client(flask_app):
    """Fixture pour créer un client de test Flask."""
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def authenticated_flask_client(flask_client):
    """Fixture pour créer un client Flask authentifié."""
    with flask_client.session_transaction() as sess:
        sess["_user_id"] = "admin"
        sess["_fresh"] = True
    return flask_client
