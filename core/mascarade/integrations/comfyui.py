"""Client ComfyUI — generation d'images via Stable Diffusion."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import Any

import httpx

from mascarade.config import settings

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Client pour interagir avec une instance ComfyUI externe."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.comfyui_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        self._client_id = uuid.uuid4().hex

    # --- Infos systeme ---

    async def get_system_stats(self) -> dict[str, Any]:
        """Obtenir les statistiques systeme de ComfyUI."""
        resp = await self._client.get("/system_stats")
        resp.raise_for_status()
        return resp.json()

    async def get_queue_status(self) -> dict[str, Any]:
        """Obtenir le statut de la file d'attente."""
        resp = await self._client.get("/queue")
        resp.raise_for_status()
        return resp.json()

    async def list_models(self, model_type: str = "checkpoints") -> list[str]:
        """Lister les modeles disponibles (checkpoints, loras, vae, etc.)."""
        resp = await self._client.get(f"/models/{model_type}")
        resp.raise_for_status()
        return resp.json()

    async def get_object_info(self) -> dict[str, Any]:
        """Obtenir les specs des noeuds disponibles."""
        resp = await self._client.get("/object_info")
        resp.raise_for_status()
        return resp.json()

    # --- Execution ---

    async def queue_prompt(self, workflow: dict[str, Any]) -> str:
        """Soumettre un workflow et retourner le prompt_id."""
        payload = {"prompt": workflow, "client_id": self._client_id}
        resp = await self._client.post("/prompt", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["prompt_id"]

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        """Obtenir les resultats d'execution d'un prompt."""
        resp = await self._client.get(f"/history/{prompt_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get(prompt_id, {})

    async def wait_for_result(
        self,
        prompt_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Attendre la fin de l'execution et retourner les resultats."""
        elapsed = 0.0
        while elapsed < timeout:
            history = await self.get_history(prompt_id)
            if history and history.get("outputs"):
                return history
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(
            f"ComfyUI: timeout apres {timeout}s en attendant prompt_id={prompt_id}"
        )

    async def interrupt(self) -> None:
        """Interrompre l'execution en cours."""
        resp = await self._client.post("/interrupt")
        resp.raise_for_status()

    # --- Images ---

    @staticmethod
    def _validate_path_component(value: str, name: str) -> str:
        """Validate a path component against traversal attacks."""
        if not value:
            return value
        if ".." in value or "/" in value or "\\" in value or "\0" in value:
            raise ValueError(f"Invalid {name}: path traversal not allowed")
        return value

    async def get_image(
        self, filename: str, subfolder: str = "", image_type: str = "output"
    ) -> bytes:
        """Telecharger une image generee."""
        self._validate_path_component(filename, "filename")
        self._validate_path_component(subfolder, "subfolder")
        self._validate_path_component(image_type, "type")
        params = {"filename": filename, "subfolder": subfolder, "type": image_type}
        resp = await self._client.get("/view", params=params)
        resp.raise_for_status()
        return resp.content

    async def upload_image(
        self, image_data: bytes, filename: str, image_type: str = "input"
    ) -> dict[str, Any]:
        """Uploader une image (pour img2img)."""
        files = {"image": (filename, image_data, "image/png")}
        data = {"type": image_type}
        resp = await self._client.post("/upload/image", files=files, data=data)
        resp.raise_for_status()
        return resp.json()

    # --- Haut niveau ---

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        checkpoint: str | None = None,
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = -1,
    ) -> dict[str, Any]:
        """Generer une image txt2img et attendre le resultat."""
        if checkpoint is None:
            models = await self.list_models("checkpoints")
            checkpoint = models[0] if models else "v1-5-pruned-emaonly.safetensors"

        workflow = self.txt2img_workflow(
            prompt,
            negative_prompt,
            checkpoint=checkpoint,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
        )
        prompt_id = await self.queue_prompt(workflow)
        result = await self.wait_for_result(prompt_id)

        images = []
        for node_output in result.get("outputs", {}).values():
            if "images" in node_output:
                images.extend(node_output["images"])

        return {"prompt_id": prompt_id, "images": images, "status": "completed"}

    # --- Workflow templates ---

    @staticmethod
    def txt2img_workflow(
        prompt: str,
        negative_prompt: str = "",
        *,
        checkpoint: str = "v1-5-pruned-emaonly.safetensors",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = -1,
    ) -> dict[str, Any]:
        """Construire un workflow txt2img standard."""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["4", 1]},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "mascarade", "images": ["8", 0]},
            },
        }

    @staticmethod
    def img2img_workflow(
        prompt: str,
        image_name: str,
        negative_prompt: str = "",
        *,
        checkpoint: str = "v1-5-pruned-emaonly.safetensors",
        steps: int = 20,
        cfg: float = 7.0,
        denoise: float = 0.75,
        seed: int = -1,
    ) -> dict[str, Any]:
        """Construire un workflow img2img standard."""
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": denoise,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["10", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["4", 1]},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "mascarade", "images": ["8", 0]},
            },
            "10": {
                "class_type": "VAEEncode",
                "inputs": {"pixels": ["11", 0], "vae": ["4", 2]},
            },
            "11": {
                "class_type": "LoadImage",
                "inputs": {"image": image_name},
            },
        }

    async def close(self) -> None:
        """Fermer le client HTTP."""
        await self._client.aclose()
