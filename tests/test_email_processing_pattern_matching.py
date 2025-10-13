"""
Tests unitaires pour email_processing/pattern_matching.py
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo

from email_processing import pattern_matching


class TestCheckMediaSolutionPattern:
    """Tests pour check_media_solution_pattern()"""
    
    @pytest.mark.unit
    def test_valid_pattern_with_dropbox(self, mock_logger):
        """Test pattern valide avec lien Dropbox"""
        subject = "Média Solution - Missions Recadrage - Lot 42"
        body = "À faire pour 14h30. Lien: https://www.dropbox.com/scl/fo/abc123"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is True
        assert result['delivery_time'] == "14h30"
    
    @pytest.mark.unit
    def test_valid_pattern_with_fromsmash(self, mock_logger):
        """Test pattern valide avec lien FromSmash"""
        subject = "Média Solution - Missions Recadrage - Lot 1"
        body = "À faire pour 09h00. https://fromsmash.com/ABC-XYZ-123"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is True
        assert result['delivery_time'] == "09h00"
    
    @pytest.mark.unit
    def test_valid_pattern_with_swisstransfer(self, mock_logger):
        """Test pattern valide avec lien SwissTransfer"""
        subject = "Média Solution - Missions Recadrage - Lot 7"
        body = "À faire pour 16h45. https://www.swisstransfer.com/d/uuid-1234"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is True
        assert result['delivery_time'] == "16h45"
    
    @pytest.mark.unit
    def test_urgence_overrides_time(self, mock_logger):
        """Test que URGENCE dans le sujet écrase l'heure du corps"""
        subject = "Média Solution - Missions Recadrage - Lot 5 - URGENCE"
        body = "À faire pour 14h30. https://www.dropbox.com/scl/fo/abc123"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is True
        # L'heure devrait être maintenant + 1h au format HHhMM
        assert result['delivery_time'] is not None
        assert len(result['delivery_time']) == 5  # Format "HHhMM"
        assert 'h' in result['delivery_time']
    
    @pytest.mark.unit
    def test_date_and_time_format(self, mock_logger):
        """Test extraction avec date et heure"""
        subject = "Média Solution - Missions Recadrage - Lot 10"
        body = "À faire pour le 15/10/2025 à 09h30. https://www.dropbox.com/scl/fo/abc"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is True
        assert "15/10/2025" in result['delivery_time']
        assert "09h30" in result['delivery_time']
    
    @pytest.mark.unit
    def test_missing_subject(self, mock_logger):
        """Test avec sujet manquant"""
        body = "À faire pour 14h30. https://www.dropbox.com/scl/fo/abc123"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(None, body, tz, mock_logger)
        
        assert result['matches'] is False
    
    @pytest.mark.unit
    def test_missing_body(self, mock_logger):
        """Test avec corps manquant"""
        subject = "Média Solution - Missions Recadrage - Lot 42"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, None, tz, mock_logger)
        
        assert result['matches'] is False
    
    @pytest.mark.unit
    def test_wrong_subject_pattern(self, mock_logger):
        """Test avec sujet non conforme"""
        subject = "Autre chose"
        body = "À faire pour 14h30. https://www.dropbox.com/scl/fo/abc123"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is False
    
    @pytest.mark.unit
    def test_missing_delivery_url(self, mock_logger):
        """Test sans URL de livraison"""
        subject = "Média Solution - Missions Recadrage - Lot 42"
        body = "À faire pour 14h30. Pas de lien ici."
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is False
    
    @pytest.mark.unit
    def test_case_insensitive_subject(self, mock_logger):
        """Test insensibilité à la casse du sujet"""
        subject = "média solution - missions recadrage - lot 42"
        body = "À faire pour 14h30. https://www.dropbox.com/scl/fo/abc123"
        tz = ZoneInfo("Europe/Paris")
        
        result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
        
        assert result['matches'] is True
    
    @pytest.mark.unit
    def test_various_time_formats(self, mock_logger):
        """Test différents formats d'heure"""
        subject = "Média Solution - Missions Recadrage - Lot 1"
        tz = ZoneInfo("Europe/Paris")
        
        test_cases = [
            ("À faire pour 9h. https://www.dropbox.com/scl/fo/abc", "09h00"),
            ("À faire pour 9h5. https://www.dropbox.com/scl/fo/abc", "09h05"),
            ("À faire pour 9:05. https://www.dropbox.com/scl/fo/abc", "09h05"),
            ("À faire pour 14h51. https://www.dropbox.com/scl/fo/abc", "14h51"),
        ]
        
        for body, expected_time in test_cases:
            result = pattern_matching.check_media_solution_pattern(subject, body, tz, mock_logger)
            assert result['matches'] is True
            assert result['delivery_time'] == expected_time


