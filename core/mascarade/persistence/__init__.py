"""Mascarade Persistence Module - Context, Memory, Skills, and MCP Persistence."""

from mascarade.persistence.context_manager import (
    BaseContext,
    ContextPersistenceManager,
    PersistentOrchestrationContext,
    load_orchestration_context,
    save_orchestration_context,
)
from mascarade.persistence.mcp_persistence import (
    MCPPersistenceManager,
    PersistentModelContext,
    create_persistent_mcp_context,
    load_mcp_context_with_persistence,
    update_mcp_context_with_persistence,
)
from mascarade.persistence.memory_manager import (
    MemoryEntry,
    MultiBackendMemoryManager,
    create_conversation_memory,
    create_memory_entry,
)
from mascarade.persistence.skills_manager import (
    SkillDefinition,
    SkillExecutionRecord,
    SkillsPersistenceManager,
    create_execution_record,
    create_skill_definition,
    execute_skill_with_recording,
)

__all__ = [
    # Context Management
    "ContextPersistenceManager",
    "PersistentOrchestrationContext",
    "BaseContext",
    "save_orchestration_context",
    "load_orchestration_context",
    # Memory Management
    "MultiBackendMemoryManager",
    "MemoryEntry",
    "create_memory_entry",
    "create_conversation_memory",
    # Skills Management
    "SkillsPersistenceManager",
    "SkillDefinition",
    "SkillExecutionRecord",
    "create_skill_definition",
    "create_execution_record",
    "execute_skill_with_recording",
    # MCP Persistence
    "MCPPersistenceManager",
    "PersistentModelContext",
    "create_persistent_mcp_context",
    "load_mcp_context_with_persistence",
    "update_mcp_context_with_persistence",
]
