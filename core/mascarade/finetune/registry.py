"""Local registry for fine-tuning artifacts (models, datasets, runs)."""

from __future__ import annotations

import fcntl
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger("mascarade.finetune.registry")

DEFAULT_REGISTRY_PATH = Path.home() / ".mascarade" / "finetune" / "registry.json"


@dataclass
class ModelEntry:
    model_id: str
    source: str  # "huggingface", "local", "finetuned"
    task: str
    size_gb: float
    license: str = ""
    downloads: int = 0
    likes: int = 0
    quantizations: list[str] = field(default_factory=list)
    paper_refs: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    added_at: float = field(default_factory=time.time)


@dataclass
class DatasetEntry:
    dataset_id: str
    source: str  # "huggingface", "synthetic", "local"
    domain: str
    rows: int = 0
    format: str = ""  # "jsonl", "parquet", "csv"
    license: str = ""
    languages: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    added_at: float = field(default_factory=time.time)


@dataclass
class RunEntry:
    run_id: str
    base_model: str
    dataset: str
    method: str  # "lora", "qlora", "full", "dpo"
    node: str  # peer_id of training node
    status: str = "pending"  # pending, training, completed, failed
    metrics: dict = field(default_factory=dict)
    output_model: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class FinetuneRegistry:
    """Persisted JSON registry of fine-tuning artifacts."""

    def __init__(self, path: Path | str = DEFAULT_REGISTRY_PATH):
        self.path = Path(path)
        self.models: dict[str, ModelEntry] = {}
        self.datasets: dict[str, DatasetEntry] = {}
        self.runs: dict[str, RunEntry] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                for k, v in data.get("models", {}).items():
                    self.models[k] = ModelEntry(**v)
                for k, v in data.get("datasets", {}).items():
                    self.datasets[k] = DatasetEntry(**v)
                for k, v in data.get("runs", {}).items():
                    self.runs[k] = RunEntry(**v)
                logger.info(
                    "Loaded registry: %d models, %d datasets, %d runs",
                    len(self.models),
                    len(self.datasets),
                    len(self.runs),
                )
            except Exception:
                logger.exception("Failed to load registry from %s", self.path)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "models": {k: asdict(v) for k, v in self.models.items()},
            "datasets": {k: asdict(v) for k, v in self.datasets.items()},
            "runs": {k: asdict(v) for k, v in self.runs.items()},
        }
        # Atomic write with file lock to prevent concurrent corruption
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2, default=str)
            f.flush()
        tmp_path.rename(self.path)
        logger.debug("Saved registry to %s", self.path)

    def add_model(self, entry: ModelEntry):
        self.models[entry.model_id] = entry
        self.save()

    def add_dataset(self, entry: DatasetEntry):
        self.datasets[entry.dataset_id] = entry
        self.save()

    def add_run(self, entry: RunEntry):
        self.runs[entry.run_id] = entry
        self.save()

    def best_model_for_task(
        self, task: str, max_size_gb: float = 4.0
    ) -> ModelEntry | None:
        candidates = [
            m
            for m in self.models.values()
            if m.task == task and m.size_gb <= max_size_gb
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda m: (m.quality_score, m.downloads))
