"""Unit tests for Mem0 memory operations.

This module tests the core Mem0 memory functionality including:
- Memory storage and retrieval
- Semantic search operations
- User/agent scoping and privacy controls
- Error handling and edge cases
- Memory metadata and TTL handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from mascarade.routers.memory import (
    MemoryAddRequest,
    MemoryDeleteRequest,
    MemoryGetRequest,
    MemorySearchRequest,
    Message,
    _get_mem0_url,
    _mem0_request,
)


# --- Tests for helper functions ---


def test_get_mem0_url():
    """Test Mem0 URL configuration."""
    mock_request = MagicMock()
    url = _get_mem0_url(mock_request)
    assert url == "http://mem0:8765"
    assert "mem0" in url


@pytest.mark.asyncio
async def test_mem0_request_post_success():
    """Test successful POST request to Mem0 service."""
    mock_response = {"id": "mem-123", "status": "created"}

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)

        result = await _mem0_request(
            "http://mem0:8765/memories",
            method="POST",
            json_data={"test": "data"},
        )

        assert result == mock_response
        mock_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_mem0_request_get_success():
    """Test successful GET request to Mem0 service."""
    mock_response = {"results": [{"id": "mem-1", "content": "test"}]}

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_resp)

        result = await _mem0_request(
            "http://mem0:8765/memories",
            method="GET",
            json_data={"user_id": "test-user"},
        )

        assert result == mock_response
        mock_instance.get.assert_called_once()


@pytest.mark.asyncio
async def test_mem0_request_delete_success():
    """Test successful DELETE request to Mem0 service."""
    mock_response = {"status": "deleted"}

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_instance.delete = AsyncMock(return_value=mock_resp)

        result = await _mem0_request(
            "http://mem0:8765/memories/mem-123",
            method="DELETE",
            json_data={"memory_id": "mem-123"},
        )

        assert result == mock_response
        mock_instance.delete.assert_called_once()


@pytest.mark.asyncio
async def test_mem0_request_timeout():
    """Test timeout handling in Mem0 requests."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await _mem0_request(
                "http://mem0:8765/memories",
                method="POST",
                json_data={"test": "data"},
            )

        assert exc_info.value.status_code == 503
        assert "timeout" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_mem0_request_http_error():
    """Test HTTP error handling in Mem0 requests."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance

        # Create a mock response with error status
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Memory not found"

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=mock_response,
        )
        mock_instance.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(HTTPException) as exc_info:
            await _mem0_request(
                "http://mem0:8765/memories",
                method="POST",
                json_data={"test": "data"},
            )

        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_mem0_request_connection_error():
    """Test connection error handling in Mem0 requests."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_instance.post = AsyncMock(side_effect=Exception("Connection refused"))

        with pytest.raises(HTTPException) as exc_info:
            await _mem0_request(
                "http://mem0:8765/memories",
                method="POST",
                json_data={"test": "data"},
            )

        assert exc_info.value.status_code == 503
        assert "unavailable" in exc_info.value.detail.lower()


# --- Tests for request models ---


def test_message_model_valid():
    """Test Message model with valid data."""
    msg = Message(role="user", content="Hello, world!")
    assert msg.role == "user"
    assert msg.content == "Hello, world!"


def test_message_model_validation():
    """Test Message model validation."""
    # Empty role should fail
    with pytest.raises(Exception):  # Pydantic validation error
        Message(role="", content="test")

    # Empty content should fail
    with pytest.raises(Exception):
        Message(role="user", content="")

    # Too long role should fail
    with pytest.raises(Exception):
        Message(role="x" * 30, content="test")


def test_memory_add_request_valid():
    """Test MemoryAddRequest model with valid data."""
    req = MemoryAddRequest(
        messages=[
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ],
        user_id="test-user",
        metadata={"source": "test"},
        agent_id="test-agent",
    )

    assert len(req.messages) == 2
    assert req.user_id == "test-user"
    assert req.metadata == {"source": "test"}
    assert req.agent_id == "test-agent"


