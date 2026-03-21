"""vLLM Provider - High-throughput LLM inference with continuous batching."""

from __future__ import annotations

import logging
from typing import AsyncIterator, Optional

try:
    from vllm import AsyncLLMEngine, SamplingParams
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine
    from vllm.outputs import RequestOutput
    from vllm.sampling_params import SamplingParams as VLLMSamplingParams
    VLLM_AVAILABLE = True
except ImportError:
    VLLM_AVAILABLE = False
    AsyncLLMEngine = object
    SamplingParams = object
    AsyncEngineArgs = object
    RequestOutput = object
    VLLMSamplingParams = object

from mascarade.router.providers.base import (
    LLMProvider,
    LLMResponse,
    LLMStreamChunk,
)
from mascarade.scheduler.scheduler import ScheduledRequest

logger = logging.getLogger("mascarade.vllm")


class VLLMProvider(LLMProvider):
    """vLLM provider with continuous batching and PagedAttention."""

    def __init__(
        self,
        model_path: str,
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.9,
        max_model_len: int = 8192,
        **kwargs,
    ):
        if not VLLM_AVAILABLE:
            raise RuntimeError("vLLM is not installed. Please install vllm.")

        self.model_path = model_path
        self.tensor_parallel_size = tensor_parallel_size
        self.gpu_memory_utilization = gpu_memory_utilization
        self.max_model_len = max_model_len
        self.engine: Optional[AsyncLLMEngine] = None
        self.engine_args = AsyncEngineArgs(
            model=model_path,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            max_model_len=max_model_len,
            **kwargs,
        )

    async def initialize(self) -> None:
        """Initialize the vLLM engine."""
        if self.engine is None:
            logger.info("Initializing vLLM engine for %s", self.model_path)
            self.engine = AsyncLLMEngine.from_engine_args(self.engine_args)
            logger.info("vLLM engine initialized successfully")

    async def generate(
        self,
        request: ScheduledRequest,
        stream: bool = False,
    ) -> AsyncIterator[LLMStreamChunk] | LLMResponse:
        """Generate response using vLLM continuous batching."""
        if self.engine is None:
            await self.initialize()

        # Convert request to vLLM format
        prompt = self._format_prompt(request.messages)
        sampling_params = self._create_sampling_params(request)

        # Add request to engine
        request_id = f"req_{request.request_id}"
        await self.engine.add_request(
            request_id=request_id,
            prompt=prompt,
            sampling_params=sampling_params,
        )

        if stream:
            return self._stream_response(request_id)
        else:
            return await self._get_full_response(request_id)

    async def _get_full_response(self, request_id: str) -> LLMResponse:
        """Get the complete response for a request."""
        output: Optional[RequestOutput] = None
        async for request_output in self.engine.stream_results(request_id):
            output = request_output

        if output is None:
            raise RuntimeError("No output generated for request")

        return LLMResponse(
            content=output.outputs[0].text,
            model=self.model_path,
            usage={
                "prompt_tokens": output.prompt_token_ids.shape[0],
                "completion_tokens": output.outputs[0].token_ids.shape[0],
                "total_tokens": output.prompt_token_ids.shape[0] + output.outputs[0].token_ids.shape[0],
            },
        )

    async def _stream_response(self, request_id: str) -> AsyncIterator[LLMStreamChunk]:
        """Stream the response for a request."""
        async for request_output in self.engine.stream_results(request_id):
            for output in request_output.outputs:
                yield LLMStreamChunk(
                    content=output.text,
                    model=self.model_path,
                    finish_reason=output.finish_reason,
                )

    def _format_prompt(self, messages: list[dict]) -> str:
        """Format messages into a prompt string."""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

    def _create_sampling_params(self, request: ScheduledRequest) -> VLLMSamplingParams:
        """Create vLLM sampling parameters."""
        return VLLMSamplingParams(
            temperature=request.temperature,
            top_p=request.top_p if hasattr(request, 'top_p') else 0.95,
            max_tokens=request.max_tokens,
            presence_penalty=getattr(request, 'presence_penalty', 0.0),
            frequency_penalty=getattr(request, 'frequency_penalty', 0.0),
        )

    async def close(self) -> None:
        """Clean up resources."""
        if self.engine is not None:
            await self.engine.close()
            self.engine = None
