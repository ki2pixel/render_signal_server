"""
Tests unitaires pour email_processing/link_extraction.py
"""
import pytest

from email_processing import link_extraction


class TestExtractProviderLinksFromText:
    """Tests pour extract_provider_links_from_text()"""
    
    @pytest.mark.unit
    def test_extract_single_dropbox_link(self):
        """Test extraction d'un seul lien Dropbox"""
        text = "Voici le fichier: https://www.dropbox.com/scl/fo/abc123"
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 1
        assert result[0]["provider"] == "dropbox"
        assert "dropbox.com" in result[0]["raw_url"]
    
    @pytest.mark.unit
    def test_extract_single_fromsmash_link(self):
        """Test extraction d'un seul lien FromSmash"""
        text = "Télécharger ici: https://fromsmash.com/ABC-XYZ-123"
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 1
        assert result[0]["provider"] == "fromsmash"
        assert "fromsmash.com" in result[0]["raw_url"]
    
    @pytest.mark.unit
    def test_extract_single_swisstransfer_link(self):
        """Test extraction d'un seul lien SwissTransfer"""
        text = "Fichiers disponibles: https://www.swisstransfer.com/d/uuid-1234"
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 1
        assert result[0]["provider"] == "swisstransfer"
        assert "swisstransfer.com" in result[0]["raw_url"]
    
    @pytest.mark.unit
    def test_extract_multiple_links(self):
        """Test extraction de plusieurs liens de différents fournisseurs"""
        text = """
        Fichier 1: https://www.dropbox.com/scl/fo/abc123
        Fichier 2: https://fromsmash.com/XYZ-789
        Fichier 3: https://www.swisstransfer.com/d/uuid-5678
        """
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 3
        providers = [link["provider"] for link in result]
        assert "dropbox" in providers
        assert "fromsmash" in providers
        assert "swisstransfer" in providers
    
    @pytest.mark.unit
    def test_extract_no_links(self):
        """Test extraction sans liens présents"""
        text = "Ceci est un email sans aucun lien de partage"
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 0
    
    @pytest.mark.unit
    def test_extract_empty_text(self):
        """Test extraction avec texte vide"""
        result = link_extraction.extract_provider_links_from_text("")
        assert len(result) == 0
    
    @pytest.mark.unit
    def test_extract_none_text(self):
        """Test extraction avec None"""
        result = link_extraction.extract_provider_links_from_text(None)
        assert len(result) == 0
    
    @pytest.mark.unit
    def test_extract_ignores_unsupported_links(self):
        """Test que les liens non supportés sont ignorés"""
        text = """
        Dropbox: https://www.dropbox.com/scl/fo/abc123
        Google: https://drive.google.com/file/xyz
        """
        result = link_extraction.extract_provider_links_from_text(text)
        
        # Seul le lien Dropbox doit être extrait
        assert len(result) == 1
        assert result[0]["provider"] == "dropbox"
    
    @pytest.mark.unit
    def test_extract_duplicate_links(self):
        """Test extraction avec liens en double - vérifie la déduplication"""
        text = """
        Lien 1: https://www.dropbox.com/scl/fo/abc123
        Lien 2: https://www.dropbox.com/scl/fo/abc123
        """
        result = link_extraction.extract_provider_links_from_text(text)
        
        # Après refactoring: déduplication activée, une seule URL doit être extraite
        assert len(result) == 1
        assert result[0]["provider"] == "dropbox"
        assert "dropbox.com/scl/fo/abc123" in result[0]["raw_url"]
    
    @pytest.mark.unit
    def test_extract_from_html(self):
        """Test extraction depuis du HTML"""
        text = """
        <html>
        <body>
        <a href="https://www.dropbox.com/scl/fo/abc123">Télécharger</a>
        <p>Ou via FromSmash: https://fromsmash.com/XYZ-789</p>
        </body>
        </html>
        """
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 2
        providers = [link["provider"] for link in result]
        assert "dropbox" in providers
        assert "fromsmash" in providers
    
    @pytest.mark.unit
    def test_extract_case_insensitive(self):
        """Test extraction insensible à la casse"""
        text = "HTTPS://WWW.DROPBOX.COM/scl/fo/ABC123"
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 1
        assert result[0]["provider"] == "dropbox"
    
    @pytest.mark.unit
    def test_extract_with_query_params(self):
        """Test extraction avec paramètres de requête"""
        text = "https://www.dropbox.com/scl/fo/abc123?dl=0&rlkey=xyz"
        result = link_extraction.extract_provider_links_from_text(text)
        
        assert len(result) == 1
        assert result[0]["provider"] == "dropbox"
        assert "?dl=0" in result[0]["raw_url"]
