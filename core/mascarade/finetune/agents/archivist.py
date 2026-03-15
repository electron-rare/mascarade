"""Archivist agent — versions models and datasets on HuggingFace Hub."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.archivist")


@dataclass
class ArtifactVersion:
    repo_id: str
    version: int
    commit_hash: str = ""
    url: str = ""


class ArchivistAgent:
    """Versions and publishes fine-tuning artifacts to HuggingFace Hub.

    Manages the naming convention clemsail/mascarade-{domain}-v{n}.
    Tracks versions in the local registry.

    P2P capability: ft-archive
    """

    def __init__(self, *, hf_token: str | None = None, namespace: str = "clemsail"):
        self.hf_token = hf_token
        self.namespace = namespace

    async def push_dataset(
        self,
        local_path: Path | str,
        domain: str,
        *,
        version: int | None = None,
        private: bool = False,
    ) -> ArtifactVersion:
        """Push a dataset directory or file to HuggingFace Hub."""
        from huggingface_hub import HfApi
        api = HfApi(token=self.hf_token)

        if version is None:
            version = await asyncio.to_thread(self._next_version, api, "dataset", domain)

        repo_id = f"{self.namespace}/mascarade-{domain}-v{version}"
        await asyncio.to_thread(api.create_repo, repo_id, repo_type="dataset", private=private, exist_ok=True)

        local_path = Path(local_path)
        if local_path.is_dir():
            await asyncio.to_thread(api.upload_folder, folder_path=str(local_path), repo_id=repo_id, repo_type="dataset")
        else:
            await asyncio.to_thread(api.upload_file,
                path_or_fileobj=str(local_path),
                path_in_repo=local_path.name,
                repo_id=repo_id,
                repo_type="dataset",
            )

        info = await asyncio.to_thread(api.dataset_info, repo_id)
        result = ArtifactVersion(
            repo_id=repo_id,
            version=version,
            commit_hash=info.sha or "",
            url=f"https://huggingface.co/datasets/{repo_id}",
        )
        logger.info("Pushed dataset %s → %s", local_path, result.url)
        return result

    async def push_model(
        self,
        local_path: Path | str,
        task: str,
        size_label: str,
        *,
        version: int | None = None,
        private: bool = False,
        model_card: str = "",
    ) -> ArtifactVersion:
        """Push a model directory to HuggingFace Hub."""
        from huggingface_hub import HfApi
        api = HfApi(token=self.hf_token)

        if version is None:
            version = await asyncio.to_thread(self._next_version, api, "model", f"{task}-{size_label}")

        repo_id = f"{self.namespace}/mascarade-{task}-{size_label}-v{version}"
        await asyncio.to_thread(api.create_repo, repo_id, repo_type="model", private=private, exist_ok=True)

        local_path = Path(local_path)
        if local_path.is_dir():
            await asyncio.to_thread(api.upload_folder, folder_path=str(local_path), repo_id=repo_id, repo_type="model")
        else:
            await asyncio.to_thread(api.upload_file,
                path_or_fileobj=str(local_path),
                path_in_repo=local_path.name,
                repo_id=repo_id,
                repo_type="model",
            )

        if model_card:
            await asyncio.to_thread(api.upload_file,
                path_or_fileobj=model_card.encode(),
                path_in_repo="README.md",
                repo_id=repo_id,
                repo_type="model",
            )

        info = await asyncio.to_thread(api.model_info, repo_id)
        result = ArtifactVersion(
            repo_id=repo_id,
            version=version,
            commit_hash=info.sha or "",
            url=f"https://huggingface.co/{repo_id}",
        )
        logger.info("Pushed model %s → %s", local_path, result.url)
        return result

    def _next_version(self, api, repo_type: str, name_prefix: str) -> int:
        """Find the next version number by checking existing repos."""
        try:
            if repo_type == "dataset":
                repos = api.list_datasets(author=self.namespace, search=f"mascarade-{name_prefix}")
            else:
                repos = api.list_models(author=self.namespace, search=f"mascarade-{name_prefix}")

            max_v = 0
            for r in repos:
                parts = r.id.rsplit("-v", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    max_v = max(max_v, int(parts[1]))
            return max_v + 1
        except Exception:
            return 1
