"""vLLM Integration Layer for Mascarade Scheduler."""

from __future__ import annotations

import asyncio
import logging

from mascarade.router.providers.vllm_provider import VLLMProvider
from mascarade.scheduler.scheduler import ResourceAwareScheduler, ScheduledRequest
from mascarade.scheduler.worker_state import WorkerState

logger = logging.getLogger("mascarade.scheduler.vllm")


class VLLMWorker:
    """Worker specialized for vLLM inference."""

    def __init__(
        self,
        node_id: str,
        model_path: str,
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.9,
    ):
        self.node_id = node_id
        self.provider = VLLMProvider(
            model_path=model_path,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        self.current_requests: dict[str, ScheduledRequest] = {}
        self.batch_queue: asyncio.Queue[ScheduledRequest] = asyncio.Queue()
        self.processing = False

    async def initialize(self) -> None:
        """Initialize the vLLM provider."""
        await self.provider.initialize()

    async def add_request(self, request: ScheduledRequest) -> None:
        """Add a request to the batch queue."""
        await self.batch_queue.put(request)
        self.current_requests[request.request_id] = request

        if not self.processing:
            asyncio.create_task(self._process_batches())

    async def _process_batches(self) -> None:
        """Process batches using vLLM continuous batching."""
        self.processing = True

        try:
            while not self.batch_queue.empty():
                # Collect batch (vLLM handles continuous batching internally)
                request = await self.batch_queue.get()

                # Process with vLLM
                response = await self.provider.generate(request)

                # Complete the request
                if hasattr(request, "complete_callback"):
                    await request.complete_callback(response)

                # Clean up
                self.current_requests.pop(request.request_id, None)

        finally:
            self.processing = False

    async def get_status(self) -> dict:
        """Get worker status."""
        return {
            "node_id": self.node_id,
            "current_load": len(self.current_requests),
            "queue_size": self.batch_queue.qsize(),
            "model": self.provider.model_path,
        }

    async def close(self) -> None:
        """Clean up resources."""
        await self.provider.close()


class VLLMScheduler(ResourceAwareScheduler):
    """Scheduler with vLLM-specific optimizations."""

    def __init__(self):
        super().__init__()
        self.vllm_workers: dict[str, VLLMWorker] = {}
        self.mlx_workers: dict[str, MLXWorker] = {}

    async def register_vllm_worker(
        self,
        node_id: str,
        model_path: str,
        tensor_parallel_size: int = 1,
        gpu_memory_utilization: float = 0.9,
    ) -> None:
        """Register a vLLM worker."""
        worker = VLLMWorker(
            node_id=node_id,
            model_path=model_path,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        await worker.initialize()
        self.vllm_workers[node_id] = worker

        # Also register as regular worker
        worker_state = WorkerState(
            node_id=node_id,
            url=f"vllm://{node_id}",
            runtime="vllm",
            status="alive",
            loaded_models=[model_path],
            max_concurrent=16,  # vLLM handles batching
            supports_batching=True,
            max_batch_size=32,
        )
        self.register_worker(worker_state)

    async def register_mlx_worker(
        self,
        node_id: str,
        model_path: str,
        device: str = "mps",
        **kwargs,
    ) -> None:
        """Register an MLX worker for Apple Silicon."""
        from mascarade.router.providers.mlx_provider import MLXWorker

        worker = MLXWorker(
            node_id=node_id,
            model_path=model_path,
            device=device,
            **kwargs,
        )
        await worker.initialize()
        self.mlx_workers[node_id] = worker

        # Register as regular worker
        worker_state = WorkerState(
            node_id=node_id,
            url=f"mlx://{node_id}",
            runtime="mlx",
            status="alive",
            loaded_models=[model_path],
            max_concurrent=4,  # MLX has lower concurrency
            supports_batching=False,  # MLX doesn't support batching yet
            max_batch_size=1,
        )
        self.register_worker(worker_state)

    async def schedule_vllm_request(self, request: ScheduledRequest) -> None:
        """Schedule a request to a vLLM worker."""
        # Find best vLLM worker
        best_worker = None
        best_score = -1

        for _worker_id, worker in self.vllm_workers.items():
            if request.model in worker.provider.model_path:
                score = self._score_vllm_worker(worker, request)
                if score > best_score:
                    best_score = score
                    best_worker = worker

        if best_worker is None:
            raise RuntimeError(f"No vLLM worker available for model {request.model}")

        # Add to vLLM worker
        await best_worker.add_request(request)

    async def schedule_mlx_request(self, request: ScheduledRequest) -> None:
        """Schedule a request to an MLX worker."""
        # Find best MLX worker
        best_worker = None
        best_score = -1

        for _worker_id, worker in self.mlx_workers.items():
            if request.model in worker.provider.model_path:
                score = self._score_mlx_worker(worker, request)
                if score > best_score:
                    best_score = score
                    best_worker = worker

        if best_worker is None:
            raise RuntimeError(f"No MLX worker available for model {request.model}")

        # Process with MLX worker
        await best_worker.process_request(request)

    def _score_mlx_worker(self, worker: MLXWorker, request: ScheduledRequest) -> float:
        """Score an MLX worker for a request."""
        score = 0.0

        # Model affinity
        if request.model == worker.provider.model_path:
            score += 50

        # Load balancing
        load_ratio = len(worker.current_requests) / 4  # Max 4 concurrent
        score += 30 * (1 - load_ratio)

        # Prefer local workers for Apple Silicon
        if worker.provider.device == "mps":
            score += 20

        return score

    def _score_vllm_worker(self, worker: VLLMWorker, request: ScheduledRequest) -> float:
        """Score a vLLM worker for a request."""
        score = 0.0

        # Model affinity
        if request.model == worker.provider.model_path:
            score += 50

        # Load balancing
        load_ratio = worker.batch_queue.qsize() / worker.provider.engine_args.max_model_len
        score += 30 * (1 - load_ratio)

        # GPU memory
        score += 20 * worker.provider.gpu_memory_utilization

        return score

    async def get_vllm_status(self) -> dict:
        """Get status of all vLLM workers."""
        status = {}
        for worker_id, worker in self.vllm_workers.items():
            status[worker_id] = await worker.get_status()
        return status

    async def get_mlx_status(self) -> dict:
        """Get status of all MLX workers."""
        status = {}
        for worker_id, worker in self.mlx_workers.items():
            status[worker_id] = await worker.get_status()
        return status

    async def close_all(self) -> None:
        """Close all workers."""
        # Close vLLM workers
        for worker in self.vllm_workers.values():
            await worker.close()
        self.vllm_workers.clear()

        # Close MLX workers
        for worker in self.mlx_workers.values():
            await worker.close()
        self.mlx_workers.clear()
