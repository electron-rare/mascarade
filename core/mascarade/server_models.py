"""Pydantic request/response models for the Mascarade HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from mascarade.orchestrator.engine import ExecutionMode as OrchestrationExecutionMode
from mascarade.orchestrator.templates import ExecutionMode as TemplateExecutionMode
from mascarade.router.router import Strategy

# --- OpenAI-compatible models ---


RoutingPolicy = Literal["auto", "strong", "cheap", "fast"]


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=100_000)


class ChatCompletionMessageParam(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatCompletionMessageParam]
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=128000)


class ChatCompletionMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str | None = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ChatCompletionChunkDelta(BaseModel):
    role: str | None = None
    content: str | None = None


class ChatCompletionChunkChoice(BaseModel):
    index: int = 0
    delta: ChatCompletionChunkDelta
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


class ModelObject(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "mascarade"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelObject]


# --- Core request models ---


class SendRequest(BaseModel):
    messages: list[Message] = Field(max_length=200)
    strategy: Strategy = Strategy.BEST
    routing_policy: RoutingPolicy = "auto"
    provider: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    system: str | None = Field(default=None, max_length=10_000)
    response_format: dict | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)


class AgentGatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    phase: Literal["pre", "post"] = "pre"
    required: bool = True
    check: str = Field(default="", max_length=200)
    status: Literal["pending", "passed", "failed", "skipped"] = "pending"


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)
    system_prompt: str = Field(max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    strategy: Strategy = Strategy.ROUTELLM
    routing_policy: RoutingPolicy = "auto"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0, le=128000)
    tools: list[str] = Field(default_factory=list, max_length=128)
    skills: list[str] = Field(default_factory=list, max_length=128)
    category: str | None = Field(default=None, max_length=100)
    retry_config: dict[str, Any] | None = Field(default=None)
    gates: list[AgentGatePayload] = Field(default_factory=list, max_length=64)
    evidence_refs: list[str] = Field(default_factory=list, max_length=128)
    capabilities: list[str] = Field(default_factory=list, max_length=128)
    cluster: str | None = Field(default=None, max_length=100)


class AgentUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=1000)
    system_prompt: str | None = Field(default=None, max_length=50_000)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    strategy: Strategy | None = None
    routing_policy: RoutingPolicy | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=128000)
    tools: list[str] | None = Field(default=None, max_length=128)
    skills: list[str] | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=100)
    retry_config: dict[str, Any] | None = Field(default=None)
    gates: list[AgentGatePayload] | None = Field(default=None, max_length=64)
    evidence_refs: list[str] | None = Field(default=None, max_length=128)
    capabilities: list[str] | None = Field(default=None, max_length=128)
    cluster: str | None = Field(default=None, max_length=100)
    version_note: str | None = Field(default=None, max_length=500)


class PromptVersionResponse(BaseModel):
    version_number: int = Field(ge=1)
    timestamp: str = Field(min_length=1, max_length=100)
    content: str = Field(max_length=500_000)
    author_hash: str = Field(max_length=64)
    diff: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class PromptHistoryResponse(BaseModel):
    versions: list[PromptVersionResponse]
    total: int = Field(ge=0)


class AgentRoutingOverride(BaseModel):
    peer_id: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    preferred_provider: str | None = Field(default=None, max_length=50)
    preferred_model: str | None = Field(default=None, max_length=100)
    routing_policy: RoutingPolicy | None = None


class TaskRequest(BaseModel):
    agent_names: list[str] = Field(max_length=20)
    prompt: str = Field(min_length=1, max_length=100_000)
    mode: OrchestrationExecutionMode = OrchestrationExecutionMode.SEQUENTIAL
    routing_overrides: dict[str, AgentRoutingOverride] = Field(default_factory=dict)


class TemplateDeployRequest(BaseModel):
    input: str = Field(min_length=1, max_length=100_000)
    routing_overrides: dict[str, AgentRoutingOverride] = Field(default_factory=dict)


class WorkflowTemplateCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    agent_names: list[str] = Field(min_length=1, max_length=20)
    mode: TemplateExecutionMode = TemplateExecutionMode.SEQUENTIAL
    routing_overrides: dict[str, AgentRoutingOverride] = Field(default_factory=dict)
    documentation: str = Field(default="", max_length=5000)


class WorkflowTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    agent_names: list[str] | None = Field(default=None, min_length=1, max_length=20)
    mode: TemplateExecutionMode | None = None
    routing_overrides: dict[str, AgentRoutingOverride] | None = None
    documentation: str | None = Field(default=None, max_length=5000)


class ClusterForwardSendRequest(SendRequest):
    peer_id: str | None = Field(default=None, max_length=100)
    preferred_role: str | None = Field(default=None, max_length=100)
    allow_local: bool = True


class KnowledgeBaseAppendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)


class KnowledgeBaseCreateRequest(BaseModel):
    parent_id: str = Field(max_length=200)
    title: str = Field(max_length=500)
    content: str = Field(default="", max_length=50_000)


class KnowledgeScribeRequest(BaseModel):
    messages: list[Message] = Field(max_length=200)
    push_to: str | None = Field(default=None, max_length=200)
    run_id: str | None = Field(default=None, max_length=64)


class GitHubDispatchRequest(BaseModel):
    workflow_file: str = Field(min_length=1, max_length=200)
    ref: str | None = Field(default=None, max_length=200)
    inputs: dict[str, str | int | float | bool] = Field(default_factory=dict)
    run_id: str | None = Field(default=None, max_length=64)


class GitHubDispatchStatusRequest(BaseModel):
    dispatch_id: str = Field(min_length=1, max_length=200)
    run_id: str | None = Field(default=None, max_length=64)


class IndustrialMcpToolRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = Field(default=None, max_length=64)


class FreeCADCreateDocumentRequest(BaseModel):
    output_path: str = Field(min_length=1, max_length=400)
    name: str = Field(default="McpDocument", min_length=1, max_length=80)
    primitive: Literal["box"] = "box"
    length: float = Field(default=10.0, gt=0, le=10_000)
    width: float = Field(default=8.0, gt=0, le=10_000)
    height: float = Field(default=6.0, gt=0, le=10_000)
    run_id: str | None = Field(default=None, max_length=64)


class FreeCADExportDocumentRequest(BaseModel):
    document_path: str = Field(min_length=1, max_length=400)
    output_path: str = Field(min_length=1, max_length=400)
    run_id: str | None = Field(default=None, max_length=64)


class FreeCADRunScriptRequest(BaseModel):
    script: str = Field(min_length=1, max_length=20_000)
    output_path: str | None = Field(default=None, max_length=400)
    run_id: str | None = Field(default=None, max_length=64)


class OpenSCADValidateRequest(BaseModel):
    source: str = Field(min_length=1, max_length=20_000)
    run_id: str | None = Field(default=None, max_length=64)


class OpenSCADRenderRequest(BaseModel):
    source: str = Field(min_length=1, max_length=20_000)
    output_path: str = Field(min_length=1, max_length=400)
    run_id: str | None = Field(default=None, max_length=64)


class ComfyUIGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    negative_prompt: str = Field(default="", max_length=10_000)
    checkpoint: str | None = Field(default=None, max_length=200)
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    steps: int = Field(default=20, ge=1, le=150)
    cfg: float = Field(default=7.0, ge=1.0, le=30.0)
    seed: int = -1


class ComfyUIWorkflowRequest(BaseModel):
    workflow: dict


class RateLimitUpdate(BaseModel):
    """Request model for updating user rate limits."""

    requests_per_minute: int | None = Field(default=None, ge=0)
    requests_per_hour: int | None = Field(default=None, ge=0)
    requests_per_day: int | None = Field(default=None, ge=0)
    tokens_per_day: int | None = Field(default=None, ge=0)


class QdrantCreateCollectionRequest(BaseModel):
    vector_size: int = Field(gt=0, le=65536)
    distance: Literal["Cosine", "Euclid", "Dot"] = "Cosine"
    on_disk_payload: bool = False


class QdrantUpsertPointsRequest(BaseModel):
    points: list[dict[str, Any]] = Field(max_length=1000)
    wait: bool = True


class QdrantSearchRequest(BaseModel):
    query_vector: list[float] = Field(max_length=65536)
    limit: int = Field(default=10, gt=0, le=100)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    with_payload: bool = True
    with_vector: bool = False
    filter_conditions: dict[str, Any] | None = None


class QdrantRecommendRequest(BaseModel):
    positive: list[str | int] = Field(min_length=1, max_length=100)
    negative: list[str | int] | None = Field(default=None, max_length=100)
    limit: int = Field(default=10, gt=0, le=100)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    with_payload: bool = True
    with_vector: bool = False
    filter_conditions: dict[str, Any] | None = None


class QdrantSemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    limit: int = Field(default=10, gt=0, le=100)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class QdrantRAGRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    limit: int = Field(default=5, gt=0, le=20)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class BenchmarkRunRequest(BaseModel):
    domain: str | None = Field(default=None, max_length=50)
    providers: list[str] | None = Field(default=None, max_length=10)
    difficulty: str | None = Field(default=None, max_length=20)
    limit: int | None = Field(default=None, gt=0, le=100)


class ModelDeploymentWebhook(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=100)
    event_type: str = Field(default="deployment", max_length=50)
    domain: str | None = Field(default=None, max_length=50)
    limit: int | None = Field(default=None, gt=0, le=100)
    background: bool = Field(default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Provider key management models ---


class ProviderKeyUpdate(BaseModel):
    keys: dict[str, str] = Field(description="Map ENV_VAR -> value")


class APIKeyCreate(BaseModel):
    key: str = Field(min_length=8, max_length=256, description="Nouvelle cle API")


class APIKeyRemove(BaseModel):
    key: str = Field(min_length=1, max_length=256, description="Cle API a retirer")


# --- Analytics models ---


class ProviderCostSummary(BaseModel):
    provider: str
    model: str
    total_cost: float = Field(ge=0.0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    request_count: int = Field(ge=0)


class CostAnalyticsResponse(BaseModel):
    total_cost: float = Field(ge=0.0)
    total_requests: int = Field(ge=0)
    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    by_provider: list[ProviderCostSummary]
