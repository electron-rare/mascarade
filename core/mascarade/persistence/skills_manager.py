"""Persistent Skills Management System for Mascarade Agents."""

from __future__ import annotations

import logging
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel

logger = logging.getLogger("mascarade.persistence.skills")


class SkillDefinition(BaseModel):
    """Definition of an agent skill with execution parameters."""

    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    parameters: dict[str, Any] = {}
    enabled: bool = True
    metadata: dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "skill_id": "skill_analysis",
                    "name": "Data Analysis",
                    "description": "Perform advanced data analysis",
                    "version": "1.0.0",
                    "parameters": {"max_iterations": 100},
                    "enabled": True,
                    "metadata": {"category": "analysis"}
                }
            ]
        }


class SkillExecutionRecord(BaseModel):
    """Record of skill execution with results and metrics."""

    execution_id: str
    skill_id: str
    agent_id: str
    timestamp: str
    parameters: dict[str, Any]
    status: str = "completed"
    result: dict[str, Any] | None = None
    metrics: dict[str, Any] = {}
    error: str | None = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "execution_id": "exec_12345",
                    "skill_id": "skill_analysis",
                    "agent_id": "agent_789",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "parameters": {"max_iterations": 100},
                    "status": "completed",
                    "result": {"analysis": "successful"},
                    "metrics": {"duration_ms": 450},
                    "error": None
                }
            ]
        }


