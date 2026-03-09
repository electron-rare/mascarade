# Apple Silicon / M5 / Neural Engine History

Date: 2026-03-06

## Context

This note records the local audit, the external research, and the implementation state for adapting Mascarade to recent Apple Silicon machines, including M5-class Macs and Neural Engine aware workflows.

## Local Audit Findings

Mascarade is currently biased toward Linux, Docker, and CUDA/NVIDIA assumptions.

Main friction points identified in the repository:

- `setup` uses Linux-only commands such as `free`, `nproc`, and `/proc/meminfo`.
- `scripts/lib.sh` checks ports with `ss` and detects GPU with `nvidia-smi`.
- `scripts/lib.sh` tries to auto-install `gum` in a Linux-oriented way, which caused a password prompt on macOS.
- Multiple training/demo scripts assume `torch.cuda.*`.
- The `generate-audio` path is CUDA/CPU oriented and not Apple Silicon aware.
- `scripts/modules/ollama.sh` assumes a Docker-managed Ollama service instead of the native macOS Ollama app.
- `core/mascarade/router/providers/ollama.py` already supports a custom `OLLAMA_BASE_URL`, but the setup path does not configure a native host-Ollama flow.

Relevant files:

- `setup`
- `scripts/lib.sh`
- `scripts/prereqs.sh`
- `scripts/compose.sh`
- `scripts/modules/ollama.sh`
- ancien module de chat UI local retire du scope actif depuis 2026-03-08
- `core/mascarade/config.py`
- `core/mascarade/router/providers/ollama.py`

## Research Results

### 1. M5 is materially better for on-device AI

Apple documents the M5 family as AI-oriented hardware with a faster 16-core Neural Engine and new Neural Accelerators in GPU cores.

Useful sources:

- https://support.apple.com/en-us/125405
- https://www.apple.com/newsroom/2025/10/apple-unveils-new-14-inch-macbook-pro-powered-by-the-m5-chip/
- https://www.apple.com/newsroom/2026/03/apple-introduces-macbook-pro-with-all-new-m5-pro-and-m5-max/

Practical implication:

- Mascarade should treat Apple Silicon as a first-class runtime target, not as a reduced Linux fallback.

### 2. MLX is the Apple Silicon-native framework, but not the Neural Engine path

Apple's MLX is explicitly designed for Apple Silicon and uses unified memory, but the documented supported devices are currently CPU and GPU.

Useful sources:

- https://github.com/ml-explore/mlx
- https://github.com/ml-explore/mlx-lm

Practical implication:

- MLX and `mlx-lm` are strong candidates for local LLM inference/fine-tuning on Apple Silicon.
- MLX is not the right answer if the specific goal is "use the Neural Engine"; it is primarily CPU/GPU oriented.

### 3. PyTorch MPS targets Metal GPU, not the Neural Engine

PyTorch's `mps` backend is the official Apple Silicon path for GPU acceleration in PyTorch.

Useful source:

- https://docs.pytorch.org/docs/stable/notes/mps.html

Practical implication:

- PyTorch MPS is useful for local experimentation and for making CUDA-only scripts less Linux-bound.
- It does not replace a Core ML / Neural Engine deployment path.

### 4. Core ML is the official Neural Engine route

Apple's Core ML Tools documentation states that conversion from PyTorch directly to Core ML is recommended, and Core ML compute units can include the Neural Engine.

Useful sources:

- https://apple.github.io/coremltools/docs-guides/source/convert-pytorch.html
- https://apple.github.io/coremltools/docs-guides/source/convert-pytorch-workflow.html
- https://apple.github.io/coremltools/docs-guides/source/load-and-convert-model.html
- https://apple.github.io/coremltools/source/coremltools.models.html

Important practical detail:

- `ComputeUnit.ALL` uses all available compute units, including the Neural Engine.
- `ComputeUnit.CPU_AND_NE` exists for CPU + Neural Engine execution.

Practical implication:

- If Mascarade wants a real Neural Engine path, it needs a Core ML compatible inference path, not only Docker + PyTorch + Ollama.

### 5. ONNX Runtime CoreML EP is a valid bridge when models are already in ONNX

ONNX Runtime documents a CoreML Execution Provider that can target Apple hardware, including ANE-oriented options.

Useful source:

- https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html

Important practical detail:

- ONNX Runtime documents `COREML_FLAG_ONLY_ENABLE_DEVICE_WITH_ANE`.

Practical implication:

- For some models, ONNX Runtime + CoreML EP may be the lowest-friction way to expose ANE-backed inference in a service.

### 6. Foundation Models is an official Apple on-device model path, but it is Swift/Xcode centric

Apple documents the Foundation Models framework as the way to access the on-device model at the core of Apple Intelligence.

Useful sources:

- https://developer.apple.com/apple-intelligence/resources/
- https://developer.apple.com/events/resources/code-along-205/

