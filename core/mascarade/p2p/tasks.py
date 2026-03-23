"""Task distribution — route tasks to capable peers and collect results."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mascarade.p2p.capabilities import P2PCapabilityExchange
from mascarade.p2p.pubsub import P2PPubSub

logger = logging.getLogger("mascarade.p2p.tasks")

_TOPIC_TASK_SUBMIT = "mascarade:task:submit"
_TOPIC_TASK_RESULT = "mascarade:task:result"
_TOPIC_TASK_CLAIM = "mascarade:task:claim"


class TaskStatus(StrEnum):
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
        self._max_task_age = 3600.0  # 1 hour

        pubsub.subscribe(_TOPIC_TASK_SUBMIT, self._handle_task_submit)
        pubsub.subscribe(_TOPIC_TASK_RESULT, self._handle_task_result)
        pubsub.subscribe(_TOPIC_TASK_CLAIM, self._handle_task_claim)

    def set_task_handler(self, handler: Any) -> None:
        self._task_handler = handler

    def prune_old_tasks(self) -> int:
        """Remove completed/failed tasks older than max_task_age. Call from heartbeat."""
        import time as _time
        cutoff = _time.time() - self._max_task_age
        to_remove = [
            tid for tid, t in self._tasks.items()
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT)
            and (t.completed_at or t.submitted_at) < cutoff
        ]
        for tid in to_remove:
            del self._tasks[tid]
            self._result_futures.pop(tid, None)
        if to_remove:
            logger.info("Pruned %d old tasks", len(to_remove))
        return len(to_remove)

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
        except TimeoutError:
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

        # Fix 3: task claim race — record this peer as an interested executor so
        # that concurrent claims from other peers are tracked locally.  We create
        # a lightweight entry if one does not already exist.
        if task_id not in self._tasks:
            self._tasks[task_id] = DistributedTask(
                task_id=task_id,
                capability=capability,
                payload=data.get("payload", {}),
                submitter=submitter,
                timeout_seconds=data.get("timeout", 300.0),
            )

        task = self._tasks[task_id]

        # If another peer already claimed this task, skip it.
        if task.status == TaskStatus.CLAIMED and task.claimed_by != self._local_peer_id:
            logger.debug(
                "Task %s already claimed by %s, skipping", task_id, task.claimed_by
            )
            return

        # Mark ourselves as the tentative claimer before broadcasting so that
        # our own _handle_task_claim callback sees a consistent state.
        task.status = TaskStatus.CLAIMED
        task.claimed_by = self._local_peer_id

        # Broadcast the claim so the submitter (and other workers) know.
        await self._pubsub.publish(_TOPIC_TASK_CLAIM, {
            "task_id": task_id,
            "claimer": self._local_peer_id,
        })

        # Give network a brief moment to deliver competing claims that were sent
        # at nearly the same time.  If a claim from a peer with a lexicographically
        # lower peer_id arrives during this window, defer to them.
        await asyncio.sleep(0.05)

        task = self._tasks.get(task_id)
        if task is None or task.claimed_by != self._local_peer_id:
            logger.debug(
                "Task %s: lost claim race, deferring to %s",
                task_id, task.claimed_by if task else "unknown",
            )
            return

        if not self._task_handler:
            logger.warning("No task handler registered, cannot process task %s", task_id)
            return

        task.status = TaskStatus.RUNNING

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
        claimer = data.get("claimer", "")
        task = self._tasks.get(task_id)
        if task is None:
            return

        if task.status == TaskStatus.PENDING:
            # First claim seen — accept unconditionally.
            task.status = TaskStatus.CLAIMED
            task.claimed_by = claimer
        elif task.status == TaskStatus.CLAIMED and task.claimed_by != claimer:
            # Fix 3: tie-break using lexicographic order of peer_id so every node
            # converges to the same winner deterministically.
            if claimer < task.claimed_by:
                logger.debug(
                    "Task %s: claim superseded by %s (was %s)",
                    task_id, claimer, task.claimed_by,
                )
                task.claimed_by = claimer

    def get_task(self, task_id: str) -> DistributedTask | None:
        return self._tasks.get(task_id)

    def pending_tasks(self) -> list[DistributedTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
