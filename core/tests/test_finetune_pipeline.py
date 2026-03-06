"""CLI contract tests for the local fine-tuning pipeline."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


PIPELINE_PATH = Path(__file__).resolve().parents[2] / "finetune" / "pipeline.py"


def _install_fake_training_modules(monkeypatch) -> None:
    runtime_compat = ModuleType("runtime_compat")
    runtime_compat.disable_broken_torchvision = lambda: None
    monkeypatch.setitem(sys.modules, "runtime_compat", runtime_compat)

    torch_module = ModuleType("torch")
    torch_module.float16 = "float16"
    torch_module.cuda = SimpleNamespace(
        empty_cache=lambda: None,
        memory_allocated=lambda: 0,
    )
    monkeypatch.setitem(sys.modules, "torch", torch_module)

    datasets_module = ModuleType("datasets")
    datasets_module.Dataset = object
    monkeypatch.setitem(sys.modules, "datasets", datasets_module)

    transformers_module = ModuleType("transformers")
    transformers_module.AutoModelForCausalLM = object
    transformers_module.AutoTokenizer = object
    transformers_module.BitsAndBytesConfig = object
    transformers_module.TrainingArguments = object
    transformers_module.Trainer = object
    transformers_module.DataCollatorForLanguageModeling = object
    monkeypatch.setitem(sys.modules, "transformers", transformers_module)

    peft_module = ModuleType("peft")
    peft_module.LoraConfig = object
    peft_module.get_peft_model = lambda model, _: model
    peft_module.prepare_model_for_kbit_training = lambda model: model
    peft_module.PeftModel = object
    monkeypatch.setitem(sys.modules, "peft", peft_module)


def _load_pipeline_module(monkeypatch):
    _install_fake_training_modules(monkeypatch)
    spec = spec_from_file_location("test_finetune_pipeline_module", PIPELINE_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_separates_train_quant_and_gguf_quant(monkeypatch):
    module = _load_pipeline_module(monkeypatch)
    calls = []
    monkeypatch.setattr(
        module,
        "run_pipeline",
        lambda domain, base_model, step, **kwargs: calls.append(
            {
                "domain": domain,
                "base_model": base_model,
                "step": step,
                **kwargs,
            }
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "stm32",
            "--train-quant",
            "none",
            "--quant",
            "q5_k_m",
        ],
    )

    module.main()

    assert calls == [
        {
            "domain": "stm32",
            "base_model": module.DEFAULT_BASE,
            "step": None,
            "epochs": 3,
            "seq_len": 512,
            "max_samples": None,
            "quant": "q5_k_m",
            "train_quant": "none",
        }
    ]


def test_main_preserves_legacy_quant_none_alias(monkeypatch, capsys):
    module = _load_pipeline_module(monkeypatch)
    calls = []
    monkeypatch.setattr(
        module,
        "run_pipeline",
        lambda domain, base_model, step, **kwargs: calls.append(
            {
                "domain": domain,
                "base_model": base_model,
                "step": step,
                **kwargs,
            }
        ),
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "stm32", "--quant", "none"])

    module.main()

    captured = capsys.readouterr()
    assert "`--quant none`" in captured.out
    assert calls == [
        {
            "domain": "stm32",
            "base_model": module.DEFAULT_BASE,
            "step": None,
            "epochs": 3,
            "seq_len": 512,
            "max_samples": None,
            "quant": "q4_k_m",
            "train_quant": "none",
        }
    ]
