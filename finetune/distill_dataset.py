#!/usr/bin/env python3
"""Generate distilled ShareGPT samples with a teacher model via Mascarade."""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import random
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from dataset_quality import DatasetQualityError, enforce_dataset_quality, summarize_quality_report
from llm_paths import configure_hf_env, hf_cache_roots
from sharegpt_utils import (
    dedupe_rows_with_stats,
    ensure_row_ids_with_stats,
    load_jsonl,
    make_row,
    validate_rows,
    write_jsonl,
)
from tqdm.auto import tqdm

DEFAULT_API_URLS = ["http://127.0.0.1:3100", "http://127.0.0.1:8100"]
DEFAULT_DOMAINS = [
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
    "components",
]
DEFAULT_TEACHER_SYSTEM = """You create supervised fine-tuning data for a smaller local model.
Return only valid JSON. Do not wrap the JSON in markdown fences.
Prioritize technical correctness, realistic code/configuration, and domain precision.
When the source is in French, keep the generated samples in French. Otherwise keep the source language."""

DOMAIN_BRIEFS = {
    "stm32": "Embedded firmware, STM32 HAL/LL, CMSIS, FreeRTOS, ARM Cortex-M, registers, DMA, UART, SPI, I2C.",
    "spice": "SPICE simulation, LTspice/ngspice, analog circuits, netlists, stability, convergence, op-amps, filters.",
    "iot": "ESP-IDF, MQTT, Wi-Fi, BLE, embedded networking, low power, telemetry, home automation.",
    "power": "Power electronics, converters, gate driving, thermal constraints, current sense, motor control.",
    "dsp": "DSP, filters, FFT, fixed-point, C implementations, signal conditioning, sampling constraints.",
    "emc": "EMC/EMI, ESD, grounding, shielding, return paths, layout, compliance troubleshooting.",
    "kicad": "KiCad, PCB stackups, routing, DRC, impedance control, footprints, BOM, Gerbers, manufacturing.",
    "embedded": "Bare-metal and RTOS embedded systems, debugging, interrupts, memory maps, toolchains, drivers.",
    "platformio": "PlatformIO, pio.ini, ESP32/ESP-IDF, Arduino, board definitions, build flags, libraries, flashing, debugging.",
    "freecad": "FreeCAD, parametric CAD, Python macros, workbenches, sketches, constraints, TechDraw, STEP export.",
    "components": "Electronic component selection, datasheets, alternates, distributor sourcing, BOM optimization, symbols, footprints, JLCPCB/LCSC, Altium and EasyEDA library workflows.",
}

LOCAL_HF_PROVIDER = "local-hf"
_LOCAL_HF_TEACHER = None
_LOCAL_HF_TEACHER_MODEL = None
_LOCAL_HF_LOAD_LOCK = threading.Lock()
_LOCAL_HF_GENERATE_LOCK = threading.Lock()

configure_hf_env()


