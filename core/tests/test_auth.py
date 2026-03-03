"""Tests pour l'authentification Bearer token."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def _get_app():
    """Importer l'app après avoir potentiellement mocké les settings."""
    from mascarade.server import app
    return app


def test_health_open_without_auth():
    """Le endpoint /health est accessible sans token, même avec auth activée."""
    with patch("mascarade.auth.settings") as mock_settings:
        mock_settings.mascarade_api_key = "test-secret"
        client = TestClient(_get_app())
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_protected_route_rejects_without_token():
    """Les routes protégées refusent sans token quand auth est activée."""
    with patch("mascarade.auth.settings") as mock_settings:
        mock_settings.mascarade_api_key = "test-secret"
        client = TestClient(_get_app())
        resp = client.get("/providers")
        assert resp.status_code == 401


def test_protected_route_rejects_bad_token():
    """Les routes protégées refusent un mauvais token."""
    with patch("mascarade.auth.settings") as mock_settings:
        mock_settings.mascarade_api_key = "test-secret"
        client = TestClient(_get_app())
        resp = client.get("/providers", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401


def test_protected_route_accepts_valid_token():
    """Les routes protégées acceptent un token valide."""
    with patch("mascarade.auth.settings") as mock_settings:
        mock_settings.mascarade_api_key = "test-secret"
        client = TestClient(_get_app())
        resp = client.get("/providers", headers={"Authorization": "Bearer test-secret"})
        assert resp.status_code == 200


def test_auth_disabled_when_no_key():
    """Quand MASCARADE_API_KEY est vide, tout passe sans token."""
    with patch("mascarade.auth.settings") as mock_settings:
        mock_settings.mascarade_api_key = ""
        client = TestClient(_get_app())
        resp = client.get("/providers")
        assert resp.status_code == 200
