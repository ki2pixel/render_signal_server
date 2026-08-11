"""
Tests pour la protection contre les URLs webhook placeholder (example.com, etc.)
"""
import pytest
from unittest.mock import MagicMock, patch

from utils.validators import is_placeholder_webhook_url


@pytest.mark.unit
class TestIsPlaceholderWebhookUrl:
    def test_returns_true_for_example_dot_com(self):
        # Given: an example.com URL
        url = "https://example.com/hook"
        # When: checking placeholder status
        result = is_placeholder_webhook_url(url)
        # Then: it is a placeholder
        assert result is True

    def test_returns_true_for_example_dot_net_and_subdomains(self):
        # Given: example.net and subdomain of example.com
        # When: checking placeholder status
        # Then: both are placeholders
        assert is_placeholder_webhook_url("https://example.net/endpoint") is True
        assert is_placeholder_webhook_url("https://sub.example.com/x") is True

    def test_returns_true_for_empty_and_none(self):
        # Given: empty or None URL
        # When: checking placeholder status
        # Then: treated as placeholder (invalid target)
        assert is_placeholder_webhook_url("") is True
        assert is_placeholder_webhook_url(None) is True

    def test_returns_false_for_legitimate_url(self):
        # Given: a real webhook URL
        url = "https://webhook.kidpixel.fr/index.php"
        # When: checking placeholder status
        result = is_placeholder_webhook_url(url)
        # Then: it is not a placeholder
        assert result is False

    def test_returns_false_for_make_dot_com(self):
        # Given: a Make.com webhook URL
        url = "https://hook.eu2.make.com/abc123"
        # When: checking placeholder status
        result = is_placeholder_webhook_url(url)
        # Then: it is not a placeholder
        assert result is False


@pytest.mark.unit
class TestIngressWebhookUrlFallback:
    def _make_ingress(self):
        from services.ingress_service import IngressService
        service = IngressService()
        service._logger = MagicMock()
        return service

    def test_placeholder_config_url_falls_back_to_env_var(
        self, monkeypatch
    ):
        # Given: stored config has a placeholder URL, env var has a real one
        monkeypatch.setattr(
            "services.ingress_service.email_orchestrator._get_webhook_config_dict",
            lambda: {"webhook_url": "https://example.com/hook"},
        )
        monkeypatch.setattr(
            "services.ingress_service.settings.WEBHOOK_URL",
            "https://webhook.kidpixel.fr/index.php",
        )
        service = self._make_ingress()
        with patch(
            "services.ingress_service.email_orchestrator.send_custom_webhook_flow"
        ) as mock_flow:
            mock_flow.return_value = False
            # When: sending an ingress webhook
            result, status = service._send_ingress_webhook(
                email_id="abc",
                subject="Test",
                payload_for_webhook={},
                delivery_links=[],
                dedup_service=MagicMock(),
            )
            # Then: the env var URL is used
            assert status == 200
            assert result["success"] is True
            sent_url = mock_flow.call_args.kwargs["webhook_url"]
            assert sent_url == "https://webhook.kidpixel.fr/index.php"

    def test_placeholder_config_url_with_placeholder_env_falls_back_to_default(
        self, monkeypatch
    ):
        # Given: stored config AND env var are placeholders
        monkeypatch.setattr(
            "services.ingress_service.email_orchestrator._get_webhook_config_dict",
            lambda: {"webhook_url": "https://example.com/hook"},
        )
        monkeypatch.setattr(
            "services.ingress_service.settings.WEBHOOK_URL",
            "https://example.com/hook",
        )
        service = self._make_ingress()
        with patch(
            "services.ingress_service.email_orchestrator.send_custom_webhook_flow"
        ) as mock_flow:
            mock_flow.return_value = False
            # When: sending an ingress webhook
            result, status = service._send_ingress_webhook(
                email_id="abc",
                subject="Test",
                payload_for_webhook={},
                delivery_links=[],
                dedup_service=MagicMock(),
            )
            # Then: the default webhook URL is used
            assert status == 200
            assert result["success"] is True
            sent_url = mock_flow.call_args.kwargs["webhook_url"]
            assert sent_url == "https://webhook.kidpixel.fr/index.php"

    def test_empty_config_url_falls_back_to_env_var(self, monkeypatch):
        # Given: stored config has no webhook_url, env var has a real one
        monkeypatch.setattr(
            "services.ingress_service.email_orchestrator._get_webhook_config_dict",
            lambda: {},
        )
        monkeypatch.setattr(
            "services.ingress_service.settings.WEBHOOK_URL",
            "https://webhook.kidpixel.fr/index.php",
        )
        service = self._make_ingress()
        with patch(
            "services.ingress_service.email_orchestrator.send_custom_webhook_flow"
        ) as mock_flow:
            mock_flow.return_value = False
            # When: sending an ingress webhook
            result, status = service._send_ingress_webhook(
                email_id="abc",
                subject="Test",
                payload_for_webhook={},
                delivery_links=[],
                dedup_service=MagicMock(),
            )
            # Then: the env var URL is used
            assert status == 200
            assert result["success"] is True
            sent_url = mock_flow.call_args.kwargs["webhook_url"]
            assert sent_url == "https://webhook.kidpixel.fr/index.php"

    def test_real_config_url_is_used_directly(self, monkeypatch):
        # Given: stored config has a legitimate URL (env var differs)
        monkeypatch.setattr(
            "services.ingress_service.email_orchestrator._get_webhook_config_dict",
            lambda: {"webhook_url": "https://webhook.kidpixel.fr/index.php"},
        )
        monkeypatch.setattr(
            "services.ingress_service.settings.WEBHOOK_URL",
            "https://other.example.com",
        )
        service = self._make_ingress()
        with patch(
            "services.ingress_service.email_orchestrator.send_custom_webhook_flow"
        ) as mock_flow:
            mock_flow.return_value = False
            # When: sending an ingress webhook
            result, status = service._send_ingress_webhook(
                email_id="abc",
                subject="Test",
                payload_for_webhook={},
                delivery_links=[],
                dedup_service=MagicMock(),
            )
            # Then: the stored legitimate URL is used
            assert status == 200
            assert result["success"] is True
            sent_url = mock_flow.call_args.kwargs["webhook_url"]
            assert sent_url == "https://webhook.kidpixel.fr/index.php"