Practical implication:

- This is relevant if Mascarade adds a native macOS/iOS-sidecar or Swift bridge.
- It is not a direct drop-in replacement for the current Python/TypeScript server architecture.

### 7. Native Ollama on macOS is useful for Apple Silicon, but it is CPU/GPU support, not Neural Engine support

Ollama now has a native macOS app and its macOS docs explicitly mention Apple M-series support with CPU and GPU support.

Useful sources:

- https://docs.ollama.com/macos
- https://docs.ollama.com/quickstart
- https://ollama.com/download/mac
- https://ollama.com/blog/new-app

Practical implication:

- On macOS, Mascarade should prefer native host Ollama over Dockerized Ollama for local model serving.
- This improves Apple Silicon ergonomics, but it should not be described as a Neural Engine integration.

## Implementation State

### Executed on the machine

- Installed a recent Homebrew Bash on the machine: `bash 5.3.9`.
- Verified that `./setup --help` now works with the Homebrew Bash.
- Built and started `core` and `api` manually with Docker Compose.
- Verified both services healthy before the Apple Silicon adaptation request changed scope.

### Applied in the repository

The first Apple Silicon batch is now implemented:

1. `setup` and shared shell helpers are portable on macOS:
   - Linux-only resource detection was replaced with macOS-compatible helpers
   - port checks no longer depend on `ss`
   - Apple Silicon detection was added

2. The bootstrap flow is macOS-aware:
   - Homebrew is preferred for `gum`
   - Docker access logic no longer assumes Linux `sudo` / docker-group flows

3. A dedicated `apple-silicon` profile now exists:
   - `setup --profile apple-silicon`
   - host Ollama is preferred when available

4. Native host Ollama support is wired end-to-end:
   - `OLLAMA_HOST_MODE`
   - `OLLAMA_BASE_URL`
   - API monitoring now probes the configured base URL

5. A first real Neural Engine integration boundary now exists:
   - new host-native service: `deploy/apple_llm_api/app.py`
   - new provider: `core/mascarade/router/providers/apple_coreml.py`
   - supported backends:
     - `coreml`
     - `onnx-coreml`
   - the provider name exposed to Mascarade is `apple-coreml`

6. Launch and verification tooling was added:
   - `scripts/run_apple_llm_service.sh`
   - `scripts/smoke_apple_llm.sh`
   - `scripts/install_apple_llm_model.sh`
   - `.env.example` and `README.md` now document the Apple LLM path

### First integrated reference model

The first concrete model path selected for this machine is:

- repository: `onnx-community/Qwen2.5-0.5B-Instruct`
- runtime: `onnx-coreml`
- file: `onnx/model.onnx`

Why this one:

- it is still small enough for a practical M5 proof path
- it is more useful than the tiny fallback models
- the repository ships ONNX artifacts directly
- on this machine, the plain `model.onnx` variant validates end-to-end with the CoreML EP path

### Implemented on the Apple M5 machine

The following concrete integration has now been executed locally on the machine:

- machine detected: Apple M5
- RAM detected: 16 GB
- downloaded model:
  - repo: `onnx-community/Qwen2.5-0.5B-Instruct`
  - local path: `/Users/electron/Models/mascarade/apple-llm/Qwen2.5-0.5B-Instruct-model`
  - ONNX file: `onnx/model.onnx`
- local `.env` now points Mascarade to:
  - `APPLE_LLM_ENABLED=true`
  - `APPLE_LLM_BACKEND=onnx-coreml`
  - `APPLE_LLM_MODEL_ID=qwen2.5-0.5b-instruct-onnx`
  - `APPLE_LLM_BASE_URL=http://host.docker.internal:8201`

### Runtime validation completed

Validation completed successfully on 2026-03-06:

- the host-native Apple LLM service starts on `http://127.0.0.1:8201`
- `/health` returns `runtime_ready: true`
- `/models` returns `qwen2.5-0.5b-instruct-onnx`
- `/generate` succeeds after adding support for ONNX `past_key_values`
- after rebuilding Docker images, Mascarade Core exposes:
  - `providers: ["apple-coreml"]`
- end-to-end API routing succeeds through:
  - `api -> core -> apple-llm`

Important nuance:

- ONNX Runtime is configured with `MLComputeUnits=CPUAndNeuralEngine`
- this validates the configured CoreML EP path for ANE-capable execution
- it is not a benchmark or a hardware counter proof of how much work was actually placed on ANE versus CPU fallback

### Correction after variant testing

The initial failure diagnosis for Qwen was incomplete.

What actually happened:

- `onnx-community/Qwen2.5-0.5B-Instruct` with `onnx/model_fp16.onnx` failed on this machine
- `onnx-community/Qwen2.5-0.5B-Instruct` with `onnx/model_q4f16.onnx` was not retained either
- `onnx-community/Qwen2.5-0.5B-Instruct` with `onnx/model.onnx` does work end-to-end