class SkillsPersistenceManager:
    """Persistent skills management with Redis backend."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 86400
    ) -> None:
        """Initialize skills persistence manager.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds (24h)
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Connected to Redis for skills persistence")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Disconnected from Redis")

    # --- Skill Definition Management ---

    def _get_skill_key(self, skill_id: str) -> str:
        """Generate Redis key for skill storage."""
        return f"skill:def:{skill_id}"

    async def register_skill(
        self,
        skill_definition: SkillDefinition,
        ttl: int | None = None
    ) -> str:
        """Register a new skill or update existing one.

        Args:
            skill_definition: Skill definition to register
            ttl: Optional TTL override in seconds

        Returns:
            skill_id of the registered skill
        """
        if self._redis is None:
            await self.connect()

        key = self._get_skill_key(skill_definition.skill_id)
        value = skill_definition.json()
        ttl_seconds = ttl or self.default_ttl

        await self._redis.set(key, value, ex=ttl_seconds)
        logger.info(f"Registered skill {skill_definition.skill_id} (v{skill_definition.version})")

        return skill_definition.skill_id

    async def get_skill(self, skill_id: str) -> SkillDefinition | None:
        """Retrieve skill definition.

        Args:
            skill_id: ID of skill to retrieve

        Returns:
            SkillDefinition object or None if not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_skill_key(skill_id)
        value = await self._redis.get(key)

        if value is None:
            logger.warning(f"Skill {skill_id} not found")
            return None

        try:
            skill = SkillDefinition.parse_raw(value)
            logger.info(f"Retrieved skill {skill_id}")
            return skill
        except Exception as e:
            logger.error(f"Failed to deserialize skill {skill_id}: {e}")
            return None

    async def update_skill(
        self,
        skill_id: str,
        update_data: dict[str, Any]
    ) -> bool:
        """Update existing skill definition.

        Args:
            skill_id: ID of skill to update
            update_data: Dictionary of fields to update

        Returns:
            True if update succeeded, False if skill not found
        """
        if self._redis is None:
            await self.connect()

        # Retrieve existing skill
        existing_skill = await self.get_skill(skill_id)
        if existing_skill is None:
            return False

        # Update fields
        for field, value in update_data.items():
            if hasattr(existing_skill, field):
                setattr(existing_skill, field, value)

        # Save updated skill
        await self.register_skill(existing_skill)
        logger.info(f"Updated skill {skill_id}")

        return True

    async def delete_skill(self, skill_id: str) -> bool:
        """Delete skill definition.

        Args:
            skill_id: ID of skill to delete

        Returns:
            True if deletion succeeded, False if skill not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_skill_key(skill_id)
        result = await self._redis.delete(key)

        if result > 0:
            logger.info(f"Deleted skill {skill_id}")
            return True

        logger.warning(f"Skill {skill_id} not found for deletion")
        return False

    # --- Skill Execution Management ---

    def _get_execution_key(self, execution_id: str) -> str:
        """Generate Redis key for execution record."""
        return f"skill:exec:{execution_id}"

    def _get_agent_executions_key(self, agent_id: str) -> str:
        """Generate Redis key for agent's execution history."""
        return f"skill:agent:{agent_id}:executions"

    async def record_execution(
        self,
        execution_record: SkillExecutionRecord,
        ttl: int | None = None
    ) -> str:
        """Record skill execution with results.

        Args:
            execution_record: Execution record to store
            ttl: Optional TTL override in seconds

        Returns:
            execution_id of the recorded execution
        """
        if self._redis is None:
            await self.connect()

        # Store execution record
        exec_key = self._get_execution_key(execution_record.execution_id)
        exec_value = execution_record.json()
        ttl_seconds = ttl or self.default_ttl

        # Store agent execution history
        agent_exec_key = self._get_agent_executions_key(execution_record.agent_id)

        pipeline = self._redis.pipeline()
        pipeline.set(exec_key, exec_value, ex=ttl_seconds)
        pipeline.lpush(agent_exec_key, execution_record.execution_id)
        pipeline.expire(agent_exec_key, ttl_seconds)

        await pipeline.execute()

        logger.info(f"Recorded execution {execution_record.execution_id} "
                   f"for skill {execution_record.skill_id}")

        return execution_record.execution_id

    async def get_execution(self, execution_id: str) -> SkillExecutionRecord | None:
        """Retrieve skill execution record.

        Args:
            execution_id: ID of execution to retrieve

        Returns:
            SkillExecutionRecord object or None if not found
        """
        if self._redis is None:
            await self.connect()

        key = self._get_execution_key(execution_id)
        value = await self._redis.get(key)

        if value is None:
            logger.warning(f"Execution {execution_id} not found")
            return None

        try:
            execution = SkillExecutionRecord.parse_raw(value)
            logger.info(f"Retrieved execution {execution_id}")
            return execution
        except Exception as e:
            logger.error(f"Failed to deserialize execution {execution_id}: {e}")
            return None

    async def get_agent_executions(
        self,
        agent_id: str,
        limit: int = 10
    ) -> list[SkillExecutionRecord]:
        """Get execution history for an agent.

        Args:
            agent_id: ID of agent
            limit: Maximum number of executions to return

        Returns:
            List of SkillExecutionRecord objects
        """
        if self._redis is None:
            await self.connect()

        agent_exec_key = self._get_agent_executions_key(agent_id)
        execution_ids = await self._redis.lrange(agent_exec_key, 0, limit - 1)

        executions = []
        for exec_id in execution_ids:
            execution = await self.get_execution(exec_id)
            if execution:
                executions.append(execution)

        logger.info(f"Retrieved {len(executions)} executions for agent {agent_id}")
        return executions

    # --- Agent Skill Management ---

    def _get_agent_skills_key(self, agent_id: str) -> str:
        """Generate Redis key for agent's skills."""
        return f"agent:{agent_id}:skills"

    async def assign_skill_to_agent(
        self,
        agent_id: str,
        skill_id: str
    ) -> bool:
        """Assign skill to an agent.

        Args:
            agent_id: ID of agent
            skill_id: ID of skill to assign

        Returns:
            True if assignment succeeded, False if skill not found
        """
        if self._redis is None:
            await self.connect()

        # Verify skill exists
        skill = await self.get_skill(skill_id)
        if skill is None:
            return False

        agent_skills_key = self._get_agent_skills_key(agent_id)
        await self._redis.sadd(agent_skills_key, skill_id)
        await self._redis.expire(agent_skills_key, self.default_ttl)

        logger.info(f"Assigned skill {skill_id} to agent {agent_id}")
        return True

    async def remove_skill_from_agent(
        self,
        agent_id: str,
        skill_id: str
    ) -> bool:
        """Remove skill from an agent.

        Args:
            agent_id: ID of agent
            skill_id: ID of skill to remove

        Returns:
            True if removal succeeded, False if skill not assigned
        """
        if self._redis is None:
            await self.connect()

        agent_skills_key = self._get_agent_skills_key(agent_id)
        result = await self._redis.srem(agent_skills_key, skill_id)

        if result > 0:
            logger.info(f"Removed skill {skill_id} from agent {agent_id}")
            return True

        logger.warning(f"Skill {skill_id} not found for agent {agent_id}")
        return False

    async def get_agent_skills(self, agent_id: str) -> list[SkillDefinition]:
        """Get all skills assigned to an agent.

        Args:
            agent_id: ID of agent

        Returns:
            List of SkillDefinition objects
        """
        if self._redis is None:
            await self.connect()

        agent_skills_key = self._get_agent_skills_key(agent_id)
        skill_ids = await self._redis.smembers(agent_skills_key)

        skills = []
        for skill_id in skill_ids:
            skill = await self.get_skill(skill_id)
            if skill:
                skills.append(skill)

        logger.info(f"Retrieved {len(skills)} skills for agent {agent_id}")
        return skills

    # --- Advanced Operations ---

    async def list_all_skills(self) -> list[str]:
        """List all registered skill IDs.

        Returns:
            List of skill IDs
        """
        if self._redis is None:
            await self.connect()

        pattern = "skill:def:*"
        skill_ids = []

        async for key in self._redis.scan_iter(match=pattern):
            skill_id = key.replace("skill:def:", "")
            skill_ids.append(skill_id)

        return sorted(skill_ids)

    async def search_skills(
        self,
        query: str,
        category: str | None = None
    ) -> list[SkillDefinition]:
        """Search skills by name, description, or category.

        Args:
            query: Search query
            category: Optional category filter

        Returns:
            List of matching SkillDefinition objects
        """
        if self._redis is None:
            await self.connect()

        pattern = "skill:def:*"
        results = []

        async for key in self._redis.scan_iter(match=pattern):
            skill_id = key.replace("skill:def:", "")
            skill = await self.get_skill(skill_id)

            if skill is None:
                continue

            # Apply category filter
            if category and skill.metadata.get("category") != category:
                continue

            # Search in name and description
            if (query.lower() in skill.name.lower() or
                query.lower() in skill.description.lower()):
                results.append(skill)

        return results

    async def get_skill_stats(self, skill_id: str) -> dict[str, Any]:
        """Get usage statistics for a skill.

        Args:
            skill_id: ID of skill

        Returns:
            Dictionary with usage statistics
        """
        if self._redis is None:
            await self.connect()

        # Count executions (would need to scan all execution records in production)
        # This is a simplified version - real implementation would use indexes
        pattern = "skill:exec:*"
        execution_count = 0

        async for key in self._redis.scan_iter(match=pattern):
            exec_data = await self._redis.get(key)
            if exec_data:
                try:
                    execution = SkillExecutionRecord.parse_raw(exec_data)
                    if execution.skill_id == skill_id:
                        execution_count += 1
                except:
                    continue

        # Get agents using this skill
        agents_using = []
        agent_pattern = "agent:*:skills"

        async for key in self._redis.scan_iter(match=agent_pattern):
            if await self._redis.sismember(key, skill_id):
                agent_id = key.replace("agent:", "").replace(":skills", "")
                agents_using.append(agent_id)

        return {
            "skill_id": skill_id,
            "execution_count": execution_count,
            "agents_using": len(agents_using),
            "agent_ids": agents_using
        }

    async def clear_all_skills(self) -> int:
        """Clear all skills (for testing/debugging).

        Returns:
            Number of skills deleted
        """
        if self._redis is None:
            await self.connect()

        # Delete skill definitions
        skill_keys = []
        async for key in self._redis.scan_iter(match="skill:def:*"):
            skill_keys.append(key)

        # Delete execution records
        exec_keys = []
        async for key in self._redis.scan_iter(match="skill:exec:*"):
            exec_keys.append(key)

        # Delete agent skill assignments
        agent_skill_keys = []
        async for key in self._redis.scan_iter(match="agent:*:skills"):
            agent_skill_keys.append(key)

        # Delete agent execution histories
        agent_exec_keys = []
        async for key in self._redis.scan_iter(match="skill:agent:*:executions"):
            agent_exec_keys.append(key)

        all_keys = skill_keys + exec_keys + agent_skill_keys + agent_exec_keys

        if all_keys:
            result = await self._redis.delete(*all_keys)
            logger.info(f"Cleared {result} skill-related records")
            return result

        return 0


