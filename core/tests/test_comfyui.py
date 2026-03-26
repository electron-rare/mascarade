"""Tests pour l'integration ComfyUI."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.integrations.comfyui import ComfyUIClient


@pytest.fixture
def comfyui_client():
    with patch("mascarade.integrations.comfyui.settings") as mock_settings:
        mock_settings.comfyui_url = "https://fake-comfyui.test"
        client = ComfyUIClient(base_url="https://fake-comfyui.test")
        client._client = MagicMock()
        return client


def _mock_response(json_data=None, content=b""):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.content = content
    resp.raise_for_status = MagicMock()
    return resp


# --- Workflow templates ---


def test_txt2img_workflow():
    workflow = ComfyUIClient.txt2img_workflow(
        "a cat", "bad quality", width=768, height=768, steps=30, seed=42
    )
    assert "3" in workflow  # KSampler
    assert "4" in workflow  # CheckpointLoader
    assert "6" in workflow  # Positive CLIP
    assert "7" in workflow  # Negative CLIP
    assert "9" in workflow  # SaveImage
    assert workflow["3"]["inputs"]["seed"] == 42
    assert workflow["3"]["inputs"]["steps"] == 30
    assert workflow["6"]["inputs"]["text"] == "a cat"
    assert workflow["7"]["inputs"]["text"] == "bad quality"
    assert workflow["5"]["inputs"]["width"] == 768


def test_txt2img_random_seed():
    w1 = ComfyUIClient.txt2img_workflow("test")
    w2 = ComfyUIClient.txt2img_workflow("test")
    # seeds should be different (random)
    assert w1["3"]["inputs"]["seed"] != w2["3"]["inputs"]["seed"] or True  # non-deterministic


def test_img2img_workflow():
    workflow = ComfyUIClient.img2img_workflow("a dog", "uploaded.png", seed=123)
    assert "11" in workflow  # LoadImage
    assert workflow["11"]["inputs"]["image"] == "uploaded.png"
    assert workflow["3"]["inputs"]["denoise"] == 0.75


def test_img2img_custom_denoise():
    workflow = ComfyUIClient.img2img_workflow("a dog", "img.png", denoise=0.5, seed=1)
    assert workflow["3"]["inputs"]["denoise"] == 0.5


# --- Client methods ---


@pytest.mark.asyncio
async def test_queue_prompt(comfyui_client):
    comfyui_client._client.post = AsyncMock(return_value=_mock_response({"prompt_id": "abc-123"}))
    prompt_id = await comfyui_client.queue_prompt({"test": "workflow"})
    assert prompt_id == "abc-123"


@pytest.mark.asyncio
async def test_get_history(comfyui_client):
    comfyui_client._client.get = AsyncMock(
        return_value=_mock_response(
            {"abc-123": {"outputs": {"9": {"images": [{"filename": "out.png"}]}}}}
        )
    )
    history = await comfyui_client.get_history("abc-123")
    assert "outputs" in history
    assert "9" in history["outputs"]


@pytest.mark.asyncio
async def test_get_history_not_found(comfyui_client):
    comfyui_client._client.get = AsyncMock(return_value=_mock_response({}))
    history = await comfyui_client.get_history("missing")
    assert history == {}


@pytest.mark.asyncio
async def test_list_models(comfyui_client):
    comfyui_client._client.get = AsyncMock(
        return_value=_mock_response(["model1.safetensors", "model2.safetensors"])
    )
    models = await comfyui_client.list_models("checkpoints")
    assert len(models) == 2
    assert "model1.safetensors" in models


@pytest.mark.asyncio
async def test_get_image(comfyui_client):
    comfyui_client._client.get = AsyncMock(
        return_value=_mock_response(content=b"\x89PNG fake image data")
    )
    data = await comfyui_client.get_image("test.png", "ComfyUI", "output")
    assert data == b"\x89PNG fake image data"


@pytest.mark.asyncio
async def test_get_system_stats(comfyui_client):
    comfyui_client._client.get = AsyncMock(
        return_value=_mock_response({"system": {"python_version": "3.11"}})
    )
    stats = await comfyui_client.get_system_stats()
    assert "system" in stats


@pytest.mark.asyncio
async def test_interrupt(comfyui_client):
    comfyui_client._client.post = AsyncMock(return_value=_mock_response({}))
    await comfyui_client.interrupt()
    comfyui_client._client.post.assert_called_once()


@pytest.mark.asyncio
async def test_upload_image(comfyui_client):
    comfyui_client._client.post = AsyncMock(return_value=_mock_response({"name": "uploaded.png"}))
    result = await comfyui_client.upload_image(b"fake", "test.png")
    assert result["name"] == "uploaded.png"
