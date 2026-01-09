"""
tests.test_r2_transfer_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests unitaires pour R2TransferService.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from services.r2_transfer_service import R2TransferService


@pytest.fixture
def temp_links_file(tmp_path):
    """Crée un fichier temporaire pour webhook_links.json."""
    links_file = tmp_path / "webhook_links.json"
    links_file.write_text("[]", encoding="utf-8")
    return links_file


@pytest.fixture
def r2_service(temp_links_file):
    """Crée une instance R2TransferService pour les tests."""
    R2TransferService.reset_instance()
    
    service = R2TransferService.get_instance(
        fetch_endpoint="https://test-worker.example.com/fetch",
        public_base_url="https://media.example.com",
        bucket_name="test-bucket",
        links_file=temp_links_file,
    )
    
    # Activer le service pour les tests
    with patch.dict(os.environ, {"R2_FETCH_ENABLED": "true"}):
        service._enabled = True
        service._fetch_token = "test-token"
    
    yield service
    
    R2TransferService.reset_instance()


class TestR2TransferServiceInit:
    """Tests d'initialisation du service."""
    
    def test_singleton_pattern(self, temp_links_file):
        """Vérifie que le pattern Singleton fonctionne."""
        R2TransferService.reset_instance()
        
        service1 = R2TransferService.get_instance(
            fetch_endpoint="https://worker.example.com",
            links_file=temp_links_file,
        )
        service2 = R2TransferService.get_instance()
        
        assert service1 is service2
        
        R2TransferService.reset_instance()
    
    def test_initialization_from_env(self, temp_links_file):
        """Vérifie l'initialisation depuis les variables d'environnement."""
        R2TransferService.reset_instance()
        
        with patch.dict(os.environ, {
            "R2_FETCH_ENDPOINT": "https://env-worker.example.com",
            "R2_PUBLIC_BASE_URL": "https://env-cdn.example.com",
            "R2_BUCKET_NAME": "env-bucket",
            "R2_FETCH_TOKEN": "env-token",
            "R2_FETCH_ENABLED": "true",
        }):
            service = R2TransferService.get_instance(links_file=temp_links_file)
            
            assert service._fetch_endpoint == "https://env-worker.example.com"
            assert service._public_base_url == "https://env-cdn.example.com"
            assert service._bucket_name == "env-bucket"
            assert service._fetch_token == "env-token"
            assert service.is_enabled() is True
        
        R2TransferService.reset_instance()
    
    def test_disabled_by_default(self, temp_links_file):
        """Vérifie que le service est désactivé par défaut."""
        R2TransferService.reset_instance()
        
        with patch.dict(os.environ, {"R2_FETCH_ENABLED": "false"}, clear=True):
            service = R2TransferService.get_instance(
                fetch_endpoint="https://worker.example.com",
                links_file=temp_links_file,
            )
            
            assert service.is_enabled() is False
        
        R2TransferService.reset_instance()


