"""
Wizard Agents Management Pydantic v2 Schemas.

Defines request/response types for agent selection, orchestration, and result tracking.
All schemas use Pydantic v2 with strict validation and async field validators.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_core import PydanticUndefinedType


# ============================================================================
# Enums
# ============================================================================


class ExecutionMode(str, Enum):
    """Task execution mode: sequential or parallel."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class WizardRunStatus(str, Enum):
    """Lifecycle status for a wizard run."""
    PENDING = "pending"
    SELECTING = "selecting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentSelectionStatus(str, Enum):
    """Agent execution status within a run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class CostClass(str, Enum):
    """Cost tier for agent execution."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Constraints & Metadata
# ============================================================================


class ExecutionConstraints(BaseModel):
    """Resource and cost constraints for wizard execution."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    max_cost: float = Field(
        default=1.0,
        ge=0.0,
        le=100.0,
        description="Max cost in USD for the entire run.",
    )
    max_latency_ms: int = Field(
        default=10000,
        ge=100,
        le=120000,
        description="Max latency in milliseconds.",
    )
    required_models: list[str] = Field(
        default_factory=list,
        description="Specific models that must be available.",
    )
    
    @field_validator("required_models")
    @classmethod
    def validate_required_models(cls, v: list[str]) -> list[str]:
        """Validate that required models list is not too long."""
        if len(v) > 10:
            raise ValueError("required_models list too long (max 10)")
        if any(not isinstance(m, str) or len(m) == 0 for m in v):
            raise ValueError("each required_model must be a non-empty string")
        return v


class ExecutionMetrics(BaseModel):
    """Metrics collected during agent execution."""
    
    model_config = ConfigDict(frozen=True)
    
    duration_ms: float = Field(ge=0, description="Execution time in milliseconds.")
    tokens_used: int = Field(default=0, ge=0, description="Tokens consumed.")
    cost_usd: float = Field(ge=0, description="Cost in USD.")
    provider_used: Optional[str] = Field(default=None, description="LLM provider name.")


# ============================================================================
# Wizard Request
# ============================================================================


class WizardAgentRunRequest(BaseModel):
    """Request to run agents for a task."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    task: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Task description or prompt.",
    )
    domain: str = Field(
        ...,
        pattern=r'^[a-z_]+$',
        description="Agent domain (electronics, rag, orchestration, code, design, etc.).",
    )
    constraints: ExecutionConstraints = Field(
        default_factory=ExecutionConstraints,
        description="Resource/cost constraints.",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific context (files, settings, metadata).",
    )
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEQUENTIAL,
        description="Run agents sequentially or in parallel.",
    )
    timeout_seconds: float = Field(
        default=120,
        ge=10,
        le=3600,
        description="Total timeout for the entire run.",
    )
    continue_on_error: bool = Field(
        default=False,
        description="If True, continue even if an agent fails (sequential mode).",
    )
    fail_on_partial: bool = Field(
        default=True,
        description="If False, allow partial results from parallel execution.",
    )
    
    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Ensure domain is a known type."""
        valid_domains = {
            "electronics", "rag", "orchestration", "code", "design",
            "analysis", "generation", "validation"
        }
        if v not in valid_domains:
            raise ValueError(f"domain must be one of {valid_domains}")
        return v


# ============================================================================
# Agent Selection
# ============================================================================


class SelectedAgentInfo(BaseModel):
    """Metadata for a selected agent in the result."""
    
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(description="Agent name.")
    domain: str = Field(description="Agent domain.")
    selection_score: float = Field(ge=0.0, le=1.0, description="Selection score (0-1).")
    cost_class: CostClass = Field(description="Cost tier of this agent.")


class WizardAgentSelectionResult(BaseModel):
    """Result of agent selection phase."""
    
    model_config = ConfigDict(frozen=True)
    
    task_id: str = Field(description="Unique task/run identifier.")
    selected_agents: list[SelectedAgentInfo] = Field(
        default_factory=list,
        description="Selected agents ordered by score.",
    )
    total_agents_evaluated: int = Field(ge=0, description="Total agents considered.")
    selection_timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Agent Execution Result
# ============================================================================


class WizardAgentResult(BaseModel):
    """Result from a single agent's execution."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    task_id: str = Field(description="Parent task/run identifier.")
    agent_name: str = Field(description="Name of the agent that ran.")
    status: AgentSelectionStatus = Field(description="Execution status.")
    output: Optional[dict[str, Any]] = Field(
        default=None,
        description="Agent output (if successful).",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message (if failed).",
    )
    metrics: Optional[ExecutionMetrics] = Field(
        default=None,
        description="Performance metrics.",
    )
    completion_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator("status")
    @classmethod
    def validate_status_consistency(cls, v: AgentSelectionStatus, info) -> AgentSelectionStatus:
        """Ensure output/error consistency with status."""
        if v == AgentSelectionStatus.COMPLETED and info.data.get("output") is None:
            raise ValueError("status=completed requires non-null output")
        if v == AgentSelectionStatus.FAILED and info.data.get("error") is None:
            raise ValueError("status=failed requires non-null error")
        return v