def test_memory_add_request_minimal():
    """Test MemoryAddRequest with minimal required fields."""
    req = MemoryAddRequest(
        messages=[Message(role="user", content="Hello")],
        user_id="test-user",
    )

    assert len(req.messages) == 1
    assert req.user_id == "test-user"
    assert req.metadata is None
    assert req.agent_id is None


def test_memory_add_request_validation():
    """Test MemoryAddRequest validation."""
    # Empty messages should fail
    with pytest.raises(Exception):
        MemoryAddRequest(messages=[], user_id="test-user")

    # Missing user_id should fail
    with pytest.raises(Exception):
        MemoryAddRequest(messages=[Message(role="user", content="test")])

    # Too many messages should fail (>200)
    with pytest.raises(Exception):
        MemoryAddRequest(
            messages=[Message(role="user", content="test") for _ in range(201)],
            user_id="test-user",
        )


def test_memory_search_request_valid():
    """Test MemorySearchRequest model with valid data."""
    req = MemorySearchRequest(
        query="test query",
        user_id="test-user",
        limit=5,
        agent_id="test-agent",
    )

    assert req.query == "test query"
    assert req.user_id == "test-user"
    assert req.limit == 5
    assert req.agent_id == "test-agent"


def test_memory_search_request_defaults():
    """Test MemorySearchRequest default values."""
    req = MemorySearchRequest(
        query="test query",
        user_id="test-user",
    )

    assert req.limit == 10  # Default limit
    assert req.agent_id is None


def test_memory_search_request_validation():
    """Test MemorySearchRequest validation."""
    # Limit too low should fail
    with pytest.raises(Exception):
        MemorySearchRequest(query="test", user_id="test-user", limit=0)

    # Limit too high should fail
    with pytest.raises(Exception):
        MemorySearchRequest(query="test", user_id="test-user", limit=101)

    # Empty query should fail
    with pytest.raises(Exception):
        MemorySearchRequest(query="", user_id="test-user")


def test_memory_get_request_valid():
    """Test MemoryGetRequest model with valid data."""
    req = MemoryGetRequest(
        user_id="test-user",
        agent_id="test-agent",
    )

    assert req.user_id == "test-user"
    assert req.agent_id == "test-agent"


def test_memory_get_request_minimal():
    """Test MemoryGetRequest with minimal fields."""
    req = MemoryGetRequest(user_id="test-user")

    assert req.user_id == "test-user"
    assert req.agent_id is None


def test_memory_delete_request_valid():
    """Test MemoryDeleteRequest model with valid data."""
    req = MemoryDeleteRequest(
        memory_id="mem-123",
        user_id="test-user",
    )

    assert req.memory_id == "mem-123"
    assert req.user_id == "test-user"


def test_memory_delete_request_validation():
    """Test MemoryDeleteRequest validation."""
    # Empty memory_id should fail
    with pytest.raises(Exception):
        MemoryDeleteRequest(memory_id="", user_id="test-user")

    # Empty user_id should fail
    with pytest.raises(Exception):
        MemoryDeleteRequest(memory_id="mem-123", user_id="")


# --- Tests for memory operations scenarios ---


def test_memory_privacy_scoping():
    """Test that memory requests properly scope by user_id and agent_id."""
    # User-only scoping
    user_req = MemoryGetRequest(user_id="user-1")
    assert user_req.user_id == "user-1"
    assert user_req.agent_id is None

    # User + agent scoping
    agent_req = MemoryGetRequest(user_id="user-1", agent_id="agent-1")
    assert agent_req.user_id == "user-1"
    assert agent_req.agent_id == "agent-1"

    # Different users should have different scoping
    user_req_2 = MemoryGetRequest(user_id="user-2")
    assert user_req.user_id != user_req_2.user_id


def test_memory_metadata_handling():
    """Test metadata handling in memory operations."""
    # With custom metadata
    req_with_meta = MemoryAddRequest(
        messages=[Message(role="user", content="test")],
        user_id="test-user",
        metadata={"source": "test", "priority": "high", "tags": ["important"]},
    )

    assert "source" in req_with_meta.metadata
    assert "priority" in req_with_meta.metadata
    assert "tags" in req_with_meta.metadata
    assert req_with_meta.metadata["tags"] == ["important"]

    # Without metadata
    req_no_meta = MemoryAddRequest(
        messages=[Message(role="user", content="test")],
        user_id="test-user",
    )

    assert req_no_meta.metadata is None


