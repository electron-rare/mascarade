"""Domain-specific types for the Universal Node Engine."""

__all__ = []

try:
    from mascarade.node_engine.domains.electronics import ELECTRONICS_DOMAIN_TYPES

    __all__.append("ELECTRONICS_DOMAIN_TYPES")
except ImportError:
    pass
