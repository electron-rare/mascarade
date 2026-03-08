"""Declarative teacher/student scenario matrix for local finetune batches."""

from __future__ import annotations

from dataclasses import dataclass

ALL_DOMAINS = (
    "stm32",
    "spice",
    "iot",
    "power",
    "dsp",
    "emc",
    "kicad",
    "embedded",
    "platformio",
    "freecad",
)

CODE_ONLY_DOMAINS = (
    "stm32",
    "kicad",
    "embedded",
    "platformio",
    "freecad",
)

ALIAS_MAP = {
    "esp32": "iot",
    "pio": "platformio",
}

CPU_STUDENT_MODELS = {
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
}

GPU_STUDENT_MODELS = {
    "Qwen/Qwen3-8B",
    "Qwen/Qwen3.5-9B-Base",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
}

TEACHER_ONLY_MODELS = {
    "Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
    "devstral-small-2507",
    "mistral-small-3.1",
    "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
}


@dataclass(frozen=True)
class PassSpec:
    name: str
    max_source_samples: int
    samples_per_source: int
    student_max_samples: int
    epochs: int


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    group: str
    teacher_provider: str
    teacher_model: str
    student_model: str | None
    device: str
    teacher_only: bool = False
    domains: tuple[str, ...] = ALL_DOMAINS
    max_tokens: int = 2048
    seq_len: int | None = 1024
    local_hf_device: str | None = None


PASS_SPECS = {
    "1": PassSpec(
        name="1",
        max_source_samples=32,
        samples_per_source=2,
        student_max_samples=128,
        epochs=1,
    ),
    "2": PassSpec(
        name="2",
        max_source_samples=64,
        samples_per_source=2,
        student_max_samples=192,
        epochs=2,
    ),
    "3": PassSpec(
        name="3",
        max_source_samples=96,
        samples_per_source=2,
        student_max_samples=256,
        epochs=3,
    ),
}