Practical conclusion:

- the failure was variant-specific, not model-family-wide
- the corrected default reference on this machine is Qwen 0.5B using `onnx/model.onnx`

### Additional validated fallback

`HuggingFaceTB/SmolLM2-360M-Instruct` was also validated locally and remains a useful fallback when a smaller, simpler ONNX graph is preferred.

### Important scope limit

This is a practical v1 integration, not a full production-grade ANE runtime:

- the service uses a simple autoregressive generation loop over logits
- it assumes a decoder model exported in a shape Mascarade can drive with `input_ids` and optional masks
- KV-cache optimized generation is not implemented yet
- Foundation Models / Swift sidecar integration is still a separate future path

## Proposed Direction

Recommended runtime split for Apple Silicon:

- Native Ollama on macOS: best simple local LLM serving path for Mascarade today.
- MLX / `mlx-lm`: best Apple Silicon-native path for experimentation and fine-tuning.
- Core ML / coremltools: official route for actual Neural Engine usage.
- ONNX Runtime CoreML EP: bridge path when the model is already available in ONNX.
- Foundation Models: future Swift bridge option for Apple-native on-device model use.

## Historical Summary

As of 2026-03-06:

- Mascarade can run locally on this Mac.
- The repo now has a first-class Apple Silicon bootstrap path and a first Neural Engine oriented provider/service boundary.
- The correct technical direction is still not "make CUDA scripts run on Mac"; it is to split Apple Silicon support into:
  - Metal/CPU-GPU local paths: native Ollama, MLX, PyTorch MPS
  - Neural Engine paths: Core ML, ONNX Runtime CoreML EP, and later Foundation Models for native Apple app integrations

## 2026-03-06: Qwen3.5-4B-ONNX runtime extension

Current validated modern default:

- model family: `Qwen/Qwen3.5-4B`
- local ONNX package: `onnx-community/Qwen3.5-4B-ONNX`
- selected variant: `onnx/decoder_model_merged_q4f16.onnx`
- paired embedding graph: `onnx/embed_tokens_q4f16.onnx`
- local path: `/Users/electron/Models/mascarade/apple-llm/Qwen3.5-4B-ONNX-q4f16`
- configured model id: `qwen3.5-4b-onnx-q4f16`

What changed in the service:

- tokenizer loading now falls back to `PreTrainedTokenizerFast` when an ONNX export declares `TokenizersBackend`
- ONNX runtime now supports decoder graphs that consume `inputs_embeds` instead of `input_ids`
- the service auto-detects a sibling `embed_tokens*.onnx` graph when needed
- input preparation now handles 3D `position_ids`
- cache handling now supports `past_conv.*` and `past_recurrent.*` in addition to `past_key_values.*`

Local validation:

- isolated host service booted successfully on `http://127.0.0.1:8202`
- `/health` returned `runtime_ready: true`
- `/models` returned `qwen3.5-4b-onnx-q4f16`
- `/generate` succeeded end-to-end with `backend: onnx-coreml`
- `APPLE_LLM_ENABLE_THINKING=false` was then enabled so direct prompts return concise answers without `<think>` blocks

Operational note:

- `Qwen3.5-4B` is the most modern validated local model on this machine as of `2026-03-06`
- `Qwen2.5-0.5B-Instruct` remains documented as a smaller fallback, but it is no longer the preferred default

## 2026-03-07: Native Core ML runtime hardening

The host Apple LLM service was extended so `APPLE_LLM_BACKEND=coreml` is no longer just a config placeholder.

What changed:

- `APPLE_LLM_EMBED_MODEL_PATH` was added for models that require a separate `embed_tokens` Core ML artifact
- the service now rejects `.onnx` paths early when `APPLE_LLM_BACKEND=coreml`
- `/health` now surfaces the runtime input specs so native Core ML models can be inspected without opening the package manually
- the native `coreml` runtime can auto-discover sibling `embed_tokens*.mlpackage` / `embed_tokens*.mlmodelc` artifacts
- a staging helper was added: `scripts/stage_apple_coreml_model.sh`
- the native `coreml` runtime now supports stateful Core ML models via `MLModel.make_state()`
- an acquisition helper was added for official Core ML packages: `scripts/install_apple_coreml_model.sh`
- the first real run against `apple/mistral-coreml` exposed a Python runtime constraint: `coremltools` installed under Python 3.14 but failed to load `libmodelpackage`, so the launcher now prefers Python 3.12 for `APPLE_LLM_BACKEND=coreml`

Practical effect:

- `onnx-coreml` remains the current validated fallback on this machine
- `coreml` is now a real first-class runtime path for future `.mlpackage` exports, with a stable config/env contract already wired into Mascarade
