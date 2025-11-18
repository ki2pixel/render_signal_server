"""
Unit/integration tests for routes/dashboard.py to raise coverage ≥70%:
- GET /login (200)
- POST /login invalid credentials -> shows error
- POST /login success with next=... -> redirects to next
- GET /logout when authenticated -> redirects to login
- GET / (dashboard) requires auth (covered elsewhere); here, exercise authenticated path
"""
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.integration
def test_login_page_get(flask_client):
    r = flask_client.get('/login')
    assert r.status_code == 200


@pytest.mark.integration
def test_login_post_invalid_credentials(flask_client):
    # Patch AuthService.create_user_from_credentials to return None (invalid)
    with patch('routes.dashboard._auth_service.create_user_from_credentials', return_value=None):
        r = flask_client.post('/login', data={'username': 'u', 'password': 'p'})
        assert r.status_code == 200
        # Should re-render login with error text
        assert b"Identifiants invalides" in r.data


@pytest.mark.integration
def test_login_post_success_with_next(flask_client):
    # Simulate a valid user object for login_user()
    user = MagicMock()
    user.is_authenticated = True
    user.get_id.return_value = '123'

    with patch('routes.dashboard._auth_service.create_user_from_credentials', return_value=user):
        r = flask_client.post('/login?next=%2Fsomewhere', data={'username': 'ok', 'password': 'ok'})
        # Should redirect to provided next
        assert r.status_code in (302, 303)
        assert '/somewhere' in r.headers.get('Location', '')


@pytest.mark.integration
def test_logout_redirects_to_login(authenticated_flask_client):
    r = authenticated_flask_client.get('/logout')
    # Should redirect to login
    assert r.status_code in (302, 303)
    assert '/login' in r.headers.get('Location', '')


@pytest.mark.integration
def test_dashboard_access_when_authenticated(authenticated_flask_client):
    r = authenticated_flask_client.get('/')
    assert r.status_code == 200
