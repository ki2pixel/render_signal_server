"""
Tests end-to-end pour le flux complet de traitement des emails
"""
import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
from zoneinfo import ZoneInfo


@pytest.mark.e2e
class TestEmailProcessingE2E:
    """Tests end-to-end du flux de traitement des emails"""
    
    def test_complete_media_solution_flow(self, mock_logger):
        """Test du flux complet Média Solution"""
        from email_processing import pattern_matching, link_extraction, payloads, webhook_sender
        
        # Données d'entrée
        subject = "Média Solution - Missions Recadrage - Lot 42"
        body = "À faire pour 14h30. Lien: https://www.dropbox.com/scl/fo/abc123"
        tz = ZoneInfo("Europe/Paris")
        
        # 1. Vérification du pattern
        pattern_result = pattern_matching.check_media_solution_pattern(
            subject, body, tz, mock_logger
        )
        assert pattern_result['matches'] is True
        assert pattern_result['delivery_time'] == "14h30"
        
        # 2. Extraction des liens
        links = link_extraction.extract_provider_links_from_text(body)
        assert len(links) == 1
        assert links[0]['provider'] == 'dropbox'
        
        # 3. Construction du payload
        payload = payloads.build_custom_webhook_payload(
            email_id="12345",
            subject=subject,
            date_received="2025-10-13T12:00:00Z",
            sender="sender@example.com",
            body_preview=body[:100],
            full_email_content=body,
            delivery_links=links,
            first_direct_url=links[0]['raw_url']
        )
        
        assert payload['subject'] == subject
        assert payload['delivery_links'] == links
        assert len(payload['dropbox_urls']) == 1
    
    def test_complete_desabo_flow(self, mock_logger):
        """Test du flux complet DESABO"""
        from email_processing import pattern_matching, payloads
        
        # Données d'entrée
        subject = "Demande de désabonnement"
        body = """
        Bonjour,
        Je souhaite me désabonner de la journée.
        Voici les tarifs habituels à appliquer.
        Lien: https://www.dropbox.com/request/abc123
        """
        
        # 1. Vérification du pattern DESABO
        desabo_result = pattern_matching.check_desabo_conditions(
            subject, body, mock_logger
        )
        assert desabo_result['matches'] is True
        assert desabo_result['has_dropbox_request'] is True
        
        # 2. Construction du payload DESABO
        desabo_payload = payloads.build_desabo_make_payload(
            subject=subject,
            full_email_content=body,
            sender_email="sender@example.com",
            time_start_payload="09:00",
            time_end_payload="17:00"
        )
        
        assert desabo_payload['detector'] == "desabonnement_journee_tarifs"
        assert desabo_payload['Subject'] == subject
        assert desabo_payload['webhooks_time_start'] == "09:00"
    
    @pytest.mark.slow
    def test_webhook_sending_with_retry(self, mock_logger):
        """Test envoi webhook avec retry sur échec"""
        from email_processing import webhook_sender
        
        # Mock des appels HTTP
        with patch('email_processing.webhook_sender.requests.post') as mock_post:
            # Simuler un échec puis un succès
            mock_response_fail = Mock()
            mock_response_fail.status_code = 500
            mock_response_fail.text = "Server Error"
            
            mock_response_success = Mock()
            mock_response_success.status_code = 200
            mock_response_success.text = "OK"
            
            mock_post.side_effect = [mock_response_fail, mock_response_success]
            
            # Mock de log_hook
            log_hook = MagicMock()
            
            # Appel avec retry
            result = webhook_sender.send_makecom_webhook(
                subject="Test",
                delivery_time="14h30",
                sender_email="test@example.com",
                email_id="12345",
                logger=mock_logger,
                log_hook=log_hook
            )
            
            # Le premier appel a échoué, le second a réussi
            assert mock_post.call_count == 2
    
    def test_multiple_providers_in_single_email(self, mock_logger):
        """Test email avec plusieurs fournisseurs"""
        from email_processing import link_extraction
        
        body = """
        Fichiers disponibles:
        - Dropbox: https://www.dropbox.com/scl/fo/abc123
        - FromSmash: https://fromsmash.com/XYZ-789
        - SwissTransfer: https://www.swisstransfer.com/d/uuid-1234
        """
        
        links = link_extraction.extract_provider_links_from_text(body)
        
        assert len(links) == 3
        providers = [link['provider'] for link in links]
        assert 'dropbox' in providers
        assert 'fromsmash' in providers
        assert 'swisstransfer' in providers
    
    def test_email_without_matching_pattern(self, mock_logger):
        """Test email ne correspondant à aucun pattern"""
        from email_processing import pattern_matching
        
        subject = "Email normal"
        body = "Contenu quelconque sans pattern spécifique"
        tz = ZoneInfo("Europe/Paris")
        
        # Vérifier qu'aucun pattern ne match
        media_result = pattern_matching.check_media_solution_pattern(
            subject, body, tz, mock_logger
        )
        assert media_result['matches'] is False
        
        desabo_result = pattern_matching.check_desabo_conditions(
            subject, body, mock_logger
        )
        assert desabo_result['matches'] is False


@pytest.mark.integration
class TestOrchestratorIntegration:
    """Tests d'intégration pour l'orchestrateur"""
    
    def test_orchestrator_exists_and_is_callable(self):
        """Test que l'orchestrateur existe et est appelable"""
        from email_processing import orchestrator
        
        assert hasattr(orchestrator, 'check_new_emails_and_trigger_webhook')
        assert callable(orchestrator.check_new_emails_and_trigger_webhook)
    
    def test_orchestrator_helper_functions_exist(self):
        """Test que les helpers d'orchestration existent"""
        from email_processing import orchestrator
        
        expected_helpers = [
            'handle_presence_route',
            'handle_desabo_route',
            'handle_media_solution_route',
            'compute_desabo_time_window',
            'send_custom_webhook_flow'
        ]
        
        for helper in expected_helpers:
            assert hasattr(orchestrator, helper), f"Helper {helper} manquant"
            assert callable(getattr(orchestrator, helper))


@pytest.mark.integration
class TestIMAPClientIntegration:
    """Tests d'intégration pour le client IMAP"""
    
    def test_imap_client_creation_function_exists(self):
        """Test que la fonction de création IMAP existe"""
        from email_processing import imap_client
        
        assert hasattr(imap_client, 'create_imap_connection')
        assert callable(imap_client.create_imap_connection)
    
    @pytest.mark.imap
    @pytest.mark.slow
    def test_imap_connection_with_invalid_credentials(self):
        """Test connexion IMAP avec credentials invalides"""
        from email_processing import imap_client
        
        # Cette fonction devrait lever une exception ou retourner None
        # avec des credentials invalides
        try:
            result = imap_client.create_imap_connection(
                server="invalid.server.com",
                port=993,
                email="invalid@example.com",
                password="wrongpassword",
                logger=MagicMock()
            )
            # Si pas d'exception, le résultat devrait être None ou False
            assert result is None or result is False
        except Exception:
            # C'est acceptable que ça lève une exception
            pass