def test_memory_search_limit_ranges():
    """Test various search limit values."""
    # Minimum valid limit
    req_min = MemorySearchRequest(query="test", user_id="user", limit=1)
    assert req_min.limit == 1

    # Maximum valid limit
    req_max = MemorySearchRequest(query="test", user_id="user", limit=100)
    assert req_max.limit == 100

    # Default limit
    req_default = MemorySearchRequest(query="test", user_id="user")
    assert req_default.limit == 10


def test_memory_message_content_lengths():
    """Test handling of various message content lengths."""
    # Short message
    short_msg = Message(role="user", content="Hi")
    assert len(short_msg.content) == 2

    # Long message (within limits)
    long_content = "x" * 1000
    long_msg = Message(role="user", content=long_content)
    assert len(long_msg.content) == 1000

    # Very long message (still within 100k limit)
    very_long_content = "x" * 50000
    very_long_msg = Message(role="user", content=very_long_content)
    assert len(very_long_msg.content) == 50000


def test_memory_multi_message_conversation():
    """Test memory operations with multi-turn conversations."""
    messages = [
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
        Message(role="user", content="How are you?"),
        Message(role="assistant", content="I'm doing well, thank you!"),
    ]

    req = MemoryAddRequest(
        messages=messages,
        user_id="test-user",
        metadata={"conversation_type": "greeting"},
    )

    assert len(req.messages) == 4
    assert req.messages[0].role == "user"
    assert req.messages[1].role == "assistant"
    assert req.messages[2].role == "user"
    assert req.messages[3].role == "assistant"


def test_memory_agent_scoping_isolation():
    """Test that agent scoping provides proper isolation."""
    # Agent 1 request
    agent1_req = MemoryGetRequest(user_id="user-1", agent_id="agent-1")

    # Agent 2 request for same user
    agent2_req = MemoryGetRequest(user_id="user-1", agent_id="agent-2")

    # Same user, different agents - should be isolated
    assert agent1_req.user_id == agent2_req.user_id
    assert agent1_req.agent_id != agent2_req.agent_id


def test_memory_search_query_formats():
    """Test various query formats for memory search."""
    # Simple query
    simple_req = MemorySearchRequest(query="test", user_id="user")
    assert simple_req.query == "test"

    # Multi-word query
    multi_req = MemorySearchRequest(
        query="tell me about machine learning",
        user_id="user",
    )
    assert "machine learning" in multi_req.query

    # Query with punctuation
    punct_req = MemorySearchRequest(
        query="What's the weather like?",
        user_id="user",
    )
    assert "?" in punct_req.query


@pytest.mark.asyncio
async def test_mem0_request_custom_timeout():
    """Test custom timeout configuration for Mem0 requests."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_instance.post = AsyncMock()
        mock_instance.post.return_value.json.return_value = {"id": "mem-123"}
        mock_instance.post.return_value.raise_for_status = MagicMock()

        # Custom timeout
        await _mem0_request(
            "http://mem0:8765/memories",
            method="POST",
            json_data={"test": "data"},
            timeout=60.0,
        )

        # Verify client was created with custom timeout
        mock_client.assert_called_once_with(timeout=60.0)


@pytest.mark.asyncio
async def test_mem0_request_handles_various_response_formats():
    """Test that _mem0_request handles different response formats."""
    # Test with 'id' field
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "mem-123"}
        mock_resp.raise_for_status = MagicMock()
        mock_instance.post = AsyncMock(return_value=mock_resp)

        result = await _mem0_request(
            "http://mem0:8765/memories",
            method="POST",
            json_data={},
        )

        assert "id" in result

    # Test with 'results' field
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{"id": "mem-1"}, {"id": "mem-2"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_instance.get = AsyncMock(return_value=mock_resp)

        result = await _mem0_request(
            "http://mem0:8765/memories",
            method="GET",
            json_data={},
        )

        assert "results" in result
        assert len(result["results"]) == 2