class TestCheckDesaboConditions:
    """Tests pour check_desabo_conditions()"""
    
    @pytest.mark.unit
    def test_desabo_with_all_keywords(self, mock_logger):
        """Test détection DESABO avec tous les mots-clés"""
        subject = "Demande de désabonnement"
        body = """
        Bonjour,
        Je souhaite me désabonner de la journée.
        Voici les tarifs habituels à appliquer.
        Lien: https://www.dropbox.com/request/abc123
        """
        
        result = pattern_matching.check_desabo_conditions(subject, body, mock_logger)
        
        assert result['matches'] is True
        assert result['has_dropbox_request'] is True
    
    @pytest.mark.unit
    def test_desabo_without_dropbox_request(self, mock_logger):
        """Test DESABO sans lien Dropbox /request"""
        subject = "Désabonnement"
        body = "Je souhaite me désabonner de la journée. Tarifs habituels."
        
        result = pattern_matching.check_desabo_conditions(subject, body, mock_logger)
        
        assert result['matches'] is True
        assert result['has_dropbox_request'] is False
    
    @pytest.mark.unit
    def test_desabo_case_insensitive(self, mock_logger):
        """Test insensibilité à la casse"""
        subject = "DÉSABONNEMENT"
        body = "JOURNÉE et TARIFS HABITUELS"
        
        result = pattern_matching.check_desabo_conditions(subject, body, mock_logger)
        
        assert result['matches'] is True
    
    @pytest.mark.unit
    def test_desabo_with_accents(self, mock_logger):
        """Test avec accents"""
        subject = "Désabonnement"
        body = "journée et tarifs habituels"
        
        result = pattern_matching.check_desabo_conditions(subject, body, mock_logger)
        
        assert result['matches'] is True
    
    @pytest.mark.unit
    def test_desabo_missing_keywords(self, mock_logger):
        """Test sans tous les mots-clés requis"""
        subject = "Autre sujet"
        body = "Contenu sans les mots-clés requis"
        
        result = pattern_matching.check_desabo_conditions(subject, body, mock_logger)
        
        assert result['matches'] is False
    
    @pytest.mark.unit
    def test_desabo_only_desabonner(self, mock_logger):
        """Test avec seulement 'désabonner' (insuffisant)"""
        subject = "Désabonnement"
        body = "Je veux me désabonner"
        
        result = pattern_matching.check_desabo_conditions(subject, body, mock_logger)
        
        # Doit avoir les 3 mots-clés
        assert result['matches'] is False
    
    @pytest.mark.unit
    def test_desabo_none_inputs(self, mock_logger):
        """Test avec entrées None"""
        result = pattern_matching.check_desabo_conditions(None, None, mock_logger)
        
        assert result['matches'] is False
        assert result['has_dropbox_request'] is False
    
    @pytest.mark.unit
    def test_desabo_empty_inputs(self, mock_logger):
        """Test avec entrées vides"""
        result = pattern_matching.check_desabo_conditions("", "", mock_logger)
        
        assert result['matches'] is False


class TestURLProvidersPattern:
    """Tests pour le pattern regex URL_PROVIDERS_PATTERN"""
    
    @pytest.mark.unit
    def test_pattern_matches_dropbox(self):
        """Test que le pattern détecte Dropbox"""
        text = "Fichier: https://www.dropbox.com/scl/fo/abc123"
        matches = list(pattern_matching.URL_PROVIDERS_PATTERN.finditer(text))
        
        assert len(matches) == 1
        assert "dropbox.com" in matches[0].group(1)
    
    @pytest.mark.unit
    def test_pattern_matches_fromsmash(self):
        """Test que le pattern détecte FromSmash"""
        text = "Lien: https://fromsmash.com/ABC-XYZ-123"
        matches = list(pattern_matching.URL_PROVIDERS_PATTERN.finditer(text))
        
        assert len(matches) == 1
        assert "fromsmash.com" in matches[0].group(1)
    
    @pytest.mark.unit
    def test_pattern_matches_swisstransfer(self):
        """Test que le pattern détecte SwissTransfer"""
        text = "Download: https://www.swisstransfer.com/d/uuid-1234-5678"
        matches = list(pattern_matching.URL_PROVIDERS_PATTERN.finditer(text))
        
        assert len(matches) == 1
        assert "swisstransfer.com" in matches[0].group(1)
    
    @pytest.mark.unit
    def test_pattern_matches_multiple(self):
        """Test détection de plusieurs URLs"""
        text = """
        Dropbox: https://www.dropbox.com/scl/fo/abc
        FromSmash: https://fromsmash.com/XYZ
        Swiss: https://www.swisstransfer.com/d/uuid
        """
        matches = list(pattern_matching.URL_PROVIDERS_PATTERN.finditer(text))
        
        assert len(matches) == 3
    
    @pytest.mark.unit
    def test_pattern_case_insensitive(self):
        """Test insensibilité à la casse"""
        text = "HTTPS://WWW.DROPBOX.COM/scl/fo/ABC123"
        matches = list(pattern_matching.URL_PROVIDERS_PATTERN.finditer(text))
        
        assert len(matches) == 1
    
    @pytest.mark.unit
    def test_pattern_ignores_other_urls(self):
        """Test que d'autres URLs sont ignorées"""
        text = """
        Dropbox: https://www.dropbox.com/scl/fo/abc
        Google: https://drive.google.com/file/xyz
        """
        matches = list(pattern_matching.URL_PROVIDERS_PATTERN.finditer(text))
        
        # Seul Dropbox devrait être détecté
        assert len(matches) == 1
        assert "dropbox" in matches[0].group(1).lower()