# Utility functions for common skill operations

async def create_skill_definition(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    skill_id: str | None = None,
    version: str = "1.0.0",
    metadata: dict[str, Any] | None = None
) -> SkillDefinition:
    """Create a new SkillDefinition with automatic IDs."""
    import uuid

    return SkillDefinition(
        skill_id=skill_id or f"skill_{uuid.uuid4().hex[:8]}",
        name=name,
        description=description,
        version=version,
        parameters=parameters or {},
        enabled=True,
        metadata=metadata or {}
    )


async def create_execution_record(
    skill_id: str,
    agent_id: str,
    parameters: dict[str, Any],
    result: dict[str, Any] | None = None,
    error: str | None = None,
    execution_id: str | None = None
) -> SkillExecutionRecord:
    """Create a new SkillExecutionRecord with automatic IDs and timestamps."""
    import uuid
    from datetime import datetime

    now = datetime.utcnow().isoformat() + "Z"
    status = "error" if error else "completed"

    return SkillExecutionRecord(
        execution_id=execution_id or f"exec_{uuid.uuid4().hex[:8]}",
        skill_id=skill_id,
        agent_id=agent_id,
        timestamp=now,
        parameters=parameters,
        status=status,
        result=result,
        metrics={},
        error=error
    )


async def execute_skill_with_recording(
    manager: SkillsPersistenceManager,
    skill_id: str,
    agent_id: str,
    parameters: dict[str, Any],
    execution_func: callable
) -> SkillExecutionRecord:
    """Execute a skill and automatically record the execution.

    Args:
        manager: SkillsPersistenceManager instance
        skill_id: ID of skill being executed
        agent_id: ID of executing agent
        parameters: Execution parameters
        execution_func: Function to execute (should return result dict)

    Returns:
        SkillExecutionRecord with execution details
    """
    try:
        # Execute the skill
        result = execution_func()

        # Create execution record
        execution_record = await create_execution_record(
            skill_id=skill_id,
            agent_id=agent_id,
            parameters=parameters,
            result=result
        )

        # Record execution
        await manager.record_execution(execution_record)

        return execution_record

    except Exception as e:
        # Record failed execution
        execution_record = await create_execution_record(
            skill_id=skill_id,
            agent_id=agent_id,
            parameters=parameters,
            error=str(e)
        )

        await manager.record_execution(execution_record)
        raise
