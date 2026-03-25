"""Cross-domain integration layer for Universal Node Engine.

Phase 5 — Cross-Domain Integration:
- Type adapters for converting between domain-specific port types
- Unified orchestration pipeline for multi-domain workflows
- Federated graph execution across services and machines
- Data serialization contracts and error propagation
- Distributed tracing and observability

See SPEC-029-P5 for full specification.
"""

from __future__ import annotations

from mascarade.node_engine.cross_domain.adapter import (
    AdapterMapping,
    CrossDomainAdapter,
)
from mascarade.node_engine.cross_domain.envelope import CrossDomainEnvelope

__all__ = [
    "CrossDomainAdapter",
    "AdapterMapping",
    "CrossDomainEnvelope",
]