# ============================================================================
# Final Run Result
# ============================================================================


class AggregatedAnalysis(BaseModel):
    """Aggregated insights from multiple agent results."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    summary: str = Field(
        default="",
        max_length=2000,
        description="High-level summary of findings.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1).",
    )
    raw_analyses: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-agent analysis details.",
    )


class WizardRunResult(BaseModel):
    """Final result of a wizard run."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    task_id: str = Field(description="Unique task identifier.")
    status: WizardRunStatus = Field(description="Overall execution status.")
    execution_mode: ExecutionMode = Field(description="Mode used (sequential/parallel).")
    results: list[WizardAgentResult] = Field(
        default_factory=list,
        description="Per-agent results.",
    )
    aggregated_analysis: Optional[AggregatedAnalysis] = Field(
        default=None,
        description="Aggregated insights.",
    )
    total_duration_ms: float = Field(default=0.0, ge=0.0, description="Total runtime.")
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost.")
    completion_timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_reason: Optional[str] = Field(
        default=None,
        description="Root cause if status is failed or timeout.",
    )


# ============================================================================
# Status & Polling
# ============================================================================


class WizardRunStatusResponse(BaseModel):
    """Status response for polling task execution."""
    
    model_config = ConfigDict(frozen=True)
    
    task_id: str
    status: WizardRunStatus
    progress_percent: int = Field(ge=0, le=100)
    results: Optional[list[WizardAgentResult]] = None
    error: Optional[str] = None
    last_update: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Agent Registry Extensions
# ============================================================================


class AgentCapability(BaseModel):
    """Capability descriptor for an agent."""
    
    name: str = Field(description="Capability name (e.g., 'spice_simulation').")
    domain: str = Field(description="Domain this capability serves.")
    required_context: list[str] = Field(
        default_factory=list,
        description="Required context keys (e.g., ['circuit_schema']).",
    )
    cost_class: CostClass = Field(description="Cost tier.")
    concurrent_limit: int = Field(default=1, ge=1, description="Max parallel executions.")
    timeout_seconds: float = Field(default=300, ge=10, le=3600)
    circuit_breaker_enabled: bool = Field(default=True)


class WizardAgentCapabilityMatrix(BaseModel):
    """Matrix of available agents and their capabilities."""
    
    model_config = ConfigDict(frozen=True)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agents: dict[str, AgentCapability] = Field(
        default_factory=dict,
        description="Mapping of agent_name → capability.",
    )
    domain_to_agents: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Reverse mapping: domain → [agent_names].",
    )
    total_agents: int = Field(ge=0)


# ============================================================================
# Error Classes
# ============================================================================


class NoAgentAvailableError(Exception):
    """No agents found matching selection criteria."""
    pass


class WizardExecutionError(Exception):
    """Error during wizard execution."""
    pass


class WizardTimeoutError(Exception):
    """Task execution exceeded timeout."""
    pass