def resolve_local_hf_model_path(model_name: str) -> str:
    suffix = f"models--{model_name.replace('/', '--')}"
    for root in hf_cache_roots():
        snapshots_dir = root / suffix / "snapshots"
        if not snapshots_dir.exists():
            continue
        snapshots = sorted(
            (path for path in snapshots_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for snapshot in snapshots:
            if (snapshot / "config.json").exists():
                return str(snapshot)
    return model_name


def supports_bf16(torch_module) -> bool:
    return bool(torch_module.cuda.is_available() and torch_module.cuda.is_bf16_supported())


def resolve_local_hf_compute_dtype(torch_module):
    return torch_module.bfloat16 if supports_bf16(torch_module) else torch_module.float16


def resolve_local_hf_attention_implementation(torch_module) -> str | None:
    requested = os.environ.get("MASCARADE_ATTN_IMPL", "auto").strip().lower()
    if requested in {"", "auto"}:
        if find_spec("flash_attn") is not None:
            return "flash_attention_2"
        if torch_module.cuda.is_available():
            return "sdpa"
        return None
    if requested in {"none", "off"}:
        return None
    return requested


@dataclass
class EndpointConfig:
    base_url: str
    providers_url: str
    send_url: str
    providers: list[str]


class LocalHFTeacher:
    def __init__(self, model_name: str) -> None:
        import torch
        from transformers import AutoConfig, AutoTokenizer

        self.model_name = model_name
        self.model_path = resolve_local_hf_model_path(model_name)
        self.torch = torch
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            if hasattr(torch, "set_float32_matmul_precision"):
                torch.set_float32_matmul_precision("high")
        self.config = AutoConfig.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            local_files_only=True,
        )
        self.model_type = getattr(self.config, "model_type", None)
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            local_files_only=True,
        )
        self.model = self._load_model()
        self.model.eval()
        self.device = next(self.model.parameters()).device

    def _load_model(self):
        from transformers import AutoModelForCausalLM

        target_device = os.environ.get("MASCARADE_LOCAL_HF_DEVICE", "").strip()
        if not target_device:
            target_device = "auto"

        common_kwargs = {
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
            "local_files_only": True,
        }
        if target_device != "cpu" and self.torch.cuda.is_available():
            common_kwargs["torch_dtype"] = resolve_local_hf_compute_dtype(self.torch)
            attn_implementation = resolve_local_hf_attention_implementation(self.torch)
            if attn_implementation is not None:
                common_kwargs["attn_implementation"] = attn_implementation
        if target_device == "auto":
            common_kwargs["device_map"] = "auto"
        elif target_device == "cpu":
            common_kwargs["device_map"] = "cpu"
        else:
            common_kwargs["device_map"] = {"": target_device}
        if self.model_type == "qwen3_5":
            from transformers import Qwen3_5ForConditionalGeneration

            loader = Qwen3_5ForConditionalGeneration
        elif self.model_type == "mistral3":
            from transformers import Mistral3ForConditionalGeneration

            loader = Mistral3ForConditionalGeneration
        else:
            loader = AutoModelForCausalLM

        try:
            return loader.from_pretrained(
                self.model_path,
                **common_kwargs,
            )
        except TypeError:
            if "attn_implementation" not in common_kwargs:
                raise
        except Exception as exc:
            if common_kwargs.get("attn_implementation") != "flash_attention_2":
                raise
            if "flash_attention_2" not in str(exc).lower():
                raise

        common_kwargs.pop("attn_implementation", None)
        return loader.from_pretrained(
            self.model_path,
            **common_kwargs,
        )

    def _build_messages(self, teacher_system: str, user_prompt: str) -> list[dict]:
        messages = []
        if teacher_system.strip():
            messages.append({"role": "system", "content": teacher_system})
        if self.model_type == "mistral3":
            messages.append(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user_prompt}],
                }
            )
        else:
            messages.append({"role": "user", "content": user_prompt})
        return messages

    def _apply_chat_template(
        self, teacher_system: str, user_prompt: str
    ) -> str:
        messages = self._build_messages(teacher_system, user_prompt)
        if hasattr(self.tokenizer, "apply_chat_template") and getattr(
            self.tokenizer, "chat_template", None
        ):
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        prompt_parts = []
        if teacher_system.strip():
            prompt_parts.append(teacher_system.strip())
        prompt_parts.append(user_prompt.strip())
        return "\n\n".join(part for part in prompt_parts if part).strip()

    def _prepare_inputs(self, teacher_system: str, user_prompt: str) -> dict:
        messages = self._build_messages(teacher_system, user_prompt)
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                tokenized = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_tensors="pt",
                    return_dict=True,
                )
                if hasattr(tokenized, "items"):
                    return dict(tokenized.items())
            except Exception:
                pass
        prompt = self._apply_chat_template(teacher_system, user_prompt)
        return self.tokenizer(prompt, return_tensors="pt")

    def generate_json(
        self, *, teacher_system: str, user_prompt: str, max_tokens: int, temperature: float
    ) -> str:
        inputs = self._prepare_inputs(teacher_system, user_prompt)
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        generate_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": temperature > 0,
        }
        if temperature > 0:
            generate_kwargs["temperature"] = temperature
            generate_kwargs["top_p"] = 0.95

        with self.torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generate_kwargs)
        prompt_length = inputs["input_ids"].shape[1]
        generated_ids = output_ids[:, prompt_length:]
        return self.tokenizer.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0].strip()


def get_local_hf_teacher(model_name: str) -> LocalHFTeacher:
    global _LOCAL_HF_TEACHER, _LOCAL_HF_TEACHER_MODEL
    with _LOCAL_HF_LOAD_LOCK:
        if _LOCAL_HF_TEACHER is None or _LOCAL_HF_TEACHER_MODEL != model_name:
            _LOCAL_HF_TEACHER = LocalHFTeacher(model_name)
            _LOCAL_HF_TEACHER_MODEL = model_name
    return _LOCAL_HF_TEACHER


def shorten(text: str, limit: int = 800) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def clip_text(text: str, limit: int) -> str:
    value = text.strip()
    if len(value) <= limit:
        return value
    clipped = value[:limit].rstrip()
    return clipped + "\n...[truncated]"


def stringify_sample_field(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback.strip()
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2).strip()
    return str(value).strip()


def teacher_prefers_compact_json(
    teacher_provider: str | None, teacher_model: str | None
) -> bool:
    provider = (teacher_provider or "").strip().lower()
    model = (teacher_model or "").strip().lower()
    if provider != LOCAL_HF_PROVIDER:
        return False
    return any(
        needle in model
        for needle in (
            "devstral",
            "mistral-small-3.1",
            "mistral-small-3.2",
            "mistral3",
        )
    )


