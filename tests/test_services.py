"""
Tests unitaires pour les services

Ce fichier teste les fonctionnalités de base de tous les services créés.
"""

import pytest
from pathlib import Path
import tempfile
import json
import os

# Import des services
from services import (
    ConfigService,
    RuntimeFlagsService,
    WebhookConfigService,
    AuthService,
    DeduplicationService,
    MagicLinkService,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_json_file():
    """Crée un fichier JSON temporaire."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
        yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Réinitialise les singletons avant chaque test."""
    RuntimeFlagsService.reset_instance()
    WebhookConfigService.reset_instance()
    MagicLinkService.reset_instance()
    yield
    RuntimeFlagsService.reset_instance()
    WebhookConfigService.reset_instance()
    MagicLinkService.reset_instance()


# =============================================================================
# Tests ConfigService
# =============================================================================

def test_config_service_creation():
    """Test création du ConfigService."""
    config = ConfigService()
    assert config is not None
    assert repr(config).startswith("<ConfigService(")


def test_config_service_email_config():
    """Test récupération config email."""
    config = ConfigService()
    email_cfg = config.get_email_config()
    
    assert isinstance(email_cfg, dict)
    assert "address" in email_cfg
    assert "password" in email_cfg
    assert "server" in email_cfg
    assert "port" in email_cfg
    assert "use_ssl" in email_cfg


def test_config_service_email_validation():
    """Test validation config email."""
    config = ConfigService()
    # Les valeurs par défaut devraient être valides
    assert config.is_email_config_valid() is True


def test_config_service_webhook():
    """Test configuration webhook."""
    config = ConfigService()
    webhook_url = config.get_webhook_url()
    assert isinstance(webhook_url, str)
    
    has_webhook = config.has_webhook_url()
    assert isinstance(has_webhook, bool)
    
    ssl_verify = config.get_webhook_ssl_verify()
    assert isinstance(ssl_verify, bool)


def test_config_service_api_token():
    """Test API token."""
    config = ConfigService()
    token = config.get_api_token()
    assert isinstance(token, str)
    
    has_token = config.has_api_token()
    assert isinstance(has_token, bool)
    
    # Test vérification
    if token:
        assert config.verify_api_token(token) is True
        assert config.verify_api_token("wrong-token") is False


# =============================================================================
# Tests RuntimeFlagsService
# =============================================================================

def test_runtime_flags_service_singleton(temp_json_file):
    """Test pattern Singleton."""
    defaults = {"flag1": False, "flag2": True}
    
    service1 = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    service2 = RuntimeFlagsService.get_instance()
    
    assert service1 is service2  # Même instance


def test_runtime_flags_service_get_flag(temp_json_file):
    """Test lecture de flags."""
    defaults = {"disable_dedup": False, "enable_feature": True}
    service = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    
    assert service.get_flag("disable_dedup") is False
    assert service.get_flag("enable_feature") is True
    assert service.get_flag("unknown_flag", default=True) is True


def test_runtime_flags_service_set_flag(temp_json_file):
    """Test modification de flags."""
    defaults = {"test_flag": False}
    service = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    
    # Modifier le flag
    success = service.set_flag("test_flag", True)
    assert success is True
    
    # Vérifier la modification
    assert service.get_flag("test_flag") is True


def test_runtime_flags_service_update_flags(temp_json_file):
    """Test mise à jour multiple."""
    defaults = {"flag1": False, "flag2": False, "flag3": False}
    service = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    
    success = service.update_flags({
        "flag1": True,
        "flag2": True,
    })
    assert success is True
    
    assert service.get_flag("flag1") is True
    assert service.get_flag("flag2") is True
    assert service.get_flag("flag3") is False  # Pas modifié


def test_runtime_flags_service_persistence(temp_json_file):
    """Test persistence sur disque."""
    defaults = {"persistent_flag": False}
    
    # Créer et modifier
    service1 = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    service1.set_flag("persistent_flag", True)
    
    # Vérifier que le fichier existe
    assert temp_json_file.exists()
    
    # Réinitialiser et recréer
    RuntimeFlagsService.reset_instance()
    service2 = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    
    # La valeur devrait être chargée depuis le disque
    assert service2.get_flag("persistent_flag") is True


def test_runtime_flags_service_cache_ttl(temp_json_file):
    """Test configuration du cache TTL."""
    defaults = {"flag": False}
    service = RuntimeFlagsService.get_instance(temp_json_file, defaults)
    
    # TTL par défaut
    assert service.get_cache_ttl() == 60
    
    # Modifier TTL
    service.set_cache_ttl(120)
    assert service.get_cache_ttl() == 120


# =============================================================================
# Tests WebhookConfigService
# =============================================================================

def test_webhook_config_service_singleton(temp_json_file):
    """Test pattern Singleton."""
    service1 = WebhookConfigService.get_instance(temp_json_file)
    service2 = WebhookConfigService.get_instance()
    
    assert service1 is service2


def test_webhook_config_service_url_validation():
    """Test validation des URLs."""
    # URL valide
    ok, msg = WebhookConfigService.validate_webhook_url("https://example.com/webhook")
    assert ok is True
    
    # URL non-HTTPS
    ok, msg = WebhookConfigService.validate_webhook_url("http://example.com/webhook")
    assert ok is False
    assert "https" in msg.lower()
    
    # URL vide (autorisée)
    ok, msg = WebhookConfigService.validate_webhook_url("")
    assert ok is True


def test_webhook_config_service_set_url(temp_json_file):
    """Test définition d'URL."""
    service = WebhookConfigService.get_instance(temp_json_file)
    
    ok, msg = service.set_webhook_url("https://hook.eu2.make.com/abc123")
    assert ok is True
    
    url = service.get_webhook_url()
    assert url == "https://hook.eu2.make.com/abc123"


def test_webhook_config_service_ssl_verify(temp_json_file):
    """Test flag SSL verify."""
    service = WebhookConfigService.get_instance(temp_json_file)
    
    # Par défaut True
    assert service.get_ssl_verify() is True
    
    # Désactiver
    service.set_ssl_verify(False)
    assert service.get_ssl_verify() is False


# =============================================================================
# Tests AuthService
# =============================================================================

def test_auth_service_creation():
    """Test création AuthService."""
    config = ConfigService()
    auth = AuthService(config)
    
    assert auth is not None
    assert repr(auth).startswith("<AuthService(")


def test_auth_service_dashboard_credentials():
    """Test vérification credentials dashboard."""
    config = ConfigService()
    auth = AuthService(config)
    
    # Credentials par défaut (voir settings.py)
    username = config.get_dashboard_user()
    password = config.get_dashboard_password()
    
    assert auth.verify_dashboard_credentials(username, password) is True
    assert auth.verify_dashboard_credentials("wrong", "wrong") is False


def test_auth_service_create_user():
    """Test création d'utilisateur."""
    config = ConfigService()
    auth = AuthService(config)
    
    user = auth.create_user("testuser")
    assert user is not None
    assert user.id == "testuser"


def test_auth_service_create_user_from_credentials():
    """Test création user avec vérification credentials."""
    config = ConfigService()
    auth = AuthService(config)
    
    username = config.get_dashboard_user()
    password = config.get_dashboard_password()
    
    # Credentials valides
    user = auth.create_user_from_credentials(username, password)
    assert user is not None
    assert user.id == username
    
    # Credentials invalides
    user = auth.create_user_from_credentials("wrong", "wrong")
    assert user is None


def test_auth_service_api_token():
    """Test vérification API token."""
    config = ConfigService()
    auth = AuthService(config)
    
    expected_token = config.get_api_token()
    
    if expected_token:
        assert auth.verify_api_token(expected_token) is True
        assert auth.verify_api_token("wrong-token") is False


# =============================================================================
# Tests MagicLinkService
# =============================================================================


def test_magic_link_service_unlimited_token_is_reusable(temp_json_file):
    """Un token illimité ne doit pas être consommé (réutilisable)."""
    service = MagicLinkService(
        secret_key="test-secret",
        storage_path=temp_json_file,
        ttl_seconds=60,
        config_service=ConfigService(),
    )

    token, expires_at = service.generate_token(unlimited=True)
    assert isinstance(token, str)
    assert expires_at is None

    ok, username1 = service.consume_token(token)
    assert ok is True
    assert isinstance(username1, str)

    ok, username2 = service.consume_token(token)
    assert ok is True
    assert username2 == username1


def test_magic_link_service_external_store_shares_state_across_instances():
    """Le store externe doit permettre à une autre instance de consommer le token."""

    class InMemoryExternalStore:
        def __init__(self):
            self._db = {}

        def get_config_json(self, key: str, *, file_fallback=None):
            return self._db.get(key, {})

        def set_config_json(self, key: str, value: dict, *, file_fallback=None) -> bool:
            self._db[key] = value
            return True

    os.environ["EXTERNAL_CONFIG_BASE_URL"] = "https://example.invalid"
    os.environ["CONFIG_API_TOKEN"] = "test-token"

    store = InMemoryExternalStore()
    with tempfile.TemporaryDirectory() as tmp_dir:
        path_a = Path(tmp_dir) / "a.json"
        path_b = Path(tmp_dir) / "b.json"

        instance_a = MagicLinkService(
            secret_key="test-secret",
            storage_path=path_a,
            ttl_seconds=60,
            config_service=ConfigService(),
            external_store=store,
        )
        token, _ = instance_a.generate_token(unlimited=True)

        instance_b = MagicLinkService(
            secret_key="test-secret",
            storage_path=path_b,
            ttl_seconds=60,
            config_service=ConfigService(),
            external_store=store,
        )
        ok, _ = instance_b.consume_token(token)
        assert ok is True


def test_magic_link_service_legacy_external_store_signature_supported():
    """Compat: external_store dont les méthodes n'acceptent pas file_fallback."""

    class LegacyExternalStore:
        def __init__(self):
            self._db = {}

        def get_config_json(self, key: str):
            return self._db.get(key, {})

        def set_config_json(self, key: str, value: dict) -> bool:
            self._db[key] = value
            return True

    os.environ["EXTERNAL_CONFIG_BASE_URL"] = "https://example.invalid"
    os.environ["CONFIG_API_TOKEN"] = "test-token"

    store = LegacyExternalStore()
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_path = Path(tmp_dir) / "tokens.json"

        service = MagicLinkService(
            secret_key="test-secret",
            storage_path=storage_path,
            ttl_seconds=60,
            config_service=ConfigService(),
            external_store=store,
        )
        token, _ = service.generate_token(unlimited=True)

        ok, _ = service.consume_token(token)
        assert ok is True


# =============================================================================
# Tests DeduplicationService
# =============================================================================

def test_dedup_service_creation():
    """Test création DeduplicationService."""
    config = ConfigService()
    dedup = DeduplicationService(
        redis_client=None,  # Pas de Redis = fallback mémoire
        logger=None,
        config_service=config,
    )
    
    assert dedup is not None
    assert repr(dedup).startswith("<DeduplicationService(")


def test_dedup_service_email_id_memory():
    """Test déduplication email ID (fallback mémoire)."""
    config = ConfigService()
    dedup = DeduplicationService(
        redis_client=None,
        logger=None,
        config_service=config,
    )
    
    email_id = "test_email_123"
    
    # Pas encore traité
    assert dedup.is_email_processed(email_id) is False
    
    # Marquer comme traité
    dedup.mark_email_processed(email_id)
    
    # Maintenant traité
    assert dedup.is_email_processed(email_id) is True


def test_dedup_service_subject_group_id():
    """Test génération subject group ID."""
    config = ConfigService()
    dedup = DeduplicationService(
        redis_client=None,
        logger=None,
        config_service=config,
    )
    
    # Média Solution Lot
    subject1 = "Média Solution - Missions Recadrage - Lot 42"
    group_id1 = dedup.generate_subject_group_id(subject1)
    assert group_id1 == "media_solution_missions_recadrage_lot_42"
    
    # Avec Re: et Fwd: (doit donner le même ID)
    subject2 = "Re: Fwd: Média Solution - Missions Recadrage - Lot 42"
    group_id2 = dedup.generate_subject_group_id(subject2)
    assert group_id2 == group_id1
    
    # Lot sans Média Solution
    subject3 = "Autre chose - Lot 99"
    group_id3 = dedup.generate_subject_group_id(subject3)
    assert group_id3 == "lot_99"
    
    # Sans lot (fallback hash)
    subject4 = "Sujet quelconque"
    group_id4 = dedup.generate_subject_group_id(subject4)
    assert group_id4.startswith("subject_hash_")


def test_dedup_service_memory_stats():
    """Test statistiques mémoire."""
    config = ConfigService()
    dedup = DeduplicationService(
        redis_client=None,
        logger=None,
        config_service=config,
    )
    
    # Marquer quelques items
    dedup.mark_email_processed("email1")
    dedup.mark_email_processed("email2")
    
    stats = dedup.get_memory_stats()
    assert stats["email_ids_count"] >= 2
    assert stats["using_redis"] is False
    
    # Clear cache
    dedup.clear_memory_cache()
    stats = dedup.get_memory_stats()
    assert stats["email_ids_count"] == 0


# =============================================================================
# Tests d'Intégration
# =============================================================================

def test_services_integration():
    """Test intégration de plusieurs services ensemble."""
    # Config
    config = ConfigService()
    
    # Auth avec Config injecté
    auth = AuthService(config)
    assert auth._config is config
    
    # Dedup avec Config injecté
    dedup = DeduplicationService(
        redis_client=None,
        logger=None,
        config_service=config,
    )
    assert dedup._config is config
    
    # Vérifier que la config est partagée
    assert auth._config is dedup._config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