class TestR2TransferServiceFetch:
    """Tests de la méthode request_remote_fetch."""
    
    @patch('services.r2_transfer_service.requests')
    def test_successful_fetch(self, mock_requests, r2_service):
        """Teste un transfert réussi."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "r2_url": "https://media.example.com/dropbox/abc123/file.zip",
            "original_filename": "61 Camille.zip",
        }
        mock_requests.post.return_value = mock_response
        
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            provider="dropbox",
            email_id="test-email-id",
        )
        
        assert r2_url == "https://media.example.com/dropbox/abc123/file.zip"
        assert original_filename == "61 Camille.zip"
        
        # Vérifier l'appel au Worker
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert call_args[0][0] == "https://test-worker.example.com/fetch"
        
        payload = call_args[1]['json']
        assert payload['source_url'] == "https://www.dropbox.com/s/abc123/file.zip?dl=1"
        assert payload['provider'] == "dropbox"
        assert payload['bucket'] == "test-bucket"
        assert 'object_key' in payload

    @patch('services.r2_transfer_service.requests')
    def test_fetch_dropbox_shared_folder_links_best_effort(self, mock_requests, r2_service):
        """Vérifie que l'offload R2 est tenté (best-effort) pour les liens Dropbox /scl/fo/."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "r2_url": "https://media.example.com/dropbox/abc123/folder.zip",
            "original_filename": "Lot 66.zip",
        }
        mock_requests.post.return_value = mock_response

        url = "https://www.dropbox.com/scl/fo/abc123/xyz?rlkey=test&dl=0"
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url=url,
            provider="dropbox",
            email_id="test-email-id",
        )

        assert r2_url == "https://media.example.com/dropbox/abc123/folder.zip"
        assert original_filename == "Lot 66.zip"
        mock_requests.post.assert_called_once()
        payload = mock_requests.post.call_args[1]["json"]
        assert payload["source_url"].startswith(
            "https://www.dropbox.com/scl/fo/abc123/xyz?"
        )
        assert "dl=1" in payload["source_url"]
    
    @patch('services.r2_transfer_service.requests')
    def test_fetch_worker_error(self, mock_requests, r2_service):
        """Teste le cas où le Worker retourne une erreur."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_requests.post.return_value = mock_response
        
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            provider="dropbox",
        )
        
        assert r2_url is None
        assert original_filename is None
    
    @patch('services.r2_transfer_service.requests')
    def test_fetch_timeout(self, mock_requests, r2_service):
        """Teste le cas d'un timeout."""
        mock_requests.post.side_effect = mock_requests.exceptions.Timeout()
        
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            provider="dropbox",
            timeout=5,
        )
        
        assert r2_url is None
        assert original_filename is None
    
    @patch('services.r2_transfer_service.requests')
    def test_fetch_network_error(self, mock_requests, r2_service):
        """Teste le cas d'une erreur réseau."""
        mock_requests.post.side_effect = mock_requests.exceptions.RequestException()
        
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            provider="dropbox",
        )
        
        assert r2_url is None
        assert original_filename is None
    
    def test_fetch_disabled_service(self, r2_service):
        """Teste le cas où le service est désactivé."""
        r2_service._enabled = False
        
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            provider="dropbox",
        )
        
        assert r2_url is None
        assert original_filename is None
    
    def test_fetch_invalid_params(self, r2_service):
        """Teste avec des paramètres invalides."""
        # URL vide
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="",
            provider="dropbox",
        )
        assert r2_url is None
        assert original_filename is None
        
        # Provider vide
        r2_url, original_filename = r2_service.request_remote_fetch(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            provider="",
        )
        assert r2_url is None
        assert original_filename is None


class TestR2TransferServicePersistence:
    """Tests de la persistance des liens."""
    
    def test_persist_link_pair(self, r2_service, temp_links_file):
        """Teste la persistance d'une paire source/R2."""
        success = r2_service.persist_link_pair(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            r2_url="https://media.example.com/dropbox/abc123/file.zip",
            provider="dropbox",
            original_filename="57 Camille.zip",
        )
        
        assert success is True
        
        # Vérifier le contenu du fichier
        with open(temp_links_file, 'r', encoding='utf-8') as f:
            links = json.load(f)
        
        assert len(links) == 1
        assert links[0]['source_url'] == "https://www.dropbox.com/s/abc123/file.zip?dl=1"
        assert links[0]['r2_url'] == "https://media.example.com/dropbox/abc123/file.zip"
        assert links[0]['provider'] == "dropbox"
        assert links[0]['original_filename'] == "57 Camille.zip"
        assert 'email_id' not in links[0]
        assert 'created_at' in links[0]
    
    def test_persist_multiple_links(self, r2_service, temp_links_file):
        """Teste la persistance de plusieurs liens."""
        for i in range(3):
            r2_service.persist_link_pair(
                source_url=f"https://www.dropbox.com/s/link{i}/file.zip",
                r2_url=f"https://media.example.com/dropbox/link{i}/file.zip",
                provider="dropbox",
            )
        
        with open(temp_links_file, 'r', encoding='utf-8') as f:
            links = json.load(f)
        
        assert len(links) == 3
    
    def test_persist_rotation(self, r2_service, temp_links_file):
        """Teste la rotation des liens (limite max_entries)."""
        with patch.dict(os.environ, {"R2_LINKS_MAX_ENTRIES": "5"}):
            # Ajouter 10 liens
            for i in range(10):
                r2_service.persist_link_pair(
                    source_url=f"https://www.dropbox.com/s/link{i}/file.zip",
                    r2_url=f"https://media.example.com/dropbox/link{i}/file.zip",
                    provider="dropbox",
                )
            
            with open(temp_links_file, 'r', encoding='utf-8') as f:
                links = json.load(f)
            
            # Seulement les 5 derniers doivent être conservés
            assert len(links) == 5
            assert links[0]['source_url'] == "https://www.dropbox.com/s/link5/file.zip?dl=1"
            assert links[-1]['source_url'] == "https://www.dropbox.com/s/link9/file.zip?dl=1"
    
    def test_persist_invalid_params(self, r2_service):
        """Teste la persistance avec des paramètres invalides."""
        # URL source vide
        success = r2_service.persist_link_pair(
            source_url="",
            r2_url="https://media.example.com/file.zip",
            provider="dropbox",
        )
        assert success is False
        
        # URL R2 vide
        success = r2_service.persist_link_pair(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            r2_url="",
            provider="dropbox",
        )
        assert success is False
    
    def test_get_r2_url_for_source(self, r2_service, temp_links_file):
        """Teste la récupération d'une URL R2 depuis l'URL source."""
        # Ajouter un lien
        r2_service.persist_link_pair(
            source_url="https://www.dropbox.com/s/abc123/file.zip",
            r2_url="https://media.example.com/dropbox/abc123/file.zip",
            provider="dropbox",
        )
        
        # Récupérer l'URL R2
        r2_url = r2_service.get_r2_url_for_source(
            "https://www.dropbox.com/s/abc123/file.zip"
        )
        
        assert r2_url == "https://media.example.com/dropbox/abc123/file.zip"


