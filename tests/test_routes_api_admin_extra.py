"""
Extra integration tests for routes/api_admin.py
"""
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.integration
def test_restart_server_is_mocked(authenticated_flask_client):
    with patch('routes.api_admin.subprocess.Popen') as mock_popen:
        r = authenticated_flask_client.post('/api/restart_server')
        assert r.status_code == 200
        mock_popen.assert_called()


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.integration
def test_presence_webhook_missing_url_returns_400(authenticated_flask_client, monkeypatch):
    pass


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.integration
def test_presence_webhook_sends_when_url_configured(authenticated_flask_client, monkeypatch):
    pass


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.integration
def test_presence_webhook_returns_500_on_send_failure(authenticated_flask_client, monkeypatch):
    pass


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.integration
def test_presence_webhook_returns_500_on_404(authenticated_flask_client, monkeypatch):
    pass


@pytest.mark.skip(reason="presence feature removed")
@pytest.mark.integration
def test_presence_webhook_presence_false_uses_false_url(authenticated_flask_client, monkeypatch):
    pass

@pytest.mark.integration
def test_check_emails_and_download_503_on_invalid_config(authenticated_flask_client, monkeypatch):
    # Mock ConfigService to report invalid config
    with patch('routes.api_admin._config_service.is_email_config_valid', return_value=False):
        r = authenticated_flask_client.post('/api/check_emails_and_download')
        assert r.status_code == 503


@pytest.mark.integration
def test_check_emails_and_download_202_with_thread_mock(authenticated_flask_client, monkeypatch):
    from routes import api_admin
    # Provide valid config values
    monkeypatch.setattr(api_admin, 'EMAIL_ADDRESS', 'a@b.c', raising=False)
    monkeypatch.setattr(api_admin, 'EMAIL_PASSWORD', 'x', raising=False)
    monkeypatch.setattr(api_admin, 'IMAP_SERVER', 'imap.local', raising=False)
    monkeypatch.setattr(api_admin, 'SENDER_LIST_FOR_POLLING', ['a@b.c'], raising=False)
    monkeypatch.setattr(api_admin, 'WEBHOOK_URL', 'https://example.com', raising=False)

    # Patch threading.Thread to avoid real thread start
    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target; self.daemon = daemon
        def start(self):
            # no-op
            pass
    monkeypatch.setattr(api_admin, 'threading', type('T', (), {'Thread': FakeThread}))

    # Also patch orchestrator call to avoid side effects
    with patch('routes.api_admin.email_orchestrator.check_new_emails_and_trigger_webhook') as mock_run:
        r = authenticated_flask_client.post('/api/check_emails_and_download')
        assert r.status_code == 202
        # Thread start no-op; orchestrator not necessarily called in test (start would be no-op), so no assertion


@pytest.mark.integration
def test_restart_server_uses_custom_restart_cmd(authenticated_flask_client, monkeypatch):
    # Ensure custom env var is used
    monkeypatch.setenv('RESTART_CMD', 'echo custom-restart')
    with patch('routes.api_admin.subprocess.Popen') as mock_popen:
        r = authenticated_flask_client.post('/api/restart_server')
        assert r.status_code == 200
        # Check the command string contains our custom command
        args, kwargs = mock_popen.call_args
        # args[0] is the list ["/bin/bash","-lc", "sleep 1; echo custom-restart"]
        assert any("custom-restart" in str(part) for part in args[0])
