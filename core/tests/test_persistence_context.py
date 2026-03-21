"""Tests for Context Persistence Manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mascarade.persistence.context_manager import (
    ContextPersistenceManager,
    PersistentOrchestrationContext,
    BaseContext
)
from mascarade.orchestrator.context import OrchestrationContext


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
        initial_prompt="initial"
    )
    
    persistent_context = PersistentOrchestrationContext.from_orchestration_context(
        context=orch_context,
        context_id="test_ctx_123",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z"
    )
    
    assert persistent_context.context_id == "test_ctx_123"
    assert persistent_context.prompt == "test prompt"
    assert persistent_context.agent_names == ["agent1", "agent2"]
    assert persistent_context.protocol == "MCP/1.0"


@pytest.mark.asyncio
async def test_context_conversion_roundtrip():
    """Test conversion between OrchestrationContext and PersistentOrchestrationContext."""
    # Create original context
    original = OrchestrationContext(
        prompt="original prompt",
        agent_names=["agent1"],
        mode="original"
    )
    
    # Convert to persistent
    persistent = PersistentOrchestrationContext.from_orchestration_context(
        context=original,
        context_id="test_id",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z"
    )
    
    # Convert back to orchestration
    converted = persistent.to_orchestration_context()
    
    assert converted.prompt == original.prompt
    assert converted.agent_names == original.agent_names
    assert converted.mode == original.mode


@pytest.mark.asyncio
async def test_context_save_and_retrieve():
    """Test saving and retrieving contexts."""
    with patch('mascarade.persistence.context_manager.redis.from_url') as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        manager = ContextPersistenceManager()
        await manager.connect()
        
        # Create test context
        context = PersistentOrchestrationContext(
            context_id="test_ctx",
            protocol="MCP/1.0",
            model_id="test_model",
            session_id="test_session",
            parameters={"temp": 0.7},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z"
        )
        
        # Mock Redis operations
        mock_redis_client.set.return_value = True
        mock_redis_client.sadd.return_value = True
        mock_redis_client.expire.return_value = True
        
        # Save context
        result = await manager.save_context(context)
        assert result == "test_ctx"
        
        # Verify Redis calls
        mock_redis_client.set.assert_called_once()
        mock_redis_client.sadd.assert_called()
        mock_redis_client.expire.assert_called()


@pytest.mark.asyncio
async def test_context_update():
    """Test updating existing context."""
    with patch('mascarade.persistence.context_manager.redis.from_url') as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        manager = ContextPersistenceManager()
        await manager.connect()
        
        # Create and save initial context
        context = PersistentOrchestrationContext(
            context_id="test_ctx",
            protocol="MCP/1.0",
            model_id="test_model",
            session_id="test_session",
            parameters={"temp": 0.7},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z"
        )
        
        # Mock Redis operations
        mock_redis_client.get.return_value = context.json()
        mock_redis_client.set.return_value = True
        
        # Update context
        update_data = {"parameters": {"temp": 0.9}}
        result = await manager.update_context(context, update_data)
        
        assert result == True
        assert context.parameters["temp"] == 0.9


@pytest.mark.asyncio
async def test_context_deletion():
    """Test deleting context."""
    with patch('mascarade.persistence.context_manager.redis.from_url') as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        manager = ContextPersistenceManager()
        await manager.connect()
        
        # Create test context
        context = PersistentOrchestrationContext(
            context_id="test_ctx",
            protocol="MCP/1.0",
            model_id="test_model",
            session_id="test_session",
            parameters={},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z"
        )
        
        # Mock Redis operations
        mock_redis_client.get.return_value = context.json()
        mock_redis_client.delete.return_value = 1
        mock_redis_client.srem.return_value = 1
        
        # Delete context
        result = await manager.delete_context("test_ctx")
        assert result == True


@pytest.mark.asyncio
async def test_list_contexts():
    """Test listing contexts."""
    with patch('mascarade.persistence.context_manager.redis.from_url') as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        manager = ContextPersistenceManager()
        await manager.connect()
        
        # Mock scan results
        mock_redis_client.scan_iter.return_value = [
            b"context:ctx1",
            b"context:ctx2"
        ]
        
        # Mock context retrieval
        context1 = PersistentOrchestrationContext(
            context_id="ctx1",
            protocol="MCP/1.0",
            model_id="model1",
            session_id="session1",
            parameters={},
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z"
        )
        
        mock_redis_client.get.side_effect = [
            context1.json(),
            None  # ctx2 not found
        ]
        
        # List contexts
        contexts = await manager.list_contexts()
        assert len(contexts) == 1
        assert contexts[0] == "ctx1"


@pytest.mark.asyncio
async def test_context_metadata():
    """Test getting context metadata."""
    with patch('mascarade.persistence.context_manager.redis.from_url') as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        manager = ContextPersistenceManager()
        await manager.connect()
        
        # Create test context data
        context_data = {
            "context_id": "test_ctx",
            "context_type": "orchestration",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "metadata": {"test": "value"}
        }
        
        mock_redis_client.get.return_value = json.dumps(context_data)
        
        # Get metadata
        metadata = await manager.get_context_metadata("test_ctx")
        assert metadata["context_id"] == "test_ctx"
        assert metadata["metadata"]["test"] == "value"


@pytest.mark.asyncio
async def test_utility_functions():
    """Test utility functions."""
    from datetime import datetime
    
    with patch('mascarade.persistence.context_manager.redis.from_url') as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        
        manager = ContextPersistenceManager()
        await manager.connect()
        
        # Create orchestration context
        orch_context = OrchestrationContext(
            prompt="test prompt",
            agent_names=["agent1"]
        )
        
        # Save using utility function
        mock_redis_client.set.return_value = True
        mock_redis_client.sadd.return_value = True
        mock_redis_client.expire.return_value = True
        
        context_id = await save_orchestration_context(
            manager=manager,
            context=orch_context,
            context_id="test_id",
            ttl=3600
        )
        
        assert context_id == "test_id"
        
        # Load using utility function
        mock_redis_client.get.return_value = json.dumps({
            "context_id": "test_id",
            "protocol": "MCP/1.0",
            "model_id": "",
            "session_id": "",
            "parameters": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "prompt": "test prompt",
            "agent_names": ["agent1"],
            "mode": None,
            "current_input": None,
            "initial_prompt": None
        })
        
        loaded_context = await load_orchestration_context(manager, "test_id")
        assert loaded_context.prompt == "test prompt"
        assert loaded_context.agent_names == ["agent1"]