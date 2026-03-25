"""Tests for Multi-Backend Memory Manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mascarade.persistence.memory_manager import (
    MemoryEntry,
    MultiBackendMemoryManager,
    create_conversation_memory,
    create_memory_entry,
)


async def _async_iter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_memory_manager_initialization():
    """Test MultiBackendMemoryManager initialization."""
    manager = MultiBackendMemoryManager(redis_url="redis://test:6379")
    assert manager.redis_url == "redis://test:6379"
    assert manager.default_ttl == 86400
    assert manager._redis is None
    assert manager._conversation_memory is None


@pytest.mark.asyncio
async def test_memory_keys_are_scoped_by_project():
    manager = MultiBackendMemoryManager(redis_url="redis://test:6379")
    assert (
        manager._get_memory_key("mem-1", project_id="project-a")
        == "memory:project-a:mem-1"
    )
    assert (
        manager._get_memory_key("mem-1", project_id="project-b")
        == "memory:project-b:mem-1"
    )


@pytest.mark.asyncio
async def test_memory_entry_creation():
    """Test MemoryEntry creation."""
    memory = MemoryEntry(
        memory_id="test_mem",
        content="test content",
        memory_type="generic",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        metadata={"test": "value"},
        tags=["test", "example"],
    )

    assert memory.memory_id == "test_mem"
    assert memory.content == "test content"
    assert memory.memory_type == "generic"
    assert memory.tags == ["test", "example"]


@pytest.mark.asyncio
async def test_memory_save_and_retrieve():
    """Test saving and retrieving memories."""
    with patch("mascarade.persistence.memory_manager.redis.from_url") as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        manager = MultiBackendMemoryManager()
        await manager.connect()

        # Create test memory
        memory = MemoryEntry(
            memory_id="test_mem",
            content="test content",
            memory_type="generic",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Mock Redis operations
        mock_redis_client.set.return_value = True
        mock_redis_client.get.return_value = memory.json()

        # Save memory
        result = await manager.store_memory(memory)
        assert result == "test_mem"

        # Retrieve memory
        retrieved = await manager.retrieve_memory("test_mem")
        assert retrieved.memory_id == "test_mem"
        assert retrieved.content == "test content"


@pytest.mark.asyncio
async def test_memory_update():
    """Test updating existing memory."""
    with patch("mascarade.persistence.memory_manager.redis.from_url") as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        manager = MultiBackendMemoryManager()
        await manager.connect()

        # Create and save initial memory
        memory = MemoryEntry(
            memory_id="test_mem",
            content="original content",
            memory_type="generic",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        # Mock Redis operations
        mock_redis_client.get.return_value = memory.json()
        mock_redis_client.set.return_value = True

        # Update memory
        update_data = {"content": "updated content"}
        result = await manager.update_memory("test_mem", update_data)

        assert result
        stored_payload = mock_redis_client.set.await_args.args[1]
        assert "updated content" in stored_payload


@pytest.mark.asyncio
async def test_memory_deletion():
    """Test deleting memory."""
    with patch("mascarade.persistence.memory_manager.redis.from_url") as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        manager = MultiBackendMemoryManager()
        await manager.connect()

        # Mock Redis operations
        mock_redis_client.delete.return_value = 1

        # Delete memory
        result = await manager.delete_memory("test_mem")
        assert result


@pytest.mark.asyncio
async def test_memory_search():
    """Test searching memories."""
    with patch("mascarade.persistence.memory_manager.redis.from_url") as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        manager = MultiBackendMemoryManager()
        await manager.connect()

        # Mock scan results
        mock_redis_client.scan_iter = MagicMock(
            return_value=_async_iter(
                [
                    b"memory:default:mem1",
                    b"memory:default:mem2",
                ]
            )
        )

        # Mock memory retrieval
        memory1 = MemoryEntry(
            memory_id="mem1",
            content="test content",
            memory_type="generic",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            tags=["test"],
        )

        memory2 = MemoryEntry(
            memory_id="mem2",
            content="other content",
            memory_type="conversation",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            tags=["example"],
        )

        mock_redis_client.get.side_effect = [memory1.json(), memory2.json()]

        # Search memories
        results = await manager.search_memories("test", memory_type="generic")
        assert len(results) == 1
        assert results[0].memory_id == "mem1"


@pytest.mark.asyncio
async def test_batch_operations():
    """Test batch memory operations."""
    with patch("mascarade.persistence.memory_manager.redis.from_url") as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        manager = MultiBackendMemoryManager()
        await manager.connect()

        # Create test memories
        memories = [
            MemoryEntry(
                memory_id="mem1",
                content="content1",
                memory_type="generic",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            ),
            MemoryEntry(
                memory_id="mem2",
                content="content2",
                memory_type="generic",
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            ),
        ]

        # Mock Redis operations
        pipeline = MagicMock()
        pipeline.execute = AsyncMock(return_value=None)
        mock_redis_client.pipeline = MagicMock(return_value=pipeline)

        # Batch store
        stored_ids = await manager.batch_store_memories(memories)
        assert len(stored_ids) == 2
        assert "mem1" in stored_ids
        assert "mem2" in stored_ids

        # Batch delete
        mock_redis_client.delete.return_value = 2
        deleted_count = await manager.batch_delete_memories(["mem1", "mem2"])
        assert deleted_count == 2


@pytest.mark.asyncio
async def test_utility_functions():
    """Test utility functions."""
    with patch("mascarade.persistence.memory_manager.redis.from_url") as mock_redis:
        # Setup mock Redis
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        manager = MultiBackendMemoryManager()
        await manager.connect()

        # Test create_memory_entry
        memory = await create_memory_entry(
            content="test content",
            memory_type="test",
            metadata={"test": "value"},
            tags=["test"],
        )

        assert memory.memory_id.startswith("mem_")
        assert memory.content == "test content"
        assert memory.memory_type == "test"
        assert memory.metadata["test"] == "value"
        assert "test" in memory.tags

        # Test create_conversation_memory
        mock_redis_client.set.return_value = True
        mock_redis_client.lpush.return_value = True
        mock_redis_client.expire.return_value = True
        manager.store_memory = AsyncMock(return_value=memory.memory_id)
        manager.store_conversation_message = AsyncMock()

        with patch("mascarade.conversation.models.ConversationMessage") as mock_message:
            mock_message_instance = MagicMock()
            mock_message.return_value = mock_message_instance

            with patch(
                "mascarade.persistence.memory_manager.create_memory_entry"
            ) as mock_create:
                mock_create.return_value = memory

                result = await create_conversation_memory(
                    manager=manager,
                    conversation_id="conv1",
                    user_id="user1",
                    initial_message="hello",
                )

                assert result == memory.memory_id
                manager.store_memory.assert_awaited_once()
                manager.store_conversation_message.assert_awaited_once()