def teacher_is_devstral(teacher_model: str | None) -> bool:
    return "devstral" in (teacher_model or "").strip().lower()


def teacher_is_mistral_base(teacher_model: str | None) -> bool:
    model = (teacher_model or "").strip().lower()
    return "mistral-small-3.1" in model and "base" in model


def looks_like_truncated_json(raw_text: str) -> bool:
    text = raw_text.strip()
    if not text:
        return False
    if not text.startswith("{"):
        return False
    if '"samples"' not in text:
        return False
    opens = text.count("{") + text.count("[")
    closes = text.count("}") + text.count("]")
    if opens > closes:
        return True
    if text[-1] not in {"}", "]", '"'}:
        return True
    return False


def decode_loose_json_string(encoded: str) -> str:
    value = encoded
    while value:
        try:
            return json.loads(f'"{value}"')
        except json.JSONDecodeError:
            value = value[:-1]
    return ""


def decode_jsonish_string(encoded: str) -> str:
    decoded = decode_loose_json_string(encoded)
    if decoded:
        return decoded.strip()
    # Best-effort fallback for code-heavy answers that break JSON escaping.
    value = encoded
    replacements = [
        ("\\r\\n", "\n"),
        ("\\n", "\n"),
        ("\\t", "\t"),
        ('\\"', '"'),
        ("\\\\", "\\"),
    ]
    for old, new in replacements:
        value = value.replace(old, new)
    return value.strip()


def strip_markdown_json_fence(raw_text: str) -> str:
    text = raw_text.strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def extract_partial_json_string(raw_text: str, field: str) -> tuple[str, bool] | None:
    marker = f'"{field}":"'
    start = raw_text.find(marker)
    if start == -1:
        return None
    cursor = start + len(marker)
    encoded_chars: list[str] = []
    escaped = False
    terminated = False
    while cursor < len(raw_text):
        char = raw_text[cursor]
        cursor += 1
        if escaped:
            encoded_chars.append(char)
            escaped = False
            continue
        if char == "\\":
            encoded_chars.append(char)
            escaped = True
            continue
        if char == '"':
            terminated = True
            break
        encoded_chars.append(char)
    return decode_jsonish_string("".join(encoded_chars)), terminated


def extract_jsonish_field(
    raw_text: str, field: str, next_field: str | None
) -> tuple[str, bool] | None:
    match = re.search(rf'"{field}"\s*:\s*"', raw_text, flags=re.DOTALL)
    if match is None:
        return None
    remainder = raw_text[match.end() :]
    if next_field:
        tail = re.search(
            rf'"\s*,\s*"{next_field}"\s*:',
            remainder,
            flags=re.DOTALL,
        )
        if tail is not None:
            return decode_jsonish_string(remainder[: tail.start()]), True
    tail = re.search(r'"\s*[\}\]]', remainder, flags=re.DOTALL)
    if tail is not None:
        return decode_jsonish_string(remainder[: tail.start()]), True
    return decode_jsonish_string(remainder), False


def salvage_truncated_teacher_payload(raw_text: str) -> dict | None:
    normalized = strip_markdown_json_fence(raw_text)
    if not looks_like_truncated_json(normalized):
        return None
    if '"samples"' not in normalized:
        return None
    system_info = extract_jsonish_field(normalized, "system", "user")
    user_info = extract_jsonish_field(normalized, "user", "assistant")
    assistant_info = extract_jsonish_field(normalized, "assistant", "source_kind")
    if assistant_info is None:
        system_info = extract_partial_json_string(normalized, "system")
        user_info = extract_partial_json_string(normalized, "user")
        assistant_info = extract_partial_json_string(normalized, "assistant")
    if assistant_info is None:
        return None
    system = "" if system_info is None else system_info[0]
    user = "" if user_info is None else user_info[0]
    assistant, assistant_terminated = assistant_info
    if not user or not assistant:
        return None
    assistant = assistant.rstrip()
    if not assistant_terminated:
        assistant = assistant.rstrip() + "\n...[truncated]"
    return {
        "samples": [
            {
                "system": system,
                "user": user,
                "assistant": assistant,
                "source_kind": "upgrade",
            }
        ]
    }


def clip_compact_teacher_field(value: str, limit: int) -> str:
    trimmed = value.strip()
    if len(trimmed) <= limit:
        return trimmed
    compact = trimmed[:limit].rstrip()
    return compact + "\n...[truncated]"


