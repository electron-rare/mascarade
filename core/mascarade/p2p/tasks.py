"""Task distribution — route tasks to capable peers and collect results."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mascarade.p2p.capabilities import P2PCapabilityExchange, PeerCapabilities
from mascarade.p2p.pubsub import P2PPubSub

logger = logging.getLogger("mascarade.p2p.tasks")

_TOPIC_TASK_SUBMIT = "mascarade:task:submit"
_TOPIC_TASK_RESULT = "mascarade:task:result"
_TOPIC_TASK_CLAIM = "mascarade:task:claim"


class TaskStatus(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class DistributedTask:
    task_id: str
    capability: str
    payload: dict[str, Any]
    submitter: str
    status: TaskStatus = TaskStatus.PENDING
    claimed_by: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    submitted_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    timeout_seconds: float = 300.0


class P2PTaskDistribution:
    """Distribute tasks to capable peers via PubSub and collect results."""

    def __init__(
        self,
        *,
        local_peer_id: str,
        pubsub: P2PPubSub,
        capability_exchange: P2PCapabilityExchange,
        task_handler: Any | None = None,
    ) -> None:
        self._local_peer_id = local_peer_id
        self._pubsub = pubsub
        self._caps = capability_exchange
        self._tasks: dict[str, DistributedTask] = {}
        self._result_futures: dict[str, asyncio.Future] = {}
        self._task_handler = task_handler

        pubsub.subscribe(_TOPIC_TASK_SUBMIT, self._handle_task_submit)
        pubsub.subscribe(_TOPIC_TASK_RESULT, self._handle_task_result)
        pubsub.subscribe(_TOPIC_TASK_CLAIM, self._handle_task_claim)

    def set_task_handler(self, handler: Any) -> None:
        self._task_handler = handler

    async def distribute_task(
        self,
        task_id: str | None,
        payload: dict[str, Any],
        capability: str,
        *,
        timeout: float = 300.0,
        target_peer: str | None = None,
    ) -> DistributedTask:
        task_id = task_id or str(uuid.uuid4())

        task = DistributedTask(
            task_id=task_id,
            capability=capability,
            payload=payload,
            submitter=self._local_peer_id,
            timeout_seconds=timeout,
        )
        self._tasks[task_id] = task

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._result_futures[task_id] = future

        # If targeting a specific peer, check capabilities
        if target_peer:
            caps = self._caps.get_peer_capabilities(target_peer)
            if not caps or capability not in caps.capabilities:
                logger.warning(
                    "Target peer %s doesn't have capability %s",
                    target_peer, capability,
                )

        await self._pubsub.publish(_TOPIC_TASK_SUBMIT, {
            "task_id": task_id,
            "capability": capability,
            "payload": payload,
            "submitter": self._local_peer_id,
            "timeout": timeout,
            "target_peer": target_peer,
        })

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.error = f"Task timed out after {timeout}s"
            logger.warning("Task %s timed out", task_id)
        except RuntimeError as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()
        finally:
            self._result_futures.pop(task_id, None)

        return task

    async def _handle_task_submit(
        self, topic: str, data: dict[str, Any], origin: str,
    ) -> None:
        task_id = data.get("task_id", "")
        capability = data.get("capability", "")
        target_peer = data.get("target_peer")
        submitter = data.get("submitter", origin)

        if submitter == self._local_peer_id:
            return

        if target_peer and target_peer != self._local_peer_id:
            return

        # Check if we can handle this
        local_caps = self._caps._local_caps
        if not local_caps or capability not in local_caps.capabilities:
            return

        # Claim the task
        await self._pubsub.publish(_TOPIC_TASK_CLAIM, {
            "task_id": task_id,
            "claimer": self._local_peer_id,
        })

        if not self._task_handler:
            logger.warning("No task handler registered, cannot process task %s", task_id)
            return

        # Execute
        try:
            result = await self._task_handler(data.get("payload", {}), capability)
            await self._pubsub.publish(_TOPIC_TASK_RESULT, {
                "task_id": task_id,
                "executor": self._local_peer_id,
                "status": "completed",
                "result": result,
            })
        except Exception as exc:
            logger.exception("Task %s failed", task_id)
            await self._pubsub.publish(_TOPIC_TASK_RESULT, {
                "task_id": task_id,
                "executor": self._local_peer_id,
                "status": "failed",
                "error": str(exc),
            })

    async def _handle_task_result(
        self, topic: str, data: dict[str, Any], origin: str,
    ) -> None:
        task_id = data.get("task_id", "")
        future = self._result_futures.get(task_id)
        if not future or future.done():
            return

        status = data.get("status", "")
        if status == "completed":
            future.set_result(data.get("result", {}))
        elif status == "failed":
            future.set_exception(RuntimeError(data.get("error", "Remote task failed")))

        task = self._tasks.get(task_id)
        if task:
            task.claimed_by = data.get("executor")
            task.status = TaskStatus.COMPLETED if status == "completed" else TaskStatus.FAILED

    async def _handle_task_claim(
        self, topic: str, data: dict[str, Any], origin: str,
    ) -> None:
        task_id = data.get("task_id", "")
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CLAIMED
            task.claimed_by = data.get("claimer")

    def get_task(self, task_id: str) -> DistributedTask | None:
        return self._tasks.get(task_id)

    def pending_tasks(self) -> list[DistributedTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
