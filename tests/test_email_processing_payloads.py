"""
Tests unitaires pour email_processing/payloads.py
"""
import pytest

from email_processing import payloads


class TestBuildCustomWebhookPayload:
    """Tests pour build_custom_webhook_payload()"""
    
    @pytest.mark.unit
    def test_build_complete_payload(self):
        """Test construction d'un payload complet"""
        delivery_links = [
            {"provider": "dropbox", "raw_url": "https://www.dropbox.com/scl/fo/abc123"},
            {"provider": "fromsmash", "raw_url": "https://fromsmash.com/XYZ-789"},
        ]
        
        result = payloads.build_custom_webhook_payload(
            email_id="12345",
            subject="Test Subject",
            date_received="2025-10-13T14:30:00Z",
            sender="sender@example.com",
            body_preview="This is a preview...",
            full_email_content="Full email content here",
            delivery_links=delivery_links,
            first_direct_url="https://www.dropbox.com/scl/fo/abc123",
        )
        
        assert result["microsoft_graph_email_id"] == "12345"
        assert result["subject"] == "Test Subject"
        assert result["receivedDateTime"] == "2025-10-13T14:30:00Z"
        assert result["sender_address"] == "sender@example.com"
        assert result["bodyPreview"] == "This is a preview..."
        assert result["email_content"] == "Full email content here"
        assert result["delivery_links"] == delivery_links
        assert result["first_direct_download_url"] == "https://www.dropbox.com/scl/fo/abc123"
    
    @pytest.mark.unit
    def test_build_with_dropbox_legacy_fields(self):
        """Test que les champs legacy Dropbox sont ajoutés"""
        delivery_links = [
            {"provider": "dropbox", "raw_url": "https://www.dropbox.com/scl/fo/abc123"},
            {"provider": "dropbox", "raw_url": "https://www.dropbox.com/scl/fo/def456"},
            {"provider": "fromsmash", "raw_url": "https://fromsmash.com/XYZ"},
        ]
        
        result = payloads.build_custom_webhook_payload(
            email_id="12345",
            subject="Test",
            date_received=None,
            sender=None,
            body_preview=None,
            full_email_content=None,
            delivery_links=delivery_links,
            first_direct_url=None,
        )
        
        # Vérifier les champs legacy Dropbox
        assert "dropbox_urls" in result
        assert len(result["dropbox_urls"]) == 2
        assert "dropbox.com/scl/fo/abc123" in result["dropbox_urls"][0]
        assert "dropbox.com/scl/fo/def456" in result["dropbox_urls"][1]
        assert result["dropbox_first_url"] == result["dropbox_urls"][0]
    
    @pytest.mark.unit
    def test_build_without_dropbox_links(self):
        """Test payload sans liens Dropbox"""
        delivery_links = [
            {"provider": "fromsmash", "raw_url": "https://fromsmash.com/XYZ"},
        ]
        
        result = payloads.build_custom_webhook_payload(
            email_id="12345",
            subject="Test",
            date_received=None,
            sender=None,
            body_preview=None,
            full_email_content=None,
            delivery_links=delivery_links,
            first_direct_url=None,
        )
        
        assert result["dropbox_urls"] == []
        assert result["dropbox_first_url"] is None
    
    @pytest.mark.unit
    def test_build_with_empty_delivery_links(self):
        """Test payload avec liste de liens vide"""
        result = payloads.build_custom_webhook_payload(
            email_id="12345",
            subject="Test",
            date_received=None,
            sender=None,
            body_preview=None,
            full_email_content=None,
            delivery_links=[],
            first_direct_url=None,
        )
        
        assert result["delivery_links"] == []
        assert result["dropbox_urls"] == []
        assert result["dropbox_first_url"] is None
    
    @pytest.mark.unit
    def test_build_with_none_values(self):
        """Test payload avec valeurs None"""
        result = payloads.build_custom_webhook_payload(
            email_id="12345",
            subject=None,
            date_received=None,
            sender=None,
            body_preview=None,
            full_email_content=None,
            delivery_links=None,
            first_direct_url=None,
        )
        
        assert result["microsoft_graph_email_id"] == "12345"
        assert result["subject"] is None
        assert result["receivedDateTime"] is None
        assert result["sender_address"] is None
        assert result["bodyPreview"] is None
        assert result["email_content"] is None
        assert result["delivery_links"] is None
        assert result["dropbox_urls"] == []
        assert result["dropbox_first_url"] is None


class TestBuildDesaboMakePayload:
    """Tests pour build_desabo_make_payload()"""
    
    @pytest.mark.unit
    def test_build_complete_desabo_payload(self):
        """Test construction d'un payload DESABO complet"""
        result = payloads.build_desabo_make_payload(
            subject="Désabonnement demandé",
            full_email_content="Contenu complet de l'email",
            sender_email="sender@example.com",
            time_start_payload="09:00",
            time_end_payload="17:00",
        )
        
        assert result["detector"] == "desabonnement_journee_tarifs"
        assert result["email_content"] == "Contenu complet de l'email"
        assert result["Text"] == "Contenu complet de l'email"
        assert result["Subject"] == "Désabonnement demandé"
        assert result["Sender"]["email"] == "sender@example.com"
        assert result["webhooks_time_start"] == "09:00"
        assert result["webhooks_time_end"] == "17:00"
    
    @pytest.mark.unit
    def test_build_desabo_with_none_sender(self):
        """Test payload DESABO avec sender None"""
        result = payloads.build_desabo_make_payload(
            subject="Test",
            full_email_content="Content",
            sender_email=None,
            time_start_payload="09:00",
            time_end_payload="17:00",
        )
        
        assert result["Sender"] is None
    
    @pytest.mark.unit
    def test_build_desabo_with_none_values(self):
        """Test payload DESABO avec valeurs None"""
        result = payloads.build_desabo_make_payload(
            subject=None,
            full_email_content=None,
            sender_email=None,
            time_start_payload=None,
            time_end_payload=None,
        )
        
        assert result["detector"] == "desabonnement_journee_tarifs"
        assert result["Subject"] is None
        assert result["email_content"] is None
        assert result["Text"] is None
        assert result["Sender"] is None
        assert result["webhooks_time_start"] is None
        assert result["webhooks_time_end"] is None
    
    @pytest.mark.unit
    def test_build_desabo_text_alias(self):
        """Test que le champ 'Text' est un alias de 'email_content'"""
        content = "Contenu de test"
        result = payloads.build_desabo_make_payload(
            subject="Test",
            full_email_content=content,
            sender_email="test@example.com",
            time_start_payload="09:00",
            time_end_payload="17:00",
        )
        
        assert result["email_content"] == content
        assert result["Text"] == content
        assert result["email_content"] == result["Text"]
