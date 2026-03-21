"""Heartbeat monitor — probes workers for health and resource metrics."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from mascarade.scheduler.worker_state import WorkerState, WorkerStatus

logger = logging.getLogger("mascarade.scheduler.heartbeat")

HEARTBEAT_INTERVAL_S = 5
DEAD_THRESHOLD = 3
SLOW_THRESHOLD_MS = 5000


class HeartbeatMonitor:
    """Periodically probes workers to track health and resource usage."""

    def __init__(
        self,
        workers: dict[str, WorkerState],
        interval: float = HEARTBEAT_INTERVAL_S,
    ) -> None:
        self._workers = workers
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        self._task = asyncio.create_task(self._loop())
        logger.info("Heartbeat monitor started (%d workers)", len(self._workers))

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("Heartbeat monitor stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await self._probe_all()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Heartbeat probe error")
            await asyncio.sleep(self._interval)

    async def _probe_all(self) -> None:
        tasks = [self._probe_worker(w) for w in self._workers.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _probe_worker(self, worker: WorkerState) -> None:
        if self._client is None:
            return

        try:
            t0 = time.monotonic()
            resp = await self._client.get(f"{worker.url}/health")
            latency_ms = (time.monotonic() - t0) * 1000

            if resp.status_code != 200:
                self._handle_failure(worker)
                return

            data = resp.json()
            worker.update_from_health(data)

            if latency_ms > SLOW_THRESHOLD_MS:
                worker.status = WorkerStatus.SLOW
                logger.warning("Worker %s is slow (%.0f ms)", worker.node_id, latency_ms)
            else:
                if worker.status == WorkerStatus.DEAD:
                    logger.info("Worker %s came back alive", worker.node_id)
                worker.status = WorkerStatus.ALIVE

        except Exception:
            self._handle_failure(worker)

    def _handle_failure(self, worker: WorkerState) -> None:
        worker.missed_heartbeats += 1
        if worker.missed_heartbeats >= DEAD_THRESHOLD:
            if worker.status != WorkerStatus.DEAD:
                logger.error(
                    "Worker %s is DEAD (%d missed heartbeats)",
                    worker.node_id,
                    worker.missed_heartbeats,
                )
            worker.status = WorkerStatus.DEAD

    def get_alive_workers(self) -> list[WorkerState]:
        return [w for w in self._workers.values() if w.alive]

    def get_dead_workers(self) -> list[WorkerState]:
        return [w for w in self._workers.values() if w.status == WorkerStatus.DEAD]