class TestR2TransferServiceDropboxNormalization:
    """Tests ciblés sur la normalisation Dropbox inspirée de debug/csv_service.py."""

    def test_normalize_dropbox_unescape_ampersand(self, r2_service):
        url = "https://www.dropbox.com/scl/fi/abc123/file.png?rlkey=foo&amp;dl=0"
        normalized = r2_service.normalize_source_url(url, "dropbox")
        assert normalized == "https://www.dropbox.com/scl/fi/abc123/file.png?dl=1&rlkey=foo"

    def test_normalize_dropbox_decodes_amp3b(self, r2_service):
        url = "https://www.dropbox.com/s/abc123/file.zip?amp%3Bdl=0&dl=1"
        normalized = r2_service.normalize_source_url(url, "dropbox")
        assert normalized == "https://www.dropbox.com/s/abc123/file.zip?dl=1"
    
    def test_get_r2_url_not_found(self, r2_service, temp_links_file):
        """Teste la récupération d'une URL R2 inexistante."""
        r2_url = r2_service.get_r2_url_for_source(
            "https://www.dropbox.com/s/notfound/file.zip"
        )
        
        assert r2_url is None


class TestR2TransferServiceObjectKey:
    """Tests de la génération de clés d'objets."""
    
    def test_generate_object_key(self, r2_service):
        """Teste la génération d'une clé d'objet unique."""
        key = r2_service._generate_object_key(
            source_url="https://www.dropbox.com/s/abc123/myfile.zip?dl=1",
            provider="dropbox"
        )
        
        # Vérifier le format : provider/hash[:8]/hash[8:16]/filename
        parts = key.split('/')
        assert len(parts) == 4
        assert parts[0] == "dropbox"
        assert len(parts[1]) == 8  # prefix
        assert len(parts[2]) == 8  # subdir
        assert parts[3] == "myfile.zip"
    
    def test_generate_object_key_deterministic(self, r2_service):
        """Vérifie que la même URL génère toujours la même clé."""
        url = "https://www.dropbox.com/s/abc123/file.zip"
        
        key1 = r2_service._generate_object_key(url, "dropbox")
        key2 = r2_service._generate_object_key(url, "dropbox")
        
        assert key1 == key2
    
    def test_generate_object_key_different_urls(self, r2_service):
        """Vérifie que des URLs différentes génèrent des clés différentes."""
        key1 = r2_service._generate_object_key(
            "https://www.dropbox.com/s/abc123/file1.zip",
            "dropbox"
        )
        key2 = r2_service._generate_object_key(
            "https://www.dropbox.com/s/def456/file2.zip",
            "dropbox"
        )
        
        assert key1 != key2
    
    def test_generate_object_key_fallback_filename(self, r2_service):
        """Teste le fallback quand aucun nom de fichier n'est détectable."""
        key = r2_service._generate_object_key(
            "https://fromsmash.com/ABC123",
            "fromsmash"
        )
        
        parts = key.split('/')
        # Le nom de fichier par défaut devrait être "file"
        assert parts[-1] == "file"


class TestR2TransferServiceRepr:
    """Tests de la représentation du service."""
    
    def test_repr_enabled(self, r2_service):
        """Teste la représentation quand le service est activé."""
        repr_str = repr(r2_service)
        
        assert "R2TransferService" in repr_str
        assert "enabled" in repr_str
        assert "test-bucket" in repr_str
    
    def test_repr_disabled(self, temp_links_file):
        """Teste la représentation quand le service est désactivé."""
        R2TransferService.reset_instance()
        
        with patch.dict(os.environ, {"R2_FETCH_ENABLED": "false"}, clear=True):
            service = R2TransferService.get_instance(
                fetch_endpoint="https://worker.example.com",
                links_file=temp_links_file,
            )
            
            repr_str = repr(service)
            
            assert "R2TransferService" in repr_str
            assert "disabled" in repr_str
        
        R2TransferService.reset_instance()