def resolve_teacher_attempt_max_tokens(
    *,
    teacher_provider: str | None,
    teacher_model: str | None,
    base_max_tokens: int,
    attempt: int,
    last_raw: str,
) -> int:
    tokens = base_max_tokens
    compact = teacher_prefers_compact_json(teacher_provider, teacher_model)
    if compact:
        if teacher_is_devstral(teacher_model):
            tokens = max(tokens, 192)
        elif teacher_is_mistral_base(teacher_model):
            tokens = max(tokens, 64)
        else:
            tokens = max(tokens, 128)
    if attempt == 0:
        return tokens
    if compact:
        if looks_like_truncated_json(last_raw):
            if teacher_is_mistral_base(teacher_model):
                return min(max(tokens * 2, tokens + 64), 256)
            return min(max(tokens * 2, tokens + 192), 768)
        if teacher_is_mistral_base(teacher_model):
            return min(max(tokens, 128), 256)
        return min(max(tokens, 320), 640)
    if looks_like_truncated_json(last_raw):
        return min(max(tokens * 2, tokens + 128), 1024)
    return tokens


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail = shorten(raw) if raw else str(exc)
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error while calling {url}: {exc.reason}") from exc


def candidate_endpoints(base_url: str) -> list[tuple[str, str]]:
    base = base_url.rstrip("/")
    if base.endswith("/api/agents"):
        return [(f"{base}/providers", f"{base}/send")]
    if base.endswith("/api"):
        return [(f"{base}/agents/providers", f"{base}/agents/send")]
    if ":3100" in base:
        return [
            (f"{base}/api/agents/providers", f"{base}/api/agents/send"),
            (f"{base}/providers", f"{base}/send"),
        ]
    return [
        (f"{base}/providers", f"{base}/send"),
        (f"{base}/api/agents/providers", f"{base}/api/agents/send"),
    ]


def resolve_endpoint(
    api_urls: list[str], headers: dict[str, str], timeout: int
) -> EndpointConfig:
    last_error: str | None = None
    for base_url in api_urls:
        for providers_url, send_url in candidate_endpoints(base_url):
            try:
                payload = request_json(
                    providers_url,
                    method="GET",
                    headers=headers,
                    timeout=timeout,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{providers_url}: {exc}"
                continue
            providers = payload.get("providers", [])
            if not isinstance(providers, list):
                providers = []
            return EndpointConfig(
                base_url=base_url.rstrip("/"),
                providers_url=providers_url,
                send_url=send_url,
                providers=[str(provider) for provider in providers],
            )
    raise RuntimeError(
        f"Unable to reach Mascarade API/providers endpoint ({last_error})"
    )


def extract_messages(row: dict) -> tuple[str, str, str]:
    system = ""
    user = ""
    assistant = ""
    for message in row.get("conversations", []):
        role = message.get("from")
        value = str(message.get("value", "")).strip()
        if role == "system" and not system:
            system = value
        elif role == "human" and not user:
            user = value
        elif role == "gpt":
            assistant = value
    return system, user, assistant


def build_teacher_prompt(
    row: dict,
    domain: str,
    samples_per_source: int,
    *,
    compact_json: bool = False,
) -> str:
    domain_brief = DOMAIN_BRIEFS.get(domain, "")
    source_system, source_user, source_assistant = extract_messages(row)
    source_system = clip_text(source_system or "(none)", 1200)
    source_user = clip_text(source_user, 4000)
    source_assistant = clip_text(source_assistant or "(none)", 2400)
    compact_rules = ""
    if compact_json:
        compact_rules = """
- Keep "system" empty unless a short system instruction is strictly necessary.
- Keep "user" under 320 characters.
- Keep "assistant" under 900 characters.
- Prefer one compact code block or plain text, not both."""
    return f"""Create exactly {samples_per_source} distilled supervised training samples for the domain "{domain}".

Domain brief:
{domain_brief}

Rules:
- Return only valid JSON.
- Return a single JSON object with this schema exactly:
  {{"samples":[{{"system":"...","user":"...","assistant":"...","source_kind":"upgrade|variant"}}]}}
- Every field except source_kind must be a JSON string.
- "assistant" must be a single plain-text or markdown string, never an object, array, or nested JSON value.
- Sample 1 must be an upgraded version of the source task with a stronger answer.
- Remaining samples must be close domain variants that train adjacent sub-skills.
- Keep the same language as the source user message.
- Be precise, concrete, and production-ready.
- Compress oversized source material into a focused task; do not copy giant enumerations or long checklists verbatim.
- Keep each assistant compact enough to fit comfortably in the token budget.
- If code is useful, include at most one minimal code block.
- No placeholders, no TODOs, no markdown fences around the JSON.
{compact_rules}

Source system:
{source_system}

Source user:
{source_user}

Source assistant excerpt:
{source_assistant}
"""


def build_repair_prompt(
    *,
    row: dict,
    domain: str,
    samples_per_source: int,
    raw_response: str,
    compact_json: bool = False,
) -> str:
    source_system, source_user, source_assistant = extract_messages(row)
    snippet = raw_response.strip()
    if len(snippet) > 4000:
        snippet = snippet[:4000]
    compact_rules = ""
    if compact_json:
        compact_rules = """
- Keep "system" empty unless strictly necessary.
- Keep "user" under 320 characters.
- Keep "assistant" under 900 characters.
- If the previous answer was truncated, regenerate from scratch with a shorter assistant."""
    return f"""Your previous answer was invalid for automated parsing.

Regenerate the answer from the source below.
Return only valid JSON. Do not add markdown fences. Do not add explanations.
Use this exact schema:
{{"samples":[{{"system":"...","user":"...","assistant":"...","source_kind":"upgrade|variant"}}]}}

You must return exactly {samples_per_source} samples for domain "{domain}".
- Every field except source_kind must be a JSON string.
- "assistant" must be a single plain-text or markdown string, never an object or array.
- Keep the answer compact enough to stay well within the token budget.
{compact_rules}

Source system:
{clip_text(source_system or "(none)", 1200)}

Source user:
{clip_text(source_user, 4000)}

Source assistant excerpt:
{clip_text(source_assistant or "(none)", 2400)}

Previous invalid answer:
{snippet}
"""


def parse_teacher_payload(raw_text: str) -> dict:
    candidates = [raw_text.strip()]

    fenced = re.findall(
        r"```(?:json)?\s*(.*?)```", raw_text, flags=re.DOTALL | re.IGNORECASE
    )
    candidates.extend(chunk.strip() for chunk in fenced if chunk.strip())

    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(raw_text[first_brace : last_brace + 1].strip())

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("samples"), list):
            return payload

    salvaged = salvage_truncated_teacher_payload(raw_text)
    if salvaged is not None:
        return salvaged

    raise ValueError("Teacher response is not valid JSON with a 'samples' array")


