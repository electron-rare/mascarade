"""Smoke tests for the CPU fine-tuning script (finetune/train_cpu.py).

These tests validate the control flow and key invariants without running a real
training workload.
"""

from __future__ import annotations

import json
import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

TRAIN_CPU_PATH = Path(__file__).resolve().parents[2] / "finetune" / "train_cpu.py"


class _FakeDataset:
    def __init__(self, texts: list[str]):
        self._texts = texts

    @classmethod
    def from_dict(cls, payload: dict[str, list[str]]):
        return cls(payload.get("text", []))

    def __len__(self):
        return len(self._texts)

    def train_test_split(self, test_size: int, seed: int):  # noqa: ARG002
        train_len = max(1, len(self._texts) - test_size)
        test_len = max(1, test_size)

        class _Split:
            def map(self, func, **kwargs):  # noqa: ARG002
                _ = func({"text": ["sample"]})
                return {
                    "train": [{"input_ids": [1, 2], "attention_mask": [1, 1]}]
                    * train_len,
                    "test": [{"input_ids": [1, 2], "attention_mask": [1, 1]}]
                    * test_len,
                }

        return _Split()


class _FakeModel:
    def __init__(self):
        self.config = SimpleNamespace(use_cache=True)
        self.saved_paths: list[str] = []
        self.device = None

    def to(self, device: str):
        self.device = device

    def print_trainable_parameters(self):
        return None

    def save_pretrained(self, path: str):
        self.saved_paths.append(path)
        os.makedirs(path, exist_ok=True)
        Path(path, "adapter_config.json").write_text("{}", encoding="utf-8")


class _FakeTokenizer:
    def __init__(self):
        self.pad_token = None
        self.eos_token = "<eos>"
        self.saved_paths: list[str] = []

    def __call__(self, texts, truncation, max_length, padding):  # noqa: ARG002
        if isinstance(texts, str):
            texts = [texts]
        return {
            "input_ids": [[1, 2, 3] for _ in texts],
            "attention_mask": [[1, 1, 1] for _ in texts],
        }

    def save_pretrained(self, path: str):
        self.saved_paths.append(path)
        os.makedirs(path, exist_ok=True)
        Path(path, "tokenizer_config.json").write_text("{}", encoding="utf-8")


class _FakeTrainer:
    def __init__(self, model, args, train_dataset, eval_dataset, data_collator):  # noqa: ARG002
        self.model = model
        self.args = args
        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset
        self.data_collator = data_collator
        self.removed_callbacks: list[object] = []

    def remove_callback(self, callback):
        self.removed_callbacks.append(callback)

    def train(self):
        return SimpleNamespace(training_loss=0.1234)


def _install_fake_train_cpu_modules(monkeypatch) -> None:
    llm_paths = ModuleType("llm_paths")
    llm_paths.configure_hf_env = lambda: None
    monkeypatch.setitem(sys.modules, "llm_paths", llm_paths)

    dataset_quality = ModuleType("dataset_quality")

    class _DatasetQualityError(Exception):
        pass

    dataset_quality.DatasetQualityError = _DatasetQualityError
    dataset_quality.enforce_dataset_quality = lambda rows, label, ids_fixed: {  # noqa: ARG005
        "warnings": []
    }
    dataset_quality.summarize_quality_report = lambda report: "ok"  # noqa: ARG005
    monkeypatch.setitem(sys.modules, "dataset_quality", dataset_quality)

    runtime_compat = ModuleType("runtime_compat")
    runtime_compat.disable_broken_torchvision = lambda: None
    monkeypatch.setitem(sys.modules, "runtime_compat", runtime_compat)

    sharegpt_utils = ModuleType("sharegpt_utils")
    sharegpt_utils.ensure_row_ids_with_stats = lambda rows, label: (rows, 0)  # noqa: ARG005
    sharegpt_utils.load_jsonl = lambda path: []  # noqa: ARG005
    sharegpt_utils.validate_rows = lambda rows: []  # noqa: ARG005
    monkeypatch.setitem(sys.modules, "sharegpt_utils", sharegpt_utils)

    torch_module = ModuleType("torch")
    torch_module.float32 = "float32"
    monkeypatch.setitem(sys.modules, "torch", torch_module)

    datasets_module = ModuleType("datasets")
    datasets_module.Dataset = _FakeDataset
    monkeypatch.setitem(sys.modules, "datasets", datasets_module)

    datasets_utils_logging = ModuleType("datasets.utils.logging")
    datasets_utils_logging.disable_progress_bar = lambda: None
    datasets_utils_logging.enable_progress_bar = lambda: None
    monkeypatch.setitem(sys.modules, "datasets.utils.logging", datasets_utils_logging)

    transformers = ModuleType("transformers")
    transformers.AutoModelForCausalLM = SimpleNamespace(
        from_pretrained=lambda *args, **kwargs: _FakeModel()  # noqa: ARG005
    )
    transformers.AutoTokenizer = SimpleNamespace(
        from_pretrained=lambda *args, **kwargs: _FakeTokenizer()  # noqa: ARG005
    )
    transformers.TrainingArguments = lambda **kwargs: SimpleNamespace(**kwargs)
    transformers.Trainer = _FakeTrainer
    transformers.DataCollatorForLanguageModeling = lambda tokenizer, mlm: {  # noqa: ARG005
        "tokenizer": tokenizer,
        "mlm": mlm,
    }
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    trainer_callback = ModuleType("transformers.trainer_callback")

    class _PrinterCallback:
        pass

    trainer_callback.PrinterCallback = _PrinterCallback
    monkeypatch.setitem(sys.modules, "transformers.trainer_callback", trainer_callback)

    transformers_utils_logging = ModuleType("transformers.utils.logging")
    transformers_utils_logging.set_verbosity_error = lambda: None
    transformers_utils_logging.set_verbosity_info = lambda: None
    transformers_utils_logging.set_verbosity_warning = lambda: None
    transformers_utils = ModuleType("transformers.utils")
    transformers_utils.logging = transformers_utils_logging
    monkeypatch.setitem(sys.modules, "transformers.utils", transformers_utils)
    monkeypatch.setitem(sys.modules, "transformers.utils.logging", transformers_utils_logging)

    peft_module = ModuleType("peft")
    peft_module.LoraConfig = lambda **kwargs: SimpleNamespace(**kwargs)
    peft_module.get_peft_model = lambda model, cfg: model  # noqa: ARG005
    monkeypatch.setitem(sys.modules, "peft", peft_module)


