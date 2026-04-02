"""Nextcloud WebDAV integration for mascarade.

Sync datasets, models, and training artifacts via Nextcloud.
Uses WebDAV protocol — works with any Nextcloud instance.
"""

import os
from pathlib import Path
from typing import Any

import httpx

class NextcloudClient:
    """Nextcloud WebDAV client for mascarade data management."""

    def __init__(
        self,
        url: str = "",
        username: str = "",
        password: str = "",
        base_path: str = "/mascarade",
    ):
        self.url = url or os.environ.get("NEXTCLOUD_URL", "https://cloud.saillant.cc")
        self.username = username or os.environ.get("NEXTCLOUD_USER", "")
        self.password = password or os.environ.get("NEXTCLOUD_PASSWORD", "")
        self.base_path = base_path
        self.webdav_url = f"{self.url}/remote.php/dav/files/{self.username}"

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.username and self.password)

    def _health_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        host_header = os.environ.get("NEXTCLOUD_HOST_HEADER", "").strip()
        if host_header:
            headers["Host"] = host_header
        return headers

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.webdav_url}{self.base_path}/{path}".rstrip("/")
        return httpx.request(
            method, url,
            auth=(self.username, self.password),
            timeout=60,
            **kwargs,
        )

    def healthcheck(self) -> dict[str, Any]:
        """Check if Nextcloud is reachable on this deployment.

        `status.php` is the preferred probe, but some Tower deployments only
        validate correctly through the authenticated WebDAV endpoint.
        """

        headers = self._health_headers()
        status_url = os.environ.get("NEXTCLOUD_HEALTHCHECK_URL", f"{self.url}/status.php")
        try:
            response = httpx.get(status_url, headers=headers, timeout=10, follow_redirects=True)
            if response.status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                return {
                    "ok": True,
                    "probe": "status.php",
                    "status_code": response.status_code,
                    "url": status_url,
                    "payload": payload,
                }
        except httpx.HTTPError as exc:
            status_error = str(exc)
        else:
            status_error = f"unexpected status {response.status_code}"

        dav_url = f"{self.url}/remote.php/dav/files/{self.username}/"
        try:
            dav_response = httpx.request(
                "PROPFIND",
                dav_url,
                auth=(self.username, self.password),
                headers={**headers, "Depth": "0"},
                timeout=10,
            )
            return {
                "ok": dav_response.status_code == 207,
                "probe": "webdav",
                "status_code": dav_response.status_code,
                "url": dav_url,
                "detail": "authenticated WebDAV probe",
                "status_error": status_error,
            }
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "probe": "webdav",
                "status_code": 0,
                "url": dav_url,
                "detail": str(exc),
                "status_error": status_error,
            }

    def mkdir(self, path: str) -> bool:
        """Create directory on Nextcloud."""
        r = self._request("MKCOL", path)
        return r.status_code in (201, 405)  # 405 = already exists

    def upload(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to Nextcloud."""
        with open(local_path, "rb") as f:
            r = self._request("PUT", remote_path, content=f.read())
        return r.status_code in (200, 201, 204)

    def download(self, remote_path: str, local_path: str) -> bool:
        """Download a file from Nextcloud."""
        r = self._request("GET", remote_path)
        if r.status_code == 200:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(r.content)
            return True
        return False

    def list_dir(self, path: str = "") -> list[str]:
        """List files in a Nextcloud directory."""
        r = self._request("PROPFIND", path, headers={"Depth": "1"})
        if r.status_code != 207:
            return []
        # Parse WebDAV XML response
        import xml.etree.ElementTree as ET
        tree = ET.fromstring(r.text)
        ns = {"d": "DAV:"}
        files = []
        for resp in tree.findall("d:response", ns):
            href = resp.find("d:href", ns)
            if href is not None:
                name = href.text.split("/")[-1] or href.text.split("/")[-2]
                if name:
                    files.append(name)
        return files[1:]  # Skip the directory itself

    def sync_datasets(self, local_dir: str, remote_dir: str = "datasets") -> dict:
        """Sync local dataset directory to Nextcloud."""
        self.mkdir(remote_dir)
        synced = []
        failed = []
        for fn in os.listdir(local_dir):
            if not fn.endswith(".jsonl"):
                continue
            local = os.path.join(local_dir, fn)
            remote = f"{remote_dir}/{fn}"
            if self.upload(local, remote):
                synced.append(fn)
            else:
                failed.append(fn)
        return {"synced": synced, "failed": failed}

    def sync_models(self, runs_dir: str, remote_dir: str = "models") -> dict:
        """Sync trained model manifests and LoRA adapters to Nextcloud."""
        self.mkdir(remote_dir)
        synced = []
        for run_dir in Path(runs_dir).iterdir():
            if not run_dir.is_dir():
                continue
            manifest = run_dir / "manifest.json"
            if not manifest.exists():
                continue
            # Upload manifest
            model_name = run_dir.name
            self.mkdir(f"{remote_dir}/{model_name}")
            self.upload(str(manifest), f"{remote_dir}/{model_name}/manifest.json")
            # Upload LoRA adapter if exists
            lora_dir = run_dir / "lora"
            if lora_dir.exists():
                self.mkdir(f"{remote_dir}/{model_name}/lora")
                for f in lora_dir.iterdir():
                    if f.is_file():
                        self.upload(str(f), f"{remote_dir}/{model_name}/lora/{f.name}")
            synced.append(model_name)
        return {"synced": synced}

    def import_to_argilla(self, argilla_url: str, api_key: str, remote_dir: str = "datasets") -> dict:
        """Download datasets from Nextcloud and import to Argilla."""
        import tempfile
        files = self.list_dir(remote_dir)
        imported = []
        for fn in files:
            if not fn.endswith(".jsonl"):
                continue
            with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
                if self.download(f"{remote_dir}/{fn}", tmp.name):
                    imported.append(fn)
        return {"imported": imported}