SCENARIO_SPECS = {
    "ollama_qwen25_14b_to_tinyllama_cpu": ScenarioSpec(
        name="ollama_qwen25_14b_to_tinyllama_cpu",
        group="qwen",
        teacher_provider="ollama",
        teacher_model="qwen2.5:14b",
        student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device="cpu",
        seq_len=256,
    ),
    "qwen25_7b_instruct_to_tinyllama_cpu": ScenarioSpec(
        name="qwen25_7b_instruct_to_tinyllama_cpu",
        group="qwen",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen2.5-7B-Instruct",
        student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device="cpu",
        seq_len=512,
        local_hf_device="cuda:0",
    ),
    "qwen3_4b_instruct_2507_to_tinyllama_cpu": ScenarioSpec(
        name="qwen3_4b_instruct_2507_to_tinyllama_cpu",
        group="qwen",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3-4B-Instruct-2507",
        student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device="cpu",
        seq_len=512,
        local_hf_device="cuda:0",
    ),
    "qwen35_35b_teacher_only_2048": ScenarioSpec(
        name="qwen35_35b_teacher_only_2048",
        group="qwen",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        student_model=None,
        device="gpu",
        teacher_only=True,
        max_tokens=2048,
        seq_len=None,
    ),
    "qwen35_35b_to_tinyllama_cpu": ScenarioSpec(
        name="qwen35_35b_to_tinyllama_cpu",
        group="qwen",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device="cpu",
        seq_len=512,
    ),
    "qwen35_35b_to_qwen3_8b_gpu": ScenarioSpec(
        name="qwen35_35b_to_qwen3_8b_gpu",
        group="qwen",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        student_model="Qwen/Qwen3-8B",
        device="gpu",
    ),
    "qwen35_35b_to_qwen35_9b_base_gpu": ScenarioSpec(
        name="qwen35_35b_to_qwen35_9b_base_gpu",
        group="qwen",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        student_model="Qwen/Qwen3.5-9B-Base",
        device="gpu",
    ),
    "devstral_small_2507_teacher_only": ScenarioSpec(
        name="devstral_small_2507_teacher_only",
        group="mistral",
        teacher_provider="mistral",
        teacher_model="devstral-small-2507",
        student_model=None,
        device="gpu",
        teacher_only=True,
        seq_len=None,
    ),
    "devstral_small_2507_to_tinyllama_cpu": ScenarioSpec(
        name="devstral_small_2507_to_tinyllama_cpu",
        group="mistral",
        teacher_provider="mistral",
        teacher_model="devstral-small-2507",
        student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device="cpu",
        seq_len=512,
    ),
    "devstral_small_2507_to_qwen3_8b_gpu": ScenarioSpec(
        name="devstral_small_2507_to_qwen3_8b_gpu",
        group="mistral",
        teacher_provider="mistral",
        teacher_model="devstral-small-2507",
        student_model="Qwen/Qwen3-8B",
        device="gpu",
    ),
    "mistral_small_3_1_teacher_only": ScenarioSpec(
        name="mistral_small_3_1_teacher_only",
        group="mistral",
        teacher_provider="mistral",
        teacher_model="mistral-small-3.1",
        student_model=None,
        device="gpu",
        teacher_only=True,
        seq_len=None,
    ),
    "mistral_small_3_1_to_tinyllama_cpu": ScenarioSpec(
        name="mistral_small_3_1_to_tinyllama_cpu",
        group="mistral",
        teacher_provider="mistral",
        teacher_model="mistral-small-3.1",
        student_model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        device="cpu",
        seq_len=512,
    ),
    "mistral_small_3_1_to_qwen3_8b_gpu": ScenarioSpec(
        name="mistral_small_3_1_to_qwen3_8b_gpu",
        group="mistral",
        teacher_provider="mistral",
        teacher_model="mistral-small-3.1",
        student_model="Qwen/Qwen3-8B",
        device="gpu",
    ),
    "qwen35_35b_to_deepseek_r1_distill_qwen_1_5b_cpu": ScenarioSpec(
        name="qwen35_35b_to_deepseek_r1_distill_qwen_1_5b_cpu",
        group="deepseek",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        student_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
        device="cpu",
        seq_len=512,
    ),
    "qwen35_35b_to_deepseek_r1_distill_qwen_7b_gpu": ScenarioSpec(
        name="qwen35_35b_to_deepseek_r1_distill_qwen_7b_gpu",
        group="deepseek",
        teacher_provider="local-hf",
        teacher_model="Qwen/Qwen3.5-35B-A3B-GPTQ-Int4",
        student_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        device="gpu",
    ),
    "devstral_small_2507_to_deepseek_r1_distill_qwen_7b_gpu": ScenarioSpec(
        name="devstral_small_2507_to_deepseek_r1_distill_qwen_7b_gpu",
        group="deepseek",
        teacher_provider="mistral",
        teacher_model="devstral-small-2507",
        student_model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        device="gpu",
    ),
    "deepseek_coder_v2_lite_teacher_only_code_domains": ScenarioSpec(
        name="deepseek_coder_v2_lite_teacher_only_code_domains",
        group="deepseek",
        teacher_provider="local-hf",
        teacher_model="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        student_model=None,
        device="gpu",
        teacher_only=True,
        domains=CODE_ONLY_DOMAINS,
        seq_len=None,
    ),
    "deepseek_coder_v2_lite_to_qwen3_8b_gpu_code_domains": ScenarioSpec(
        name="deepseek_coder_v2_lite_to_qwen3_8b_gpu_code_domains",
        group="deepseek",
        teacher_provider="local-hf",
        teacher_model="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
        student_model="Qwen/Qwen3-8B",
        device="gpu",
        domains=CODE_ONLY_DOMAINS,
    ),
}


def canonical_domain(raw_domain: str) -> str:
    return ALIAS_MAP.get(raw_domain, raw_domain)