def _load_train_cpu_module(monkeypatch):
    _install_fake_train_cpu_modules(monkeypatch)
    spec = spec_from_file_location("test_train_cpu_module", TRAIN_CPU_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_train_domain_returns_false_when_dataset_missing(monkeypatch, tmp_path):
    module = _load_train_cpu_module(monkeypatch)
    missing_path = tmp_path / "missing.jsonl"

    ok = module.train_domain(
        "stm32",
        epochs=1,
        max_samples=4,
        dataset_path=str(missing_path),
        output_dir=str(tmp_path / "out"),
        quiet=True,
    )

    assert ok is False


def test_train_domain_returns_false_when_dataset_invalid(monkeypatch, tmp_path):
    module = _load_train_cpu_module(monkeypatch)
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(module, "load_jsonl", lambda _path: [{"dummy": True}])
    monkeypatch.setattr(module, "ensure_row_ids_with_stats", lambda rows, label: (rows, 0))
    monkeypatch.setattr(module, "validate_rows", lambda rows: ["invalid row"])

    ok = module.train_domain(
        "stm32",
        epochs=1,
        max_samples=4,
        dataset_path=str(dataset_path),
        output_dir=str(tmp_path / "out"),
        quiet=True,
    )

    assert ok is False


def test_train_domain_success_writes_artifacts(monkeypatch, tmp_path):
    module = _load_train_cpu_module(monkeypatch)
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text("{}\n", encoding="utf-8")
    out_dir = tmp_path / "model_out"

    monkeypatch.setattr(module, "load_jsonl", lambda _path: [{"dummy": True}] * 4)
    monkeypatch.setattr(module, "ensure_row_ids_with_stats", lambda rows, label: (rows, 0))
    monkeypatch.setattr(module, "validate_rows", lambda rows: [])
    monkeypatch.setattr(module, "enforce_dataset_quality", lambda rows, label, ids_fixed: {"warnings": []})
    monkeypatch.setattr(module, "load_sharegpt_jsonl", lambda path, max_samples, model_name: ["a", "b", "c", "d"])

    ok = module.train_domain(
        "stm32",
        epochs=1,
        max_samples=4,
        max_seq_len=64,
        dataset_path=str(dataset_path),
        output_dir=str(out_dir),
        quiet=True,
    )

    assert ok is True
    assert (out_dir / "adapter").exists()
    info_path = out_dir / "training_info.json"
    assert info_path.exists()
    info = json.loads(info_path.read_text(encoding="utf-8"))
    assert info["device"] == "cpu"
    assert info["samples"] == 4
    assert info["epochs"] == 1


def test_main_forces_cpu_and_passes_cli_args(monkeypatch, tmp_path):
    module = _load_train_cpu_module(monkeypatch)

    captured: list[dict] = []

    def _fake_train_domain(
        domain,
        epochs,
        max_samples,
        max_seq_len,
        model_name,
        dataset_path,
        output_dir,
        verbose,
        quiet,
        tokenize_workers,
    ):
        captured.append(
            {
                "domain": domain,
                "epochs": epochs,
                "max_samples": max_samples,
                "max_seq_len": max_seq_len,
                "model_name": model_name,
                "dataset_path": dataset_path,
                "output_dir": output_dir,
                "verbose": verbose,
                "quiet": quiet,
                "tokenize_workers": tokenize_workers,
            }
        )
        return True

    monkeypatch.setattr(module, "train_domain", _fake_train_domain)

    dataset_path = tmp_path / "dataset.jsonl"
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_cpu.py",
            "stm32",
            "--epochs",
            "1",
            "--max-samples",
            "4",
            "--seq-len",
            "128",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(out_dir),
            "--quiet",
            "--tokenize-workers",
            "2",
        ],
    )

    module.main()

    assert os.environ["CUDA_VISIBLE_DEVICES"] == ""
    assert len(captured) == 1
    assert captured[0]["domain"] == "stm32"
    assert captured[0]["epochs"] == 1
    assert captured[0]["max_samples"] == 4
    assert captured[0]["max_seq_len"] == 128
    assert captured[0]["dataset_path"] == str(dataset_path)
    assert captured[0]["output_dir"] == str(out_dir)
    assert captured[0]["quiet"] is True
    assert captured[0]["tokenize_workers"] == 2
