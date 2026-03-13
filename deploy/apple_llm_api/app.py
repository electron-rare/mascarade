#!/usr/bin/env python3
"""Host-native Apple Silicon text generation service."""

from __future__ import annotations

import importlib.metadata
import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Mascarade Apple LLM", version="0.1.0")


class Message(BaseModel):
    role: str = Field(..., min_length=1, max_length=20)
    content: str = Field(..., min_length=1, max_length=100_000)


class GenerateRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=200)
    system: str | None = Field(default=None, max_length=10_000)
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=8192)


class RuntimeConfigError(Exception):
    """Configuration or dependency error for the runtime."""


class RuntimeState(Protocol):
    backend_name: str

    def check_ready(self) -> None: ...

    def dependency_versions(self) -> dict[str, str | None]: ...

    def available_models(self) -> list[str]: ...

    def describe(self) -> dict[str, Any]: ...

    def generate(self, req: GenerateRequest) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RuntimeConfig:
    backend: str
    model_id: str
    model_path: str
    embed_model_path: str
    tokenizer_path: str
    compute_units: str
    max_input_tokens: int
    max_new_tokens: int
    trust_remote_code: bool


class ModelManager:
    """Manages multiple CoreML/ONNX models with hot-swap and priority queue support."""

    def __init__(self, max_concurrent_models: int = 1):
        """Initialize the model manager.

        Args:
            max_concurrent_models: Maximum number of models that can be loaded simultaneously.
                                   Default is 1 for memory-constrained devices.
        """
        self.loaded_models: dict[str, RuntimeState] = {}
        self.model_configs: dict[str, RuntimeConfig] = {}
        self.max_concurrent_models: int = max_concurrent_models
        self.current_model_id: str | None = None
        self.model_load_lock: Lock = Lock()

    def get_loaded_model(self, model_id: str) -> RuntimeState | None:
        """Get a loaded model by ID.

        Args:
            model_id: The model identifier

        Returns:
            The runtime state if loaded, None otherwise
        """
        return self.loaded_models.get(model_id)

    def is_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded.

        Args:
            model_id: The model identifier

        Returns:
            True if the model is loaded, False otherwise
        """
        return model_id in self.loaded_models

    def register_model_config(self, model_id: str, config: RuntimeConfig) -> None:
        """Register a model configuration.

        Args:
            model_id: The model identifier
            config: The runtime configuration for the model
        """
        self.model_configs[model_id] = config

    def get_model_config(self, model_id: str) -> RuntimeConfig | None:
        """Get a registered model configuration.

        Args:
            model_id: The model identifier

        Returns:
            The runtime configuration if registered, None otherwise
        """
        return self.model_configs.get(model_id)

    def list_loaded_models(self) -> list[str]:
        """List all currently loaded model IDs.

        Returns:
            List of loaded model IDs
        """
        return list(self.loaded_models.keys())

    def list_configured_models(self) -> list[str]:
        """List all configured model IDs.

        Returns:
            List of configured model IDs
        """
        return list(self.model_configs.keys())

    def load_model(self, model_id: str, config: RuntimeConfig) -> RuntimeState:
        """Load a model into memory.

        Args:
            model_id: The model identifier
            config: The runtime configuration for the model

        Returns:
            The loaded runtime state

        Raises:
            RuntimeConfigError: If the model cannot be loaded
            ValueError: If the model_id is empty
        """
        if not model_id or not model_id.strip():
            raise ValueError("model_id cannot be empty")

        with self.model_load_lock:
            # Check if already loaded
            if model_id in self.loaded_models:
                return self.loaded_models[model_id]

            # Check if we need to unload a model first
            if len(self.loaded_models) >= self.max_concurrent_models:
                # Unload the least recently used model (first in dict)
                # In Python 3.7+ dicts maintain insertion order
                if self.loaded_models:
                    lru_model_id = next(iter(self.loaded_models))
                    self.unload_model(lru_model_id)

            # Register the config if not already registered
            if model_id not in self.model_configs:
                self.model_configs[model_id] = config

            # Build the runtime
            try:
                runtime = _build_runtime(config)
                runtime.check_ready()
                self.loaded_models[model_id] = runtime
                self.current_model_id = model_id
                return runtime
            except Exception as exc:
                raise RuntimeConfigError(
                    f"Failed to load model '{model_id}': {exc}"
                ) from exc

    def unload_model(self, model_id: str) -> bool:
        """Unload a model from memory.

        Args:
            model_id: The model identifier

        Returns:
            True if the model was unloaded, False if it wasn't loaded

        Raises:
            ValueError: If the model_id is empty
        """
        if not model_id or not model_id.strip():
            raise ValueError("model_id cannot be empty")

        with self.model_load_lock:
            if model_id not in self.loaded_models:
                return False

            # Remove the model
            del self.loaded_models[model_id]

            # Update current_model_id if needed
            if self.current_model_id == model_id:
                # Set to the most recently loaded model, or None if no models loaded
                self.current_model_id = (
                    list(self.loaded_models.keys())[-1]
                    if self.loaded_models
                    else None
                )

            return True

    def _mark_model_used(self, model_id: str) -> None:
        """Mark a model as recently used by moving it to the end of the dict.

        Args:
            model_id: The model identifier

        Note:
            This method assumes the caller holds model_load_lock.
            Python 3.7+ dicts maintain insertion order, so we move the model
            to the end to mark it as most recently used.
        """
        if model_id in self.loaded_models:
            # Move to end by removing and re-inserting
            runtime = self.loaded_models.pop(model_id)
            self.loaded_models[model_id] = runtime

    def swap_model(self, new_model_id: str) -> RuntimeState:
        """Swap to a different model, implementing LRU eviction if needed.

        This method loads the requested model if it's not already loaded.
        If the model is already loaded, it updates its access time.
        When the maximum number of concurrent models is reached, the least
        recently used model is evicted.

        Args:
            new_model_id: The model identifier to swap to

        Returns:
            The runtime state for the requested model

        Raises:
            ValueError: If new_model_id is empty or if the model is not configured
            RuntimeConfigError: If the model cannot be loaded
        """
        if not new_model_id or not new_model_id.strip():
            raise ValueError("model_id cannot be empty")

        with self.model_load_lock:
            # If already loaded, mark as recently used and return
            if new_model_id in self.loaded_models:
                self._mark_model_used(new_model_id)
                self.current_model_id = new_model_id
                return self.loaded_models[new_model_id]

            # Get the model configuration
            config = self.model_configs.get(new_model_id)
            if config is None:
                raise ValueError(
                    f"Model '{new_model_id}' is not configured. "
                    f"Available models: {list(self.model_configs.keys())}"
                )

            # Check if we need to unload a model first (LRU eviction)
            if len(self.loaded_models) >= self.max_concurrent_models:
                if self.loaded_models:
                    # Evict the least recently used model (first in dict)
                    lru_model_id = next(iter(self.loaded_models))
                    self.unload_model(lru_model_id)

            # Load the new model
            try:
                runtime = _build_runtime(config)
                runtime.check_ready()
                self.loaded_models[new_model_id] = runtime
                self.current_model_id = new_model_id
                return runtime
            except Exception as exc:
                raise RuntimeConfigError(
                    f"Failed to load model '{new_model_id}': {exc}"
                ) from exc


_runtime_lock = Lock()
_runtime_cache: RuntimeState | None = None
_runtime_signature: RuntimeConfig | None = None
_model_manager = ModelManager(max_concurrent_models=1)
InputSpec = tuple[str, str, list[Any] | None]
StateSpec = tuple[str, str, list[Any] | None]


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_backend(raw: str | None) -> str:
    value = (raw or "coreml").strip().lower()
    aliases = {
        "coreml": "coreml",
        "onnx-coreml": "onnx-coreml",
        "ort-coreml": "onnx-coreml",
    }
    return aliases.get(value, "coreml")


def _normalize_compute_units(raw: str | None) -> str:
    value = (raw or "cpu_and_ne").strip().lower().replace("-", "_")
    aliases = {
        "all": "all",
        "cpu_only": "cpu_only",
        "cpu_and_gpu": "cpu_and_gpu",
        "cpu_and_ne": "cpu_and_ne",
        "cpu_and_neural_engine": "cpu_and_ne",
    }
    return aliases.get(value, "cpu_and_ne")


def _runtime_config() -> RuntimeConfig:
    return RuntimeConfig(
        backend=_normalize_backend(os.getenv("APPLE_LLM_BACKEND")),
        model_id=os.getenv("APPLE_LLM_MODEL_ID", "apple-local").strip() or "apple-local",
        model_path=os.getenv("APPLE_LLM_MODEL_PATH", "").strip(),
        embed_model_path=os.getenv("APPLE_LLM_EMBED_MODEL_PATH", "").strip(),
        tokenizer_path=os.getenv("APPLE_LLM_TOKENIZER_PATH", "").strip(),
        compute_units=_normalize_compute_units(os.getenv("APPLE_LLM_COMPUTE_UNITS")),
        max_input_tokens=max(32, _env_int("APPLE_LLM_MAX_INPUT_TOKENS", 2048)),
        max_new_tokens=max(1, _env_int("APPLE_LLM_MAX_NEW_TOKENS", 256)),
        trust_remote_code=_env_flag("APPLE_LLM_TRUST_REMOTE_CODE", False),
    )


def _configured(config: RuntimeConfig) -> bool:
    return bool(config.model_path and config.tokenizer_path)


def _is_coreml_artifact(path: str) -> bool:
    return Path(path).suffix.lower() in {".mlpackage", ".mlmodelc"}


def _require_model_artifact(path: str, *, backend: str, label: str) -> Path:
    artifact = Path(path)
    if backend == "coreml":
        if not _is_coreml_artifact(path):
            raise RuntimeConfigError(
                f"{label} must point to a Core ML artifact (.mlpackage or .mlmodelc), "
                f"got: {path}"
            )
    elif artifact.suffix.lower() != ".onnx":
        raise RuntimeConfigError(
            f"{label} must point to an ONNX model (.onnx), got: {path}"
        )

    if not artifact.exists():
        raise RuntimeConfigError(f"{label} does not exist: {path}")
    return artifact


def _load_tokenizer(tokenizer_path: str, *, trust_remote_code: bool):
    try:
        from transformers import AutoTokenizer, PreTrainedTokenizerFast
    except Exception as exc:  # pragma: no cover
        raise RuntimeConfigError(
            f"transformers tokenizer dependencies are not available: {exc}"
        ) from exc

    try:
        return AutoTokenizer.from_pretrained(
            tokenizer_path,
            trust_remote_code=trust_remote_code,
        )
    except Exception as exc:
        if "Tokenizer class TokenizersBackend" not in str(exc):
            raise

        tokenizer_dir = Path(tokenizer_path)
        tokenizer_file = tokenizer_dir / "tokenizer.json"
        tokenizer_config_file = tokenizer_dir / "tokenizer_config.json"
        if not tokenizer_file.exists() or not tokenizer_config_file.exists():
            raise

        with tokenizer_config_file.open() as handle:
            tokenizer_config = json.load(handle)

        tokenizer_kwargs = {
            "tokenizer_file": str(tokenizer_file),
        }
        for key in (
            "bos_token",
            "eos_token",
            "pad_token",
            "unk_token",
            "sep_token",
            "cls_token",
            "mask_token",
        ):
            value = tokenizer_config.get(key)
            if value is not None:
                tokenizer_kwargs[key] = value

        tokenizer = PreTrainedTokenizerFast(**tokenizer_kwargs)
        model_max_length = tokenizer_config.get("model_max_length")
        if isinstance(model_max_length, int) and model_max_length > 0:
            tokenizer.model_max_length = model_max_length
        for attr in ("padding_side", "truncation_side"):
            value = tokenizer_config.get(attr)
            if isinstance(value, str) and value:
                setattr(tokenizer, attr, value)
        chat_template = tokenizer_config.get("chat_template")
        if isinstance(chat_template, str) and chat_template:
            tokenizer.chat_template = chat_template
        return tokenizer


def _fallback_prompt(messages: list[dict[str, str]], system: str | None = None) -> str:
    lines: list[str] = []
    if system:
        lines.append(f"System: {system.strip()}")
    for message in messages:
        role = message.get("role", "user").strip().lower()
        label = {
            "system": "System",
            "user": "User",
            "assistant": "Assistant",
            "tool": "Tool",
        }.get(role, role.title() or "User")
        lines.append(f"{label}: {message.get('content', '').strip()}")
    lines.append("Assistant:")
    return "\n\n".join(part for part in lines if part).strip()


class _IterativeDecoderRuntime:
    backend_name = "unknown"

    def __init__(self, config: RuntimeConfig) -> None:
        if not _configured(config):
            raise RuntimeConfigError(
                "APPLE_LLM_MODEL_PATH and APPLE_LLM_TOKENIZER_PATH must be configured"
            )
        self.config = config
        self._runtime_lock = Lock()
        self._tokenizer = None
        self._runtime_obj = None
        self._input_specs: list[InputSpec] = []

    def dependency_versions(self) -> dict[str, str | None]:
        return {
            "numpy": _package_version("numpy"),
            "transformers": _package_version("transformers"),
        }

    def check_ready(self) -> None:
        self._load_runtime()

    def available_models(self) -> list[str]:
        return [self.config.model_id]

    def describe(self) -> dict[str, Any]:
        details = {
            "backend": self.backend_name,
            "model_id": self.config.model_id,
            "model_path": self.config.model_path,
            "tokenizer_path": self.config.tokenizer_path,
            "compute_units": self.config.compute_units,
            "model_loaded": self._runtime_obj is not None,
        }
        if self._input_specs:
            details["input_specs"] = [
                {
                    "name": name,
                    "dtype": dtype_name,
                    "shape": shape_spec,
                }
                for name, dtype_name, shape_spec in self._input_specs
            ]
        return details

    def _embed_input_ids(self, token_ids):
        raise RuntimeConfigError(
            f"Model '{self.config.model_id}' requires embedded inputs, but "
            f"{self.backend_name} does not provide an embed_tokens runtime"
        )

    def _validate_runtime_config(self) -> None:
        return None

    def _load_runtime(self) -> None:
        with self._runtime_lock:
            if self._runtime_obj is not None and self._tokenizer is not None:
                return

            try:
                import numpy as np
            except Exception as exc:  # pragma: no cover
                raise RuntimeConfigError(
                    f"{self.backend_name} dependencies are not available: {exc}"
                ) from exc

            self._np = np
            self._validate_runtime_config()
            try:
                self._tokenizer = _load_tokenizer(
                    self.config.tokenizer_path,
                    trust_remote_code=self.config.trust_remote_code,
                )
            except Exception as exc:
                raise RuntimeConfigError(
                    f"Tokenizer could not be loaded from {self.config.tokenizer_path}: {exc}"
                ) from exc
            self._runtime_obj, self._input_specs = self._create_runtime()

    def _create_runtime(self):  # pragma: no cover
        raise NotImplementedError

    def _run_model(self, inputs: dict[str, Any]):  # pragma: no cover
        raise NotImplementedError

    def _run_step(
        self,
        inputs: dict[str, Any],
        *,
        cache_state: dict[str, Any] | None = None,
    ):
        return self._run_model(inputs)

    @staticmethod
    def _dtype_from_onnx(type_name: str):
        import numpy as np

        mapping = {
            "tensor(int32)": np.int32,
            "tensor(int64)": np.int64,
            "tensor(float)": np.float32,
            "tensor(float16)": np.float16,
            "tensor(double)": np.float64,
        }
        return mapping.get(type_name, np.int32)

    @staticmethod
    def _dtype_from_coreml(type_name: str):
        import numpy as np

        mapping = {
            "int32": np.int32,
            "int64": np.int64,
            "float32": np.float32,
            "float16": np.float16,
            "double": np.float64,
        }
        return mapping.get(type_name, np.int32)

    def _render_prompt(self, req: GenerateRequest) -> str:
        self._load_runtime()
        assert self._tokenizer is not None
        messages = [message.model_dump() for message in req.messages]
        chat_messages: list[dict[str, str]] = []
        if req.system:
            chat_messages.append({"role": "system", "content": req.system})
        chat_messages.extend(messages)

        tokenizer = self._tokenizer
        if hasattr(tokenizer, "apply_chat_template"):
            try:
                template_kwargs: dict[str, Any] = {}
                chat_template = getattr(tokenizer, "chat_template", "") or ""
                if "enable_thinking" in chat_template:
                    template_kwargs["enable_thinking"] = _env_flag(
                        "APPLE_LLM_ENABLE_THINKING",
                        False,
                    )
                return tokenizer.apply_chat_template(
                    chat_messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    **template_kwargs,
                )
            except Exception:
                pass

        return _fallback_prompt(messages, req.system)

    def _resolve_model(self, requested: str | None) -> str:
        if requested and requested != self.config.model_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model '{requested}' is not available. "
                    f"Configured model: {self.config.model_id}"
                ),
            )
        return self.config.model_id

    @staticmethod
    def _is_dynamic_dim(value: Any) -> bool:
        return not isinstance(value, int)

    def _empty_past_array(self, shape_spec: list[Any] | None, dtype):
        np = self._np
        if not shape_spec:
            raise RuntimeConfigError("Missing shape metadata for past_key_values input")

        resolved_shape: list[int] = []
        for index, dim in enumerate(shape_spec):
            if isinstance(dim, int):
                resolved_shape.append(dim)
                continue
            if index == 0:
                resolved_shape.append(1)
                continue
            resolved_shape.append(0)
        return np.zeros(tuple(resolved_shape), dtype=dtype)

    def _cache_length(self, cache_state: dict[str, Any]) -> int:
        sentinel_length = cache_state.get("__past_length__")
        if isinstance(sentinel_length, int) and sentinel_length >= 0:
            return sentinel_length
        for name, value in cache_state.items():
            if not name.startswith("past_key_values."):
                continue
            shape = getattr(value, "shape", None)
            if shape is not None and len(shape) >= 3:
                return int(shape[2])
        return 0

    def _build_position_ids(
        self,
        shape_spec: list[Any] | None,
        *,
        past_length: int,
        batch_size: int,
        seq_len: int,
    ):
        np = self._np
        positions = np.arange(past_length, past_length + seq_len, dtype=np.int64)

        if not shape_spec or len(shape_spec) <= 2:
            return np.broadcast_to(
                positions.reshape(1, seq_len),
                (batch_size, seq_len),
            ).copy()

        prefix_dim = shape_spec[0] if isinstance(shape_spec[0], int) and shape_spec[0] > 0 else 1
        return np.broadcast_to(
            positions.reshape(1, 1, seq_len),
            (prefix_dim, batch_size, seq_len),
        ).copy()

    def _build_causal_mask(
        self,
        shape_spec: list[Any] | None,
        *,
        past_length: int,
        batch_size: int,
        seq_len: int,
        total_len: int,
    ):
        np = self._np
        rank = len(shape_spec or [])
        if rank >= 4:
            mask = np.full((batch_size, 1, seq_len, total_len), -1e4, dtype=np.float32)
            for row in range(seq_len):
                allowed = min(total_len, past_length + row + 1)
                mask[:, :, row, :allowed] = 0.0
            return mask
        if rank == 3:
            mask = np.full((batch_size, seq_len, total_len), -1e4, dtype=np.float32)
            for row in range(seq_len):
                allowed = min(total_len, past_length + row + 1)
                mask[:, row, :allowed] = 0.0
            return mask
        if rank == 2:
            mask = np.full((seq_len, total_len), -1e4, dtype=np.float32)
            for row in range(seq_len):
                allowed = min(total_len, past_length + row + 1)
                mask[row, :allowed] = 0.0
            return mask
        if rank == 1:
            return np.zeros((total_len,), dtype=np.float32)
        return np.zeros((batch_size, 1, seq_len, total_len), dtype=np.float32)

    def _prepare_inputs(self, token_ids, *, cache_state: dict[str, Any] | None = None):
        assert self._tokenizer is not None
        np = self._np
        cache_state = cache_state or {}
        past_length = self._cache_length(cache_state)
        seq_len = token_ids.shape[1]
        total_len = past_length + seq_len
        inputs: dict[str, Any] = {}
        embedded_tokens = None

        for name, type_name, shape_spec in self._input_specs:
            lower = name.lower()
            if lower in {"input_ids", "inputids"} or lower.endswith(".input_ids"):
                source = token_ids
            elif lower == "inputs_embeds" or lower.endswith(".inputs_embeds"):
                if embedded_tokens is None:
                    embedded_tokens = self._embed_input_ids(token_ids)
                source = embedded_tokens
            elif "attention_mask" in lower:
                source = np.ones((token_ids.shape[0], total_len), dtype=np.int64)
            elif "position_ids" in lower:
                source = self._build_position_ids(
                    shape_spec,
                    past_length=past_length,
                    batch_size=token_ids.shape[0],
                    seq_len=seq_len,
                )
            elif lower in {"causalmask", "causal_mask"} or lower.endswith(".causalmask"):
                source = self._build_causal_mask(
                    shape_spec,
                    past_length=past_length,
                    batch_size=token_ids.shape[0],
                    seq_len=seq_len,
                    total_len=total_len,
                )
            elif (
                lower.startswith("past_key_values.")
                or lower.startswith("past_conv.")
                or lower.startswith("past_recurrent.")
            ):
                if name in cache_state:
                    source = cache_state[name]
                else:
                    if self.backend_name == "onnx-coreml":
                        dtype = self._dtype_from_onnx(type_name)
                    else:
                        dtype = self._dtype_from_coreml(type_name)
                    source = self._empty_past_array(shape_spec, dtype)
            else:
                raise RuntimeConfigError(
                    f"Unsupported model input '{name}'. "
                    "Supported inputs: input_ids/inputIds, inputs_embeds, attention_mask, "
                    "position_ids, causalMask, past_key_values.*, past_conv.*, "
                    "past_recurrent.*"
                )

            if self.backend_name == "onnx-coreml":
                dtype = self._dtype_from_onnx(type_name)
            else:
                dtype = self._dtype_from_coreml(type_name)
            inputs[name] = source.astype(dtype, copy=False)

        return inputs

    def _extract_logits(self, outputs: dict[str, Any]):
        np = self._np
        for key, value in outputs.items():
            if "logits" in key.lower():
                return np.asarray(value)
        for value in outputs.values():
            array = np.asarray(value)
            if array.ndim >= 2:
                return array
        raise RuntimeConfigError("The selected model did not return logits")

    def _extract_cache_state(
        self,
        outputs: dict[str, Any],
        *,
        previous_cache_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        remapped: dict[str, Any] = {}
        for name, value in outputs.items():
            if name.startswith("present."):
                remapped[name.replace("present.", "past_key_values.", 1)] = value
            elif name.startswith("present_conv."):
                remapped[name.replace("present_conv.", "past_conv.", 1)] = value
            elif name.startswith("present_recurrent."):
                remapped[name.replace("present_recurrent.", "past_recurrent.", 1)] = value
        return remapped

    def _sample_token(self, logits, temperature: float) -> int:
        np = self._np
        vector = np.asarray(logits, dtype=np.float64)
        if temperature <= 0.05:
            return int(np.argmax(vector))
        scaled = vector / max(temperature, 1e-5)
        scaled -= scaled.max()
        probs = np.exp(scaled)
        probs /= probs.sum()
        return int(np.random.default_rng().choice(len(probs), p=probs))

    def generate(self, req: GenerateRequest) -> dict[str, Any]:
        self._load_runtime()
        assert self._tokenizer is not None
        np = self._np
        model = self._resolve_model(req.model)
        prompt = self._render_prompt(req)
        max_new_tokens = req.max_tokens or self.config.max_new_tokens

        encoded = self._tokenizer(
            prompt,
            return_tensors="np",
            truncation=True,
            max_length=self.config.max_input_tokens,
        )
        input_ids = np.asarray(encoded["input_ids"], dtype=np.int32)
        prompt_tokens = int(input_ids.shape[1])
        generated = input_ids
        current_input_ids = input_ids
        cache_state: dict[str, Any] | None = None
        produced: list[int] = []

        eos_token_id = getattr(self._tokenizer, "eos_token_id", None)

        for _ in range(max_new_tokens):
            prepared_inputs = self._prepare_inputs(
                current_input_ids,
                cache_state=cache_state,
            )
            outputs = self._run_step(
                prepared_inputs,
                cache_state=cache_state,
            )
            logits = self._extract_logits(outputs)
            next_logits = logits[0, -1] if logits.ndim >= 3 else logits[-1]
            next_token = self._sample_token(next_logits, req.temperature)
            produced.append(next_token)
            next_token_ids = np.array([[next_token]], dtype=generated.dtype)
            generated = np.concatenate([generated, next_token_ids], axis=1)
            next_cache_state = self._extract_cache_state(
                outputs,
                previous_cache_state=cache_state,
            )
            if next_cache_state:
                next_cache_state["__past_length__"] = max(0, generated.shape[1] - 1)
                cache_state = next_cache_state
                current_input_ids = next_token_ids
            else:
                current_input_ids = generated
            if eos_token_id is not None and next_token == int(eos_token_id):
                break

        content = self._tokenizer.decode(produced, skip_special_tokens=True).strip()
        finish_reason = "stop" if produced and produced[-1] == eos_token_id else "length"

        return {
            "content": content,
            "model": model,
            "backend": self.backend_name,
            "finish_reason": finish_reason,
            "usage": {
                "input_tokens": prompt_tokens,
                "output_tokens": len(produced),
            },
        }


class CoreMLRuntime(_IterativeDecoderRuntime):
    backend_name = "coreml"

    def dependency_versions(self) -> dict[str, str | None]:
        versions = super().dependency_versions()
        versions["coremltools"] = _package_version("coremltools")
        return versions

    def describe(self) -> dict[str, Any]:
        details = super().describe()
        if self._runtime_obj is not None:
            if self._runtime_obj.get("embed_model_path"):
                details["embed_model_path"] = self._runtime_obj["embed_model_path"]
            details["stateful"] = bool(self._runtime_obj.get("state_specs"))
            if self._runtime_obj.get("state_specs"):
                details["state_specs"] = [
                    {
                        "name": name,
                        "dtype": dtype_name,
                        "shape": shape_spec,
                    }
                    for name, dtype_name, shape_spec in self._runtime_obj["state_specs"]
                ]
        return details

    def _validate_runtime_config(self) -> None:
        _require_model_artifact(
            self.config.model_path,
            backend="coreml",
            label="APPLE_LLM_MODEL_PATH",
        )
        if self.config.embed_model_path:
            _require_model_artifact(
                self.config.embed_model_path,
                backend="coreml",
                label="APPLE_LLM_EMBED_MODEL_PATH",
            )

    @staticmethod
    def _shape_from_coreml_array(multi_array) -> list[Any] | None:
        shape = list(getattr(multi_array, "shape", []) or [])
        if shape:
            return shape

        shape_range = getattr(multi_array, "shapeRange", None)
        size_ranges = list(getattr(shape_range, "sizeRanges", []) or [])
        if not size_ranges:
            return None

        resolved_shape: list[Any] = []
        for index, item in enumerate(size_ranges):
            lower = getattr(item, "lowerBound", None)
            upper = getattr(item, "upperBound", None)
            if isinstance(lower, int) and isinstance(upper, int) and lower == upper and lower >= 0:
                resolved_shape.append(lower)
            else:
                resolved_shape.append(f"dim_{index}")
        return resolved_shape

    @classmethod
    def _input_specs_from_spec(cls, spec) -> list[InputSpec]:
        input_specs: list[InputSpec] = []
        for feature in spec.description.input:
            multi_array = getattr(feature.type, "multiArrayType", None)
            dtype_name = "int32"
            shape = None
            if multi_array is not None:
                data_type = getattr(multi_array, "dataType", None)
                dtype_name = {
                    65568: "int32",
                    131104: "float32",
                    65552: "double",
                    65600: "float16",
                    131072: "int64",
                }.get(data_type, "int32")
                shape = cls._shape_from_coreml_array(multi_array)
            input_specs.append((feature.name, dtype_name, shape))
        return input_specs

    @classmethod
    def _state_specs_from_spec(cls, spec) -> list[StateSpec]:
        state_specs: list[StateSpec] = []
        for feature in getattr(spec.description, "state", []):
            wrapped = getattr(feature.type, "stateType", None)
            if wrapped is None:
                continue
            multi_array = getattr(wrapped, "arrayType", None)
            dtype_name = "float32"
            shape = None
            if multi_array is not None:
                data_type = getattr(multi_array, "dataType", None)
                dtype_name = {
                    65568: "int32",
                    131104: "float32",
                    65552: "double",
                    65600: "float16",
                    131072: "int64",
                }.get(data_type, "float32")
                shape = cls._shape_from_coreml_array(multi_array)
            state_specs.append((feature.name, dtype_name, shape))
        return state_specs

    def _resolve_embed_model_path(self) -> str | None:
        if self.config.embed_model_path:
            return str(
                _require_model_artifact(
                    self.config.embed_model_path,
                    backend="coreml",
                    label="APPLE_LLM_EMBED_MODEL_PATH",
                )
            )

        model_path = Path(self.config.model_path)
        candidates: list[Path] = []
        name = model_path.name
        suffix = model_path.suffix

        if name.startswith("decoder_model_merged"):
            candidates.append(
                model_path.with_name(f"embed_tokens{name[len('decoder_model_merged'):]}")
            )
        elif name.startswith("decoder_model"):
            candidates.append(
                model_path.with_name(f"embed_tokens{name[len('decoder_model'):]}")
            )

        candidates.extend(
            [
                model_path.with_name(f"embed_tokens{suffix}"),
                model_path.with_name("embed_tokens.mlpackage"),
                model_path.with_name("embed_tokens.mlmodelc"),
            ]
        )

        seen: set[str] = set()
        for candidate in candidates:
            resolved = str(candidate)
            if resolved in seen:
                continue
            seen.add(resolved)
            if candidate.exists():
                return resolved
        return None

    def _create_runtime(self):
        _require_model_artifact(
            self.config.model_path,
            backend="coreml",
            label="APPLE_LLM_MODEL_PATH",
        )
        try:
            import coremltools as ct
        except Exception as exc:  # pragma: no cover
            raise RuntimeConfigError(
                f"coremltools is not available: {exc}"
            ) from exc

        compute_units_name = {
            "all": "ALL",
            "cpu_only": "CPU_ONLY",
            "cpu_and_gpu": "CPU_AND_GPU",
            "cpu_and_ne": "CPU_AND_NE",
        }[self.config.compute_units]
        compute_units = getattr(ct.ComputeUnit, compute_units_name)
        decoder_model = ct.models.MLModel(self.config.model_path, compute_units=compute_units)
        input_specs = self._input_specs_from_spec(decoder_model.get_spec())
        state_specs = self._state_specs_from_spec(decoder_model.get_spec())
        runtime: dict[str, Any] = {
            "decoder": decoder_model,
            "state_specs": state_specs,
        }
        needs_embeds = any(
            name.lower() == "inputs_embeds" or name.lower().endswith(".inputs_embeds")
            for name, _, _ in input_specs
        )
        if needs_embeds:
            embed_model_path = self._resolve_embed_model_path()
            if not embed_model_path:
                raise RuntimeConfigError(
                    "Model requires inputs_embeds, but no Core ML embed_tokens sibling "
                    f"was found next to {self.config.model_path}"
                )
            runtime["embed_model_path"] = embed_model_path
            runtime["embed"] = ct.models.MLModel(embed_model_path, compute_units=compute_units)
        return runtime, input_specs

    def _run_model(self, inputs: dict[str, Any]):
        assert self._runtime_obj is not None
        return self._runtime_obj["decoder"].predict(inputs)

    def _run_step(
        self,
        inputs: dict[str, Any],
        *,
        cache_state: dict[str, Any] | None = None,
    ):
        assert self._runtime_obj is not None
        if not self._runtime_obj.get("state_specs"):
            return self._run_model(inputs)

        state = None
        if cache_state is not None:
            state = cache_state.get("__coreml_state__")
        if state is None:
            state = self._runtime_obj["decoder"].make_state()
        outputs = self._runtime_obj["decoder"].predict(inputs, state=state)
        return {
            "__coreml_state__": state,
            **outputs,
        }

    def _embed_input_ids(self, token_ids):
        assert self._runtime_obj is not None
        embed_model = self._runtime_obj.get("embed")
        if embed_model is None:
            raise RuntimeConfigError(
                f"Model '{self.config.model_id}' requires embed_tokens, but no Core ML "
                "embed runtime is configured"
            )
        embed_spec = embed_model.get_spec()
        if not embed_spec.description.input or not embed_spec.description.output:
            raise RuntimeConfigError(
                f"Embed model for '{self.config.model_id}' does not expose a valid input/output spec"
            )
        input_feature = embed_spec.description.input[0]
        output_feature = embed_spec.description.output[0]
        multi_array = getattr(input_feature.type, "multiArrayType", None)
        input_dtype = "int32"
        if multi_array is not None:
            data_type = getattr(multi_array, "dataType", None)
            input_dtype = {
                65568: "int32",
                131072: "int64",
            }.get(data_type, "int32")
        values = embed_model.predict(
            {
                input_feature.name: token_ids.astype(
                    self._dtype_from_coreml(input_dtype),
                    copy=False,
                )
            }
        )
        return self._np.asarray(values[output_feature.name])

    def _extract_cache_state(
        self,
        outputs: dict[str, Any],
        *,
        previous_cache_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        remapped = super()._extract_cache_state(
            outputs,
            previous_cache_state=previous_cache_state,
        )
        state = outputs.get("__coreml_state__")
        if state is not None:
            remapped["__coreml_state__"] = state
        elif previous_cache_state and "__coreml_state__" in previous_cache_state:
            remapped["__coreml_state__"] = previous_cache_state["__coreml_state__"]
        return remapped


class OnnxCoreMLRuntime(_IterativeDecoderRuntime):
    backend_name = "onnx-coreml"

    def dependency_versions(self) -> dict[str, str | None]:
        versions = super().dependency_versions()
        versions["onnxruntime"] = _package_version("onnxruntime")
        return versions

    def describe(self) -> dict[str, Any]:
        details = super().describe()
        if self._runtime_obj is not None and self._runtime_obj.get("embed_model_path"):
            details["embed_model_path"] = self._runtime_obj["embed_model_path"]
        return details

    def _validate_runtime_config(self) -> None:
        _require_model_artifact(
            self.config.model_path,
            backend="onnx-coreml",
            label="APPLE_LLM_MODEL_PATH",
        )
        if self.config.embed_model_path:
            _require_model_artifact(
                self.config.embed_model_path,
                backend="onnx-coreml",
                label="APPLE_LLM_EMBED_MODEL_PATH",
            )

    def _resolve_embed_model_path(self) -> str | None:
        if self.config.embed_model_path:
            return str(
                _require_model_artifact(
                    self.config.embed_model_path,
                    backend="onnx-coreml",
                    label="APPLE_LLM_EMBED_MODEL_PATH",
                )
            )

        model_path = Path(self.config.model_path)
        candidates: list[Path] = []
        name = model_path.name

        if name.startswith("decoder_model_merged"):
            suffix = name[len("decoder_model_merged") :]
            candidates.append(model_path.with_name(f"embed_tokens{suffix}"))
        elif name.startswith("decoder_model"):
            suffix = name[len("decoder_model") :]
            candidates.append(model_path.with_name(f"embed_tokens{suffix}"))

        candidates.extend(
            [
                model_path.with_name("embed_tokens.onnx"),
                model_path.with_name("embed_tokens_fp16.onnx"),
                model_path.with_name("embed_tokens_q4f16.onnx"),
                model_path.with_name("embed_tokens_q4.onnx"),
                model_path.with_name("embed_tokens_quantized.onnx"),
            ]
        )

        seen: set[str] = set()
        for candidate in candidates:
            resolved = str(candidate)
            if resolved in seen:
                continue
            seen.add(resolved)
            if candidate.exists():
                return resolved
        return None

    def _create_runtime(self):
        _require_model_artifact(
            self.config.model_path,
            backend="onnx-coreml",
            label="APPLE_LLM_MODEL_PATH",
        )
        try:
            import onnxruntime as ort
        except Exception as exc:  # pragma: no cover
            raise RuntimeConfigError(
                f"onnxruntime is not available: {exc}"
            ) from exc

        provider_options = {
            "ModelFormat": os.getenv("APPLE_LLM_ORT_MODEL_FORMAT", "MLProgram"),
            "MLComputeUnits": {
                "all": "ALL",
                "cpu_only": "CPUOnly",
                "cpu_and_gpu": "CPUAndGPU",
                "cpu_and_ne": "CPUAndNeuralEngine",
            }[self.config.compute_units],
            "RequireStaticInputShapes": os.getenv(
                "APPLE_LLM_ORT_REQUIRE_STATIC_INPUT_SHAPES",
                "0",
            ),
            "EnableOnSubgraphs": os.getenv("APPLE_LLM_ORT_ENABLE_ON_SUBGRAPHS", "0"),
        }
        coreml_session = ort.InferenceSession(
            self.config.model_path,
            providers=[
                ("CoreMLExecutionProvider", provider_options),
                "CPUExecutionProvider",
            ],
        )
        cpu_session = ort.InferenceSession(
            self.config.model_path,
            providers=["CPUExecutionProvider"],
        )
        input_specs = [
            (item.name, item.type, list(item.shape))
            for item in coreml_session.get_inputs()
        ]
        runtime = {
            "coreml": coreml_session,
            "cpu": cpu_session,
        }
        needs_embeds = any(
            name.lower() == "inputs_embeds" or name.lower().endswith(".inputs_embeds")
            for name, _, _ in input_specs
        )
        if needs_embeds:
            embed_model_path = self._resolve_embed_model_path()
            if not embed_model_path:
                raise RuntimeConfigError(
                    "Model requires inputs_embeds, but no embed_tokens*.onnx sibling "
                    f"was found next to {self.config.model_path}"
                )
            runtime["embed_model_path"] = embed_model_path
            runtime["embed_coreml"] = ort.InferenceSession(
                embed_model_path,
                providers=[
                    ("CoreMLExecutionProvider", provider_options),
                    "CPUExecutionProvider",
                ],
            )
            runtime["embed_cpu"] = ort.InferenceSession(
                embed_model_path,
                providers=["CPUExecutionProvider"],
            )
        return runtime, input_specs

    def _run_model(self, inputs: dict[str, Any]):
        assert self._runtime_obj is not None
        session = self._runtime_obj["coreml"]
        output_names = [item.name for item in session.get_outputs()]
        values = session.run(output_names, inputs)
        return dict(zip(output_names, values, strict=False))

    def _run_step(
        self,
        inputs: dict[str, Any],
        *,
        cache_state: dict[str, Any] | None = None,
    ):
        assert self._runtime_obj is not None
        has_past_inputs = any(name.startswith("past_key_values.") for name, _, _ in self._input_specs)
        use_cpu_session = has_past_inputs and not cache_state
        session = self._runtime_obj["cpu"] if use_cpu_session else self._runtime_obj["coreml"]
        output_names = [item.name for item in session.get_outputs()]
        values = session.run(output_names, inputs)
        return dict(zip(output_names, values, strict=False))

    def _embed_input_ids(self, token_ids):
        assert self._runtime_obj is not None

        def _run(session_key: str):
            session = self._runtime_obj.get(session_key)
            if session is None:
                raise RuntimeConfigError(
                    f"Model '{self.config.model_id}' requires embed_tokens, but no "
                    f"{session_key} session is configured"
                )
            input_meta = session.get_inputs()[0]
            output_name = session.get_outputs()[0].name
            input_dtype = self._dtype_from_onnx(input_meta.type)
            values = session.run(
                [output_name],
                {
                    input_meta.name: token_ids.astype(input_dtype, copy=False),
                },
            )
            return self._np.asarray(values[0])

        try:
            return _run("embed_coreml")
        except Exception:
            return _run("embed_cpu")


def _build_runtime(config: RuntimeConfig) -> RuntimeState:
    if config.backend == "onnx-coreml":
        return OnnxCoreMLRuntime(config)
    return CoreMLRuntime(config)


def _resolve_runtime() -> RuntimeState:
    config = _runtime_config()
    with _runtime_lock:
        global _runtime_cache, _runtime_signature
        if _runtime_cache is not None and _runtime_signature == config:
            return _runtime_cache
        runtime = _build_runtime(config)
        _runtime_cache = runtime
        _runtime_signature = config
        return runtime


@app.get("/health")
async def health() -> dict[str, Any]:
    config = _runtime_config()
    configured = _configured(config)
    runtime_ready = False
    runtime_error: str | None = None
    details: dict[str, Any] = {
        "backend": config.backend,
        "configured": configured,
        "model_id": config.model_id,
        "model_path": config.model_path or None,
        "embed_model_path": config.embed_model_path or None,
        "tokenizer_path": config.tokenizer_path or None,
        "compute_units": config.compute_units,
        "max_input_tokens": config.max_input_tokens,
        "max_new_tokens": config.max_new_tokens,
    }

    if configured:
        try:
            runtime = _resolve_runtime()
            runtime.check_ready()
            runtime_ready = True
            details.update(runtime.describe())
            details["dependencies"] = runtime.dependency_versions()
        except RuntimeConfigError as exc:
            runtime_error = str(exc)
            details["dependencies"] = {
                "numpy": _package_version("numpy"),
                "transformers": _package_version("transformers"),
                "coremltools": _package_version("coremltools"),
                "onnxruntime": _package_version("onnxruntime"),
            }
    else:
        runtime_error = "APPLE_LLM_MODEL_PATH and APPLE_LLM_TOKENIZER_PATH must be configured"
        details["dependencies"] = {
            "numpy": _package_version("numpy"),
            "transformers": _package_version("transformers"),
            "coremltools": _package_version("coremltools"),
            "onnxruntime": _package_version("onnxruntime"),
        }

    return {
        "ok": True,
        "runtime_ready": runtime_ready,
        "runtime_error": runtime_error,
        **details,
    }


@app.get("/models")
async def models() -> dict[str, Any]:
    config = _runtime_config()
    if not _configured(config):
        return {"models": []}
    runtime = _resolve_runtime()
    return {
        "models": runtime.available_models(),
        "backend": runtime.backend_name,
    }


@app.post("/generate")
async def generate(req: GenerateRequest):
    config = _runtime_config()
    if not _configured(config):
        raise HTTPException(
            status_code=503,
            detail="APPLE_LLM_MODEL_PATH and APPLE_LLM_TOKENIZER_PATH must be configured",
        )

    try:
        # Use model_id from request or fall back to config default
        model_id = req.model or config.model_id
        runtime = _model_manager.load_model(model_id, config)
        return runtime.generate(req)
    except HTTPException:
        raise
    except RuntimeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc
