"""A2A (Agent-to-Agent) protocol support for Mascarade."""

from mascarade.a2a.agent_card import AgentCard, generate_agent_card
from mascarade.a2a.discovery import A2ADiscovery
from mascarade.a2a.router import mount_a2a

__all__ = ["AgentCard", "generate_agent_card", "A2ADiscovery", "mount_a2a"]
