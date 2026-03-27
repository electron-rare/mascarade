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
from mascarade.node_engine.cross_domain.adapters import (
    ALL_ADAPTERS,
    AIToCADAdapter,
    AIToElectronicsAdapter,
    CADToElectronicsAdapter,
    ElectronicsToHardwareAdapter,
    HardwareToAIAdapter,
)
from mascarade.node_engine.cross_domain.envelope import CrossDomainEnvelope
from mascarade.node_engine.cross_domain.orchestrator import (
    AdapterInsertionRecord,
    CrossDomainOrchestrator,
    OrchestrationResult,
)
from mascarade.node_engine.cross_domain.federation import (
    DOMAIN_CAPABILITY_MAP,
    ExecutionPlan,
    FederatedExecutor,
    MachineProfile,
    NodeAssignment,
    ResourceEstimate,
)
from mascarade.node_engine.cross_domain.register import (
    AdapterRegistry,
    register_all_adapters,
)

__all__ = [
    # Base
    "CrossDomainAdapter",
    "AdapterMapping",
    "CrossDomainEnvelope",
    # Concrete adapters
    "AIToCADAdapter",
    "AIToElectronicsAdapter",
    "CADToElectronicsAdapter",
    "ElectronicsToHardwareAdapter",
    "HardwareToAIAdapter",
    "ALL_ADAPTERS",
    # Orchestrator
    "CrossDomainOrchestrator",
    "OrchestrationResult",
    "AdapterInsertionRecord",
    # Federation
    "FederatedExecutor",
    "ExecutionPlan",
    "MachineProfile",
    "NodeAssignment",
    "ResourceEstimate",
    "DOMAIN_CAPABILITY_MAP",
    # Registry
    "AdapterRegistry",
    "register_all_adapters",
]
