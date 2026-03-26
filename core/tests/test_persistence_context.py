import json

"""Tests for Context Persistence Manager."""

from unittest.mock import AsyncMock, patch

import pytest

from mascarade.orchestrator.context import OrchestrationContext
from mascarade.persistence.context_manager import (
    ContextPersistenceManager,
    PersistentOrchestrationContext,
    load_orchestration_context,
    save_orchestration_context,
)


@pytest.mark.asyncio
async def test_context_persistence_manager_initialization():
    """Test ContextPersistenceManager initialization."""
    manager = ContextPersistenceManager(redis_url="redis://test:6379")
    assert manager.redis_url == "redis://test:6379"
    assert manager.default_ttl == 86400
    assert manager._redis is None


@pytest.mark.asyncio
async def test_persistent_orchestration_context_creation():
    """Test PersistentOrchestrationContext creation."""
    orch_context = OrchestrationContext(
        prompt="test prompt",
        agent_names=["agent1", "agent2"],
        mode="test",
        current_input="input",
        initial_prompt="initial",
    )

    persistent_context = PersistentOrchestrationContext.from_orchestration_context(
        context=orch_context,
        context_id="test_ctx_123",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )

    assert persistent_context.context_id == "test_ctx_123"
    assert persistent_context.prompt == "test prompt"
    assert persistent_context.agent_names == ["agent1", "agent2"]
    assert persistent_context.context_type == "orchestration"


@pytest.mark.asyncio
async def test_context_conversion_roundtrip():
    """Test conversion between OrchestrationContext and PersistentOrchestrationContext."""
    # Create original context
    original = OrchestrationContext(
        prompt="original prompt", agent_names=["agent1"], mode="original"
    )

    # Convert to persistent
    persistent = PersistentOrchestrationContext.from_orchestration_context(
        context=original,
        context_id="test_id",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )

    # Convert back to orchestration
    converted = persistent.to_orchestration_context()

    assert converted.prompt == original.prompt
    assert converted.agent_names == original.agent_names
    assert converted.mode == original.mode


def _make_mock_redis():
    """Create a mock Redis client and patch redis.from_url as an async function."""
    mock_redis_client = AsyncMock()
    return mock_redis_client


@pytest.mark.asyncio
async def test_context_save_and_retrieve():
    """Test saving and retrieving contexts."""
    mock_redis_client = _make_mock_redis()

    with patch("mascarade.persistence.context_manager.redis") as mock_redis_module:
        mock_redis_module.from_url = AsyncMock(return_value=mock_redis_client)

        manager = ContextPersistenceManager()
        await manager.connect()

        # Create test context
        context = PersistentOrchestrationContext(
            context_id="test_ctx",
            context_type="orchestration",
            prompt="test prompt",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Mock Redis operations
        mock_redis_client.set.return_value = True

        # Save context
        result = await manager.save_context(context)
        assert result == "test_ctx"

        # Verify Redis set was called
        mock_redis_client.set.assert_called_once()


@pytest.mark.asyncio
async def test_context_update():
    """Test updating existing context."""
    mock_redis_client = _make_mock_redis()

    with patch("mascarade.persistence.context_manager.redis") as mock_redis_module:
        mock_redis_module.from_url = AsyncMock(return_value=mock_redis_client)

        manager = ContextPersistenceManager()
        await manager.connect()

        # Create and save initial context
        context = PersistentOrchestrationContext(
            context_id="test_ctx",
            context_type="orchestration",
            prompt="test prompt",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            execution_history=[],
        )

        # Mock Redis operations
        mock_redis_client.exists.return_value = 1
        mock_redis_client.set.return_value = True

        # Update context
        update_data = {"prompt": "updated prompt"}
        result = await manager.update_context(context, update_data)

        assert result
        assert context.prompt == "updated prompt"


@pytest.mark.asyncio
async def test_context_deletion():
    """Test deleting context."""
    mock_redis_client = _make_mock_redis()

    with patch("mascarade.persistence.context_manager.redis") as mock_redis_module:
        mock_redis_module.from_url = AsyncMock(return_value=mock_redis_client)

        manager = ContextPersistenceManager()
        await manager.connect()

        # Mock Redis operations
        mock_redis_client.delete.return_value = 1

        # Delete context
        result = await manager.delete_context("test_ctx")
        assert result


@pytest.mark.asyncio
async def test_list_contexts():
    """Test listing contexts."""
    mock_redis_client = _make_mock_redis()

    with patch("mascarade.persistence.context_manager.redis") as mock_redis_module:
        mock_redis_module.from_url = AsyncMock(return_value=mock_redis_client)

        manager = ContextPersistenceManager()
        await manager.connect()

        # Mock scan_iter as an async generator
        async def mock_scan_iter(match=None):
            for key in ["context:ctx1", "context:ctx2"]:
                yield key

        mock_redis_client.scan_iter = mock_scan_iter

        # List contexts (no type filter -> all returned)
        contexts = await manager.list_contexts()
        assert len(contexts) == 2
        assert "ctx1" in contexts
        assert "ctx2" in contexts


@pytest.mark.asyncio
async def test_context_metadata():
    """Test getting context metadata."""
    mock_redis_client = _make_mock_redis()

    with patch("mascarade.persistence.context_manager.redis") as mock_redis_module:
        mock_redis_module.from_url = AsyncMock(return_value=mock_redis_client)

        manager = ContextPersistenceManager()
        await manager.connect()

        # Create test context data
        context_data = {
            "context_id": "test_ctx",
            "context_type": "orchestration",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "metadata": {"test": "value"},
        }

        mock_redis_client.get.return_value = json.dumps(context_data)

        # Get metadata
        metadata = await manager.get_context_metadata("test_ctx")
        assert metadata["context_id"] == "test_ctx"
        assert metadata["metadata"]["test"] == "value"


@pytest.mark.asyncio
async def test_utility_functions():
    """Test utility functions."""
    mock_redis_client = _make_mock_redis()

    with patch("mascarade.persistence.context_manager.redis") as mock_redis_module:
        mock_redis_module.from_url = AsyncMock(return_value=mock_redis_client)

        manager = ContextPersistenceManager()
        await manager.connect()

        # Create orchestration context
        orch_context = OrchestrationContext(prompt="test prompt", agent_names=["agent1"])

        # Save using utility function
        mock_redis_client.set.return_value = True

        context_id = await save_orchestration_context(
            manager=manager, context=orch_context, context_id="test_id", ttl=3600
        )

        assert context_id == "test_id"

        # Load using utility function
        mock_redis_client.get.return_value = json.dumps(
            {
                "context_id": "test_id",
                "context_type": "orchestration",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "prompt": "test prompt",
                "agent_names": ["agent1"],
                "mode": None,
                "current_input": None,
                "initial_prompt": None,
                "execution_history": [],
            }
        )

        loaded_context = await load_orchestration_context(manager, "test_id")
        assert loaded_context.prompt == "test prompt"
        assert loaded_context.agent_names == ["agent1"]