def build_distilled_rows(
    payload: dict,
    *,
    domain: str,
    source_row: dict,
    provider: str | None,
    model: str | None,
    max_rows: int,
) -> list[dict]:
    source_id = str(source_row.get("id") or "")
    source_system, source_user, _source_assistant = extract_messages(source_row)
    compact_fields = teacher_prefers_compact_json(provider, model)
    if not source_id:
        source_fingerprint = hashlib.sha1(
            json.dumps(
                source_row.get("conversations", []), ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()[:12]
        source_id = source_fingerprint
    rows: list[dict] = []

    for index, sample in enumerate(payload["samples"][:max_rows], start=1):
        if not isinstance(sample, dict):
            continue
        system = stringify_sample_field(sample.get("system"), source_system)
        user = stringify_sample_field(sample.get("user"), source_user)
        assistant = stringify_sample_field(sample.get("assistant"), "")
        if compact_fields:
            if not system:
                system = source_system
            system = clip_compact_teacher_field(system, 160) if system else ""
            user = clip_compact_teacher_field(user, 320)
            assistant = clip_compact_teacher_field(assistant, 900)
        source_kind = str(
            sample.get("source_kind") or ("upgrade" if index == 1 else "variant")
        ).strip()
        if not system or not user or not assistant:
            continue

        row_id = f"{domain}-distill-{source_id}-{index:02d}"
        rows.append(
            make_row(
                row_id=row_id,
                system=system,
                user=user,
                assistant=assistant,
                meta={
                    "domain": domain,
                    "source_id": source_id,
                    "source_kind": source_kind,
                    "teacher_provider": provider,
                    "teacher_model": model,
                    "generated_at": int(time.time()),
                },
            )
        )

    return rows


def sample_source_rows(
    rows: list[dict], max_samples: int | None, seed: int
) -> list[dict]:
    selected = list(rows)
    rng = random.Random(seed)
    rng.shuffle(selected)
    if max_samples is not None:
        selected = selected[:max_samples]
    return selected


def default_output_path(domain: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return (
        Path(__file__).resolve().parent
        / "datasets"
        / "distilled"
        / f"{domain}_teacher_{stamp}.jsonl"
    )


def resolve_concurrency(requested: int, sample_count: int) -> int:
    if sample_count <= 1:
        return 1
    if requested <= 0:
        cpu_count = os.cpu_count() or 1
        requested = min(4, max(1, cpu_count // 3))
    return max(1, min(requested, sample_count))


def teacher_uses_local_hf(teacher_provider: str | None) -> bool:
    return (teacher_provider or "").strip().lower() == LOCAL_HF_PROVIDER


def distill_source_row(
    *,
    index: int,
    row: dict,
    domain: str,
    samples_per_source: int,
    dry_run: bool,
    teacher_provider: str | None,
    teacher_model: str | None,
    strategy: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    sleep_ms: int,
    teacher_system: str,
    endpoint: EndpointConfig | None,
    headers: dict[str, str],
    json_retries: int,
) -> dict:
    source_id = str(row.get("id", f"row-{index}"))
    compact_json = teacher_prefers_compact_json(teacher_provider, teacher_model)
    prompt = build_teacher_prompt(
        row, domain, samples_per_source, compact_json=compact_json
    )

    if dry_run:
        system, user, assistant = extract_messages(row)
        payload = {
            "samples": [
                {
                    "system": system,
                    "user": user,
                    "assistant": f"{assistant}\n\n[distilled dry-run sample {sample_index}]",
                    "source_kind": "upgrade" if sample_index == 1 else "variant",
                }
                for sample_index in range(1, samples_per_source + 1)
            ]
        }
        provider_used = "dry-run"
        model_used = "dry-run"
        latency_ms = 0.0
    elif teacher_uses_local_hf(teacher_provider):
        if not teacher_model:
            raise ValueError("teacher_model is required when teacher_provider=local-hf")
        payload = None
        latency_ms = 0.0
        repair_raw = ""
        last_error: Exception | None = None
        attempts = max(1, json_retries + 1)
        for attempt in range(attempts):
            user_prompt = (
                prompt
                if attempt == 0
                else build_repair_prompt(
                    row=row,
                    domain=domain,
                    samples_per_source=samples_per_source,
                    raw_response=repair_raw,
                    compact_json=compact_json,
                )
            )
            attempt_max_tokens = resolve_teacher_attempt_max_tokens(
                teacher_provider=teacher_provider,
                teacher_model=teacher_model,
                base_max_tokens=max_tokens,
                attempt=attempt,
                last_raw=repair_raw,
            )
            started_at = time.perf_counter()
            try:
                with _LOCAL_HF_GENERATE_LOCK:
                    teacher = get_local_hf_teacher(teacher_model)
                    repair_raw = teacher.generate_json(
                        teacher_system=teacher_system,
                        user_prompt=user_prompt,
                        max_tokens=attempt_max_tokens,
                        temperature=temperature if attempt == 0 else 0.0,
                    )
                latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                payload = parse_teacher_payload(repair_raw)
                break
            except Exception as exc:  # noqa: BLE001
                latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise ValueError(
                    f"{exc} | raw={shorten(repair_raw, 1200)}"
                ) from exc
        provider_used = LOCAL_HF_PROVIDER
        model_used = teacher_model
    else:
        route_strategy = "specific" if teacher_provider else strategy
        provider_used = None
        model_used = None
        payload = None
        latency_ms = 0.0
        last_error: Exception | None = None
        repair_raw = ""
        attempts = max(1, json_retries + 1)
        for attempt in range(attempts):
            user_prompt = (
                prompt
                if attempt == 0
                else build_repair_prompt(
                    row=row,
                    domain=domain,
                    samples_per_source=samples_per_source,
                    raw_response=repair_raw,
                    compact_json=compact_json,
                )
            )
            body = {
                "messages": [{"role": "user", "content": user_prompt}],
                "strategy": route_strategy,
                "provider": teacher_provider,
                "model": teacher_model,
                "system": teacher_system,
                "temperature": temperature if attempt == 0 else 0.0,
                "max_tokens": resolve_teacher_attempt_max_tokens(
                    teacher_provider=teacher_provider,
                    teacher_model=teacher_model,
                    base_max_tokens=max_tokens,
                    attempt=attempt,
                    last_raw=repair_raw,
                ),
            }
            if teacher_provider in {None, "mistral", "ollama"}:
                body["response_format"] = {"type": "json_object"}
            try:
                started_at = time.perf_counter()
                response = request_json(
                    endpoint.send_url,
                    method="POST",
                    body=body,
                    headers=headers,
                    timeout=timeout,
                )
                provider_used = response.get("provider")
                model_used = response.get("model")
                if teacher_provider and provider_used != teacher_provider:
                    raise RuntimeError(
                        f"Strict teacher provider mismatch: requested {teacher_provider}, got {provider_used}"
                    )
                repair_raw = str(response.get("content", ""))
                latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
                payload = parse_teacher_payload(repair_raw)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if isinstance(
                    exc, RuntimeError
                ) and "Strict teacher provider mismatch" in str(exc):
                    raise
                if attempt < attempts - 1:
                    time.sleep(min(2**attempt, 8))
                    continue
                if attempt == attempts - 1:
                    raise ValueError(
                        f"{exc} | raw={shorten(repair_raw, 1200)}"
                    ) from exc
        if payload is None:
            raise RuntimeError(
                str(last_error) if last_error else "Teacher response parsing failed"
            )

    rows = build_distilled_rows(
        payload,
        domain=domain,
        source_row=row,
        provider=provider_used,
        model=model_used,
        max_rows=samples_per_source,
    )

    if sleep_ms:
        time.sleep(sleep_ms / 1000)

    return {
        "index": index,
        "source_id": source_id,
        "rows": rows,
        "provider": provider_used,
        "model": model_used,
        "latency_ms": latency_ms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate distilled ShareGPT samples with a teacher model"
    )
    parser.add_argument("domain", choices=DEFAULT_DOMAINS)
    parser.add_argument("--source-dataset", default=None, help="Input ShareGPT JSONL")
    parser.add_argument("--out", default=None, help="Output ShareGPT JSONL")
    parser.add_argument("--report-path", default=None, help="Optional JSON report path")
    parser.add_argument(
        "--failures-out",
        default=None,
        help="Optional JSONL of source rows that failed distillation",
    )
    parser.add_argument(
        "--api-url",
        action="append",
        dest="api_urls",
        help="Mascarade base URL, repeatable",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("MASCARADE_API_KEY", ""),
        help="MASCARADE_API_KEY bearer token",
    )
    parser.add_argument(
        "--teacher-provider", default=None, help="Provider name to force, e.g. mistral"
    )
    parser.add_argument(
        "--teacher-model", default=None, help="Specific teacher model override"
    )
    parser.add_argument(
        "--local-hf-device",
        default=os.environ.get("MASCARADE_LOCAL_HF_DEVICE"),
        help="Explicit device target for local-hf teachers (auto, cpu, cuda:0, ...)",
    )
    parser.add_argument(
        "--strategy",
        default="best",
        help="Routing strategy when provider is not forced",
    )
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-source-samples", type=int, default=32)
    parser.add_argument("--samples-per-source", type=int, default=2)
    parser.add_argument(
        "--concurrency", type=int, default=0, help="Teacher calls in parallel (0=auto)"
    )
    parser.add_argument(
        "--json-retries",
        type=int,
        default=1,
        help="Retry count when teacher returns invalid JSON",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sleep-ms", type=int, default=0)
    parser.add_argument(
        "--teacher-system-path",
        default=None,
        help="Optional file to override teacher system prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No HTTP call, emit deterministic synthetic rows",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="Print detailed progress information"
    )
    verbosity.add_argument(
        "--quiet", action="store_true", help="Only print important messages"
    )
    args = parser.parse_args()
    if args.local_hf_device:
        os.environ["MASCARADE_LOCAL_HF_DEVICE"] = args.local_hf_device

    script_dir = Path(__file__).resolve().parent
    source_dataset = (
        Path(args.source_dataset)
        if args.source_dataset
        else script_dir / "datasets" / f"{args.domain}_chat.jsonl"
    )
    output_path = Path(args.out) if args.out else default_output_path(args.domain)
    report_path = (
        Path(args.report_path)
        if args.report_path
        else output_path.with_suffix(".report.json")
    )

    if not source_dataset.exists():
        raise SystemExit(f"Source dataset not found: {source_dataset}")

    progress: tqdm | None = None

    def emit(message: str, *, important: bool = False) -> None:
        if args.quiet and not important:
            return
        if progress is not None:
            progress.write(message)
        else:
            print(message)

    raw_source_rows = load_jsonl(source_dataset)
    source_rows, normalized_source_ids = ensure_row_ids_with_stats(
        raw_source_rows,
        f"{args.domain}-source",
    )
    source_validation_errors = validate_rows(source_rows)
    if source_validation_errors:
        for error in source_validation_errors[:20]:
            emit(f"[ERROR] source dataset: {error}", important=True)
        raise SystemExit(
            f"Source dataset is invalid ({len(source_validation_errors)} errors)"
        )

    if normalized_source_ids:
        emit(
            f"[INFO] normalized source ids: {normalized_source_ids}/{len(source_rows)}",
            important=True,
        )
    try:
        source_quality = enforce_dataset_quality(
            source_rows,
            label=f"{args.domain} source dataset",
            ids_fixed=normalized_source_ids,
        )
    except DatasetQualityError as exc:
        raise SystemExit(f"Source dataset quality gate failed: {exc}") from exc
    if source_quality["warnings"]:
        emit(
            f"[WARN] source-quality: {summarize_quality_report(source_quality)}",
            important=True,
        )

    selected_rows = sample_source_rows(source_rows, args.max_source_samples, args.seed)
    resolved_concurrency = resolve_concurrency(args.concurrency, len(selected_rows))
    if teacher_uses_local_hf(args.teacher_provider):
        resolved_concurrency = 1

    teacher_system = (
        Path(args.teacher_system_path).read_text(encoding="utf-8")
        if args.teacher_system_path
        else DEFAULT_TEACHER_SYSTEM
    )

    headers: dict[str, str] = {}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    endpoint = None
    if not args.dry_run and not teacher_uses_local_hf(args.teacher_provider):
        api_urls = args.api_urls or DEFAULT_API_URLS
        endpoint = resolve_endpoint(api_urls, headers, args.timeout)
        emit(f"[OK] API: {endpoint.send_url}", important=True)
        emit(
            f"[OK] Providers: {', '.join(endpoint.providers) if endpoint.providers else '(none)'}",
            important=True,
        )
        if args.teacher_provider and args.teacher_provider not in endpoint.providers:
            emit(
                f"[WARN] Teacher provider '{args.teacher_provider}' is not currently advertised by the API",
                important=True,
            )
    elif teacher_uses_local_hf(args.teacher_provider):
        if not args.teacher_model:
            raise SystemExit(
                "--teacher-model is required when --teacher-provider local-hf"
            )
        emit(f"[OK] local teacher: {args.teacher_model}", important=True)
        emit(
            f"[OK] local teacher device: {args.local_hf_device or 'auto'}",
            important=True,
        )
        emit("[OK] local teacher concurrency forced to 1", important=True)

    if args.verbose:
        emit(f"[INFO] Source dataset: {source_dataset}", important=True)
        emit(
            f"[INFO] Selected source rows: {len(selected_rows)} / {len(source_rows)}",
            important=True,
        )
        emit(f"[INFO] Output dataset: {output_path}", important=True)
        emit(f"[INFO] Concurrency: {resolved_concurrency}", important=True)

    completed: list[dict] = []
    failures: list[dict] = []
    failed_rows: list[dict] = []
    progress = tqdm(
        total=len(selected_rows),
        desc=f"Distill {args.domain}",
        unit="sample",
        disable=args.quiet,
        dynamic_ncols=True,
    )
    with ThreadPoolExecutor(max_workers=resolved_concurrency) as executor:
        futures = {
            executor.submit(
                distill_source_row,
                index=index,
                row=row,
                domain=args.domain,
                samples_per_source=args.samples_per_source,
                dry_run=args.dry_run,
                teacher_provider=args.teacher_provider,
                teacher_model=args.teacher_model,
                strategy=args.strategy,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                sleep_ms=args.sleep_ms,
                teacher_system=teacher_system,
                endpoint=endpoint,
                headers=headers,
                json_retries=args.json_retries,
            ): index
            for index, row in enumerate(selected_rows, start=1)
        }

        for future in as_completed(futures):
            index = futures[future]
            row = selected_rows[index - 1]
            source_id = str(row.get("id", f"row-{index}"))
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append({"source_id": source_id, "error": str(exc)})
                failed_rows.append(dict(row))
                emit(
                    f"[FAIL] {index}/{len(selected_rows)} source={source_id} error={exc}",
                    important=True,
                )
                progress.update(1)
                continue

            completed.append(result)
            if args.verbose:
                emit(
                    f"[OK] {index}/{len(selected_rows)} source={result['source_id']} provider={result['provider']} model={result['model']} latency={result['latency_ms']}ms"
                )
            else:
                progress.set_postfix_str(
                    f"{result['provider'] or '-'} {result['latency_ms']:.0f}ms"
                )
            progress.update(1)

    distilled_rows: list[dict] = []
    for result in sorted(completed, key=lambda item: item["index"]):
        distilled_rows.extend(result["rows"])

    distilled_rows, duplicates_removed = dedupe_rows_with_stats(distilled_rows)
    validation_errors = validate_rows(distilled_rows)
    if validation_errors:
        for error in validation_errors[:20]:
            print(f"[ERROR] {error}")
        raise SystemExit(
            f"Generated dataset is invalid ({len(validation_errors)} errors)"
        )

    write_jsonl(output_path, distilled_rows)

    report = {
        "domain": args.domain,
        "source_dataset": str(source_dataset),
        "output_dataset": str(output_path),
        "source_rows": len(source_rows),
        "source_quality": source_quality,
        "selected_source_rows": len(selected_rows),
        "normalized_source_ids": normalized_source_ids,
        "distilled_rows": len(distilled_rows),
        "generated_rows": len(distilled_rows),
        "duplicates_removed": duplicates_removed,
        "failed_source_rows": len(failed_rows),
        "teacher_provider": args.teacher_provider,
        "teacher_model": args.teacher_model,
        "local_hf_device": args.local_hf_device,
        "strategy": "specific" if args.teacher_provider else args.strategy,
        "api_url": None if endpoint is None else endpoint.base_url,
        "failures_out": (
            None if args.failures_out is None else str(Path(args.failures_out))
        ),
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.failures_out is not None:
        write_jsonl(Path(args.failures_out), failed_rows)

    emit(f"[OK] wrote distilled dataset: {output_path}", important=True)
    emit(f"[OK] wrote report: {report_path}", important=True)
    if duplicates_removed:
        emit(
            f"[INFO] removed duplicate distilled rows: {duplicates_removed}",
            important=True,
        )
    if args.failures_out is not None:
        emit(f"[OK] wrote failures dataset: {args.failures_out}", important=True)
    emit(
        "[OK] summary: "
        f"source={len(source_rows)} "
        f"selected={len(selected_rows)} "
        f"distilled={len(distilled_rows)} "
        f"failed={len(failed_rows)}",
        important=True,
    )
    if failures:
        emit(f"[WARN] failures: {len(failures)}", important=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
