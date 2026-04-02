from unittest.mock import MagicMock, patch

from mascarade.integrations.nextcloud import NextcloudClient


def test_healthcheck_prefers_status_php():
    client = NextcloudClient(url="https://cloud.saillant.cc", username="alice", password="secret")

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"installed": True, "maintenance": False}

    with patch("mascarade.integrations.nextcloud.httpx.get", return_value=response) as mock_get:
        result = client.healthcheck()

    mock_get.assert_called_once()
    assert result["ok"] is True
    assert result["probe"] == "status.php"
    assert result["payload"]["installed"] is True


def test_healthcheck_falls_back_to_webdav_for_tower_style_deployments():
    client = NextcloudClient(url="http://192.168.0.120:8088", username="alice", password="secret")

    status_response = MagicMock()
    status_response.status_code = 400

    dav_response = MagicMock()
    dav_response.status_code = 207

    with (
        patch("mascarade.integrations.nextcloud.httpx.get", return_value=status_response),
        patch("mascarade.integrations.nextcloud.httpx.request", return_value=dav_response) as mock_request,
    ):
        result = client.healthcheck()

    mock_request.assert_called_once()
    assert result["ok"] is True
    assert result["probe"] == "webdav"
    assert result["status_code"] == 207
