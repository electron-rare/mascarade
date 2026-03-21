"""Mascarade Persistence Module - Context, Memory, Skills, and MCP Persistence."""

from mascarade.persistence.context_manager import (
    ContextPersistenceManager,
    PersistentOrchestrationContext,
    BaseContext,
    save_orchestration_context,
    load_orchestration_context
)

from mascarade.persistence.memory_manager import (
    MultiBackendMemoryManager,
    MemoryEntry,
    create_memory_entry,
    create_conversation_memory
)

from mascarade.persistence.skills_manager import (
    SkillsPersistenceManager,
    SkillDefinition,
    SkillExecutionRecord,
    create_skill_definition,
    create_execution_record,
    execute_skill_with_recording
)

from mascarade.persistence.mcp_persistence import (
    MCPPersistenceManager,
    PersistentModelContext,
    create_persistent_mcp_context,
    load_mcp_context_with_persistence,
    update_mcp_context_with_persistence
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
    "update_mcp_context_with_persistence"
]