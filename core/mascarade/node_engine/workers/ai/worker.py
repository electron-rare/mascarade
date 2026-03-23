"""AI Worker implementation for the Universal Node Engine.

Wraps Mascarade Router and AgentRegistry to provide graph-executable AI nodes.
Implements the NodeWorker interface for AI domain operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mascarade.node_engine.worker import NodeWorker

if TYPE_CHECKING:
    from mascarade.agents.registry import AgentRegistry
    from mascarade.orchestrator.engine import Orchestrator
    from mascarade.router import Router

logger = logging.getLogger("mascarade.node_engine.workers.ai")


class AIWorker(NodeWorker):
    """
    AI domain worker for executing LLM inference, agent dispatch, and orchestration nodes.

    This worker integrates Mascarade's Router (multi-provider LLM routing) and
    AgentRegistry (agent definitions) into the Universal Node Engine. It provides
    node types for:
    - LLM inference (direct provider calls)
    - Agent dispatch (agent-based routing)
    - Orchestration (multi-step agent workflows)

    The worker follows the NodeWorker interface and is registered with the
    NodeWorkerRegistry at runtime initialization.

    Attributes:
        name: Unique identifier "ai-worker"
        domain: Domain identifier "ai"
        router: Mascarade Router instance for LLM provider access
        registry: AgentRegistry instance for agent definitions
    """

    name: str = "ai-worker"
    domain: str = "ai"

    def __init__(
        self,
        router: Router,
        registry: AgentRegistry,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        """
        Initialize AI worker with router and agent registry.

        Args:
            router: Mascarade Router instance for multi-provider LLM access
            registry: AgentRegistry instance for agent definitions and dispatch
            orchestrator: Optional Orchestrator instance for multi-agent workflows
        """
        self.router = router
        self.registry = registry
        self.orchestrator = orchestrator
        logger.info(
            "AIWorker initialized with router=%s, registry=%s, orchestrator=%s",
            router.__class__.__name__,
            registry.__class__.__name__,
            orchestrator.__class__.__name__ if orchestrator else "None",
        )

    async def execute(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute an AI domain node.

        Dispatches to the appropriate handler based on node_type:
        - ai.llm-inference: Direct LLM inference via Router
        - ai.agent-dispatch: Agent-based inference via AgentRegistry
        - ai.llm-stream: Streaming LLM inference (future)

        Args:
            node_type: Fully qualified node type (e.g., "ai.llm-inference")
            inputs: Dictionary of input port values (e.g., {"prompt": "..."})
            config: Node configuration (e.g., {"model": "gpt-4", "temperature": 0.7})
            context: Execution context for the current graph run

        Returns:
            Dictionary of output port values (e.g., {"response": LLMResponse(...)})

        Raises:
            ValueError: If node_type is not supported by this worker
            RuntimeError: If execution fails due to worker-specific errors
        """
        logger.debug(
            "Executing node_type=%s with inputs=%s, config=%s",
            node_type,
            inputs,
            config,
        )

        # Dispatch to node type handlers (to be implemented in future subtasks)
        if node_type == "ai.llm-inference":
            return await self._execute_llm_inference(inputs, config, context)
        elif node_type == "ai.agent-dispatch":
            return await self._execute_agent_dispatch(inputs, config, context)
        elif node_type == "ai.llm-stream":
            return await self._execute_llm_stream(inputs, config, context)
        elif node_type == "ai.embedding":
            return await self._embedding(inputs, config, context)
        elif node_type == "ai.batch-inference":
            return await self._execute_batch_inference(inputs, config, context)
        elif node_type == "ai.prompt-template":
            # Pure function - not async
            return self._prompt_template(inputs)
        elif node_type == "ai.chain-of-thought":
            return await self._chain_of_thought(inputs, config, context)
        elif node_type == "ai.classify":
            return await self._classify(inputs, config, context)
        elif node_type == "ai.summarize":
            return await self._summarize(inputs, config, context)
        elif node_type == "ai.orchestrate":
            return await self._execute_orchestrate(inputs, config, context)
        elif node_type == "ai.router-select":
            # Pure function - not async
            return self._router_select(inputs, config)
        else:
            raise ValueError(f"Unsupported node type: {node_type}")

    async def validate(
        self,
        node_type: str,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """
        Validate node inputs and configuration before execution.

        Performs domain-specific validation checks:
        - Required inputs are present
        - Agent names exist in AgentRegistry (for agent-dispatch nodes)
        - Configuration values are within valid ranges
        - Referenced resources are available

        Args:
            node_type: Fully qualified node type (e.g., "ai.agent-dispatch")
            inputs: Dictionary of input port values to validate
            config: Node configuration parameters to validate

        Returns:
            List of validation error messages. Empty list if validation passes.
        """
        errors: list[str] = []

        # Dispatch to node type validators (to be implemented in future subtasks)
        if node_type == "ai.llm-inference":
            errors.extend(self._validate_llm_inference(inputs, config))
        elif node_type == "ai.agent-dispatch":
            errors.extend(self._validate_agent_dispatch(inputs, config))
        elif node_type == "ai.llm-stream":
            errors.extend(self._validate_llm_stream(inputs, config))
        elif node_type == "ai.embedding":
            errors.extend(self._validate_embedding(inputs, config))
        elif node_type == "ai.batch-inference":
            errors.extend(self._validate_batch_inference(inputs, config))
        elif node_type == "ai.prompt-template":
            errors.extend(self._validate_prompt_template(inputs, config))
        elif node_type == "ai.chain-of-thought":
            errors.extend(self._validate_chain_of_thought(inputs, config))
        elif node_type == "ai.classify":
            errors.extend(self._validate_classify(inputs, config))
        elif node_type == "ai.summarize":
            errors.extend(self._validate_summarize(inputs, config))
        elif node_type == "ai.orchestrate":
            errors.extend(self._validate_orchestrate(inputs, config))
        elif node_type == "ai.router-select":
            errors.extend(self._validate_router_select(inputs, config))
        else:
            errors.append(f"Unsupported node type: {node_type}")

        return errors

    def capabilities(self) -> dict[str, Any]:
        """
        Declare AI worker capabilities for the registry.

        Returns:
            Dictionary with capability metadata including:
            - node_types: List of supported node types
            - domain: Domain identifier "ai"
            - supports_streaming: Whether streaming is supported
            - max_concurrent: Maximum concurrent executions
        """
        return {
            "node_types": [
                "ai.llm-inference",
                "ai.agent-dispatch",
                "ai.llm-stream",
                "ai.embedding",
                "ai.batch-inference",
                "ai.prompt-template",
                "ai.chain-of-thought",
                "ai.classify",
                "ai.summarize",
                "ai.orchestrate",
                "ai.router-select",
            ],
            "domain": "ai",
            "supports_streaming": True,
            "supports_cancellation": False,  # Future implementation
            "max_concurrent": 10,
            "requires_gpu": False,
            "requires_hardware": False,
            "estimated_memory_mb": 128,
        }

    @property
    def is_available(self) -> bool:
        """
        Check if the AI worker is available for execution.

        The worker is available if the Router has at least one configured provider.
        Workers may be unavailable due to missing API keys or provider configuration.

        Returns:
            True if at least one LLM provider is configured, False otherwise
        """
        # Check if router has any configured providers
        # For now, return True as a skeleton — actual provider check will be
        # implemented when Router integration is complete
        return True

    # Private helper methods (to be implemented in future subtasks)

    async def _execute_llm_inference(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.llm-inference node.

        Wraps Router.send() to provide direct LLM inference via the graph engine.

        Expected inputs:
        - prompt (required): User prompt string
        - system (optional): System prompt string

        Expected config:
        - model (optional): Model name (e.g., "gpt-4")
        - provider (optional): Provider name (e.g., "openai")
        - temperature (optional): Temperature (default: 0.7)
        - max_tokens (optional): Max output tokens (default: 4096)
        - strategy (optional): Routing strategy (default: "best")
        - routing_policy (optional): RouteLLM policy (default: "auto")

        Returns:
            Dictionary with "response" key containing LLMResponse
        """
        # Extract required inputs
        prompt = inputs["prompt"]

        # Extract optional inputs
        system = inputs.get("system")

        # Extract config parameters with defaults
        model = config.get("model")
        provider = config.get("provider")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 4096)
        strategy = config.get("strategy", "best")
        routing_policy = config.get("routing_policy")
        project_id = config.get("project_id") or inputs.get("project_id")
        federation_scope = config.get("federation_scope") or inputs.get(
            "federation_scope"
        )
        knowledge_scope = config.get("knowledge_scope") or inputs.get(
            "knowledge_scope", "project"
        )

        # Build messages list (simple user message)
        messages = [{"role": "user", "content": prompt}]

        # Call Router.send() with extracted parameters
        response = await self.router.send(
            messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

        # Return response wrapped in output dict
        return {"response": response}

    async def _execute_agent_dispatch(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.agent-dispatch node.

        Wraps AgentRegistry.get() and Agent.run() to provide agent-based
        inference via the graph engine. Agents encapsulate system prompts,
        routing preferences, and specialized behavior.

        Expected inputs:
        - agent_name (required): Name of the agent in the AgentRegistry
        - message (required): User message to send to the agent
        - context (optional): Message history for multi-turn conversations

        Expected config:
        - Config parameters are inherited from the agent's settings
        - Override options can be added in future implementations

        Returns:
            Dictionary with "response" key containing LLMResponse
        """
        # Extract required inputs
        agent_name = inputs["agent_name"]
        message = inputs["message"]

        # Extract optional inputs
        message_context = inputs.get("context")
        project_id = config.get("project_id") or inputs.get("project_id")
        federation_scope = config.get("federation_scope") or inputs.get(
            "federation_scope"
        )
        knowledge_scope = config.get("knowledge_scope") or inputs.get(
            "knowledge_scope", "project"
        )

        # Get agent from registry (raises KeyError if not found)
        agent = self.registry.get(agent_name)

        # Call agent.run() with the router
        response = await agent.run(
            prompt=message,
            router=self.router,
            context=message_context,
            registry=self.registry,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

        # Return response wrapped in output dict
        return {"response": response}

    async def _execute_llm_stream(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.llm-stream node.

        Wraps Router.stream() to provide streaming LLM inference via the graph engine.
        Returns an AsyncIterator that yields tokens as they are generated.

        Expected inputs:
        - prompt (required): User prompt string
        - system (optional): System prompt string

        Expected config:
        - model (optional): Model name (e.g., "gpt-4")
        - provider (optional): Provider name (e.g., "openai")
        - temperature (optional): Temperature (default: 0.7)
        - max_tokens (optional): Max output tokens (default: 4096)
        - strategy (optional): Routing strategy (default: "best")
        - routing_policy (optional): RouteLLM policy (default: "auto")
        - domain (optional): Domain for domain-aware routing

        Returns:
            Dictionary with "stream" key containing AsyncIterator[str]
        """
        # Extract required inputs
        prompt = inputs["prompt"]

        # Extract optional inputs
        system = inputs.get("system")

        # Extract config parameters with defaults
        model = config.get("model")
        provider = config.get("provider")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 4096)
        strategy = config.get("strategy", "best")
        routing_policy = config.get("routing_policy")
        domain = config.get("domain")
        project_id = config.get("project_id") or inputs.get("project_id")
        federation_scope = config.get("federation_scope") or inputs.get(
            "federation_scope"
        )
        knowledge_scope = config.get("knowledge_scope") or inputs.get(
            "knowledge_scope", "project"
        )

        # Build messages list (simple user message)
        messages = [{"role": "user", "content": prompt}]

        # Call Router.stream() with extracted parameters and return the async iterator
        stream = self.router.stream(
            messages,
            strategy=strategy,
            routing_policy=routing_policy,
            provider=provider,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            domain=domain,
            project_id=project_id,
            federation_scope=federation_scope,
            knowledge_scope=knowledge_scope,
        )

        # Return stream wrapped in output dict
        return {"stream": stream}

    async def _embedding(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.embedding node.

        Generate embeddings for text input via the provider system.
        Delegates to provider embedding endpoint via Router.

        Expected inputs:
        - text (required): Text to embed

        Expected config:
        - model (optional): Embedding model to use (provider default if not specified)
        - provider (optional): Specific provider for embeddings (auto-select if not specified)

        Returns:
            Dictionary with "vector" key containing EmbeddingVector:
            - values: list[float] - Dense vector embedding
            - model: str - Model identifier used
            - dimensions: int - Vector dimensionality

        Raises:
            NotImplementedError: Embedding support pending provider implementation
        """
        text = inputs["text"]
        model = config.get("model", "text-embedding-3-small")

        from mascarade.rag.embeddings import EmbeddingProvider

        provider = EmbeddingProvider()
        try:
            vector = await provider.embed_query(text, model=model)
            dimensions = provider.dimension_for_model(model)
            return {
                "vector": {
                    "values": vector,
                    "model": model,
                    "dimensions": dimensions,
                },
            }
        finally:
            await provider.close()

    def _validate_llm_inference(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.llm-inference node inputs and configuration.

        Required inputs:
        - prompt: The user prompt to send to the LLM

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "prompt" not in inputs:
            errors.append("Missing required input: prompt")

        return errors

    def _validate_agent_dispatch(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.agent-dispatch node inputs and configuration.

        Required inputs:
        - agent_name: Name of agent in the AgentRegistry
        - message: Message to send to the agent

        Validation checks:
        - agent_name must be present
        - message must be present
        - agent_name must exist in the AgentRegistry

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "agent_name" not in inputs:
            errors.append("Missing required input: agent_name")
        elif not isinstance(inputs["agent_name"], str):
            errors.append("Input 'agent_name' must be a string")
        else:
            # Check if agent exists in registry
            agent_name = inputs["agent_name"]
            try:
                self.registry.get(agent_name)
            except (KeyError, ValueError):
                errors.append(f"Agent '{agent_name}' not found in registry")

        if "message" not in inputs:
            errors.append("Missing required input: message")

        return errors

    def _validate_llm_stream(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.llm-stream node inputs and configuration.

        Required inputs:
        - prompt: The user prompt to send to the LLM (for streaming)

        Note: This has the same validation as ai.llm-inference since
        the inputs are identical. The only difference is in execution
        where stream() is used instead of send().

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        # Same validation as llm-inference
        return self._validate_llm_inference(inputs, config)

    def _validate_embedding(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.embedding node inputs and configuration.

        Required inputs:
        - text: Text to embed

        Optional config:
        - model: Embedding model to use
        - provider: Specific provider for embeddings

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "text" not in inputs:
            errors.append("Missing required input: text")
        elif not isinstance(inputs["text"], str):
            errors.append("Input 'text' must be a string")

        return errors

    async def _execute_batch_inference(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.batch-inference node.

        Processes multiple prompts in parallel using asyncio.gather() to batch
        LLM inference calls. This is more efficient than sequential execution
        when processing multiple independent prompts.

        Expected inputs:
        - prompts (required): List of prompt strings to process in parallel

        Expected config:
        - model (optional): Model name (e.g., "gpt-4")
        - provider (optional): Provider name (e.g., "openai")
        - temperature (optional): Temperature (default: 0.7)
        - max_tokens (optional): Max output tokens (default: 4096)
        - strategy (optional): Routing strategy (default: "best")
        - routing_policy (optional): RouteLLM policy (default: "auto")
        - max_concurrent (optional): Max concurrent requests (default: 10)

        Returns:
            Dictionary with "responses" key containing list of LLMResponse objects
        """
        import asyncio

        # Extract required inputs
        prompts = inputs["prompts"]

        # Extract optional inputs
        system = inputs.get("system")

        # Extract config parameters with defaults
        model = config.get("model")
        provider = config.get("provider")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 4096)
        strategy = config.get("strategy", "best")
        routing_policy = config.get("routing_policy")
        max_concurrent = config.get("max_concurrent", 10)

        # If prompts list is empty, return empty responses list
        if not prompts:
            return {"responses": []}

        # Helper function to process a single prompt
        async def _process_prompt(prompt: str):
            messages = [{"role": "user", "content": prompt}]
            return await self.router.send(
                messages,
                strategy=strategy,
                routing_policy=routing_policy,
                provider=provider,
                model=model,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # Process prompts in parallel using asyncio.gather
        # If there are more prompts than max_concurrent, process in batches
        if len(prompts) <= max_concurrent:
            # Process all prompts at once
            responses = await asyncio.gather(*[_process_prompt(p) for p in prompts])
        else:
            # Process in batches to respect max_concurrent limit
            responses = []
            for i in range(0, len(prompts), max_concurrent):
                batch = prompts[i : i + max_concurrent]
                batch_responses = await asyncio.gather(
                    *[_process_prompt(p) for p in batch]
                )
                responses.extend(batch_responses)

        # Return responses wrapped in output dict
        return {"responses": responses}

    def _prompt_template(
        self,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute ai.prompt-template node.

        Pure function that performs variable substitution in a template string.
        Replaces {{variable}} placeholders with corresponding values from the
        variables dictionary. This is a non-LLM operation.

        Expected inputs:
        - template (required): Template string with {{variable}} placeholders
        - variables (required): Dictionary mapping variable names to values

        Returns:
            Dictionary with "prompt" key containing the rendered template
        """
        # Extract required inputs
        template = inputs["template"]
        variables = inputs.get("variables", {})

        # Perform variable substitution
        result = template
        for key, value in variables.items():
            # Replace {{key}} with the string value
            result = result.replace(f"{{{{{key}}}}}", str(value))

        # Return rendered prompt
        return {"prompt": result}

    def _validate_batch_inference(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.batch-inference node inputs and configuration.

        Required inputs:
        - prompts: List of prompt strings to process in parallel

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "prompts" not in inputs:
            errors.append("Missing required input: prompts")
        elif not isinstance(inputs["prompts"], list):
            errors.append("Input 'prompts' must be a list")

        return errors

    def _validate_prompt_template(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.prompt-template node inputs and configuration.

        Required inputs:
        - template: Template string with {{variable}} placeholders
        - variables: Dictionary mapping variable names to values

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "template" not in inputs:
            errors.append("Missing required input: template")
        elif not isinstance(inputs["template"], str):
            errors.append("Input 'template' must be a string")

        if "variables" not in inputs:
            errors.append("Missing required input: variables")
        elif not isinstance(inputs["variables"], dict):
            errors.append("Input 'variables' must be a dictionary")

        return errors

    async def _chain_of_thought(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.chain-of-thought node.

        Multi-step reasoning with intermediate outputs. Each step feeds its output
        as context to the next step. Maps to Orchestrator's PIPELINE execution mode.

        Expected inputs:
        - question (required): The question to reason about
        - steps (optional): Number of reasoning steps (default: 3)

        Expected config:
        - Same as ai.llm-inference (model, provider, temperature, etc.)

        Returns:
            Dictionary with:
            - reasoning: Array of intermediate reasoning steps
            - answer: Final synthesized answer
            - usage: Aggregate token consumption across all steps
        """
        # Extract inputs
        question = inputs["question"]
        steps = inputs.get("steps", 3)

        # Initialize reasoning chain
        reasoning = []
        current_context = question

        # Execute reasoning steps
        for i in range(steps):
            step_prompt = (
                f"Step {i + 1}/{steps}: Reason about the following.\n\n"
                f"{current_context}\n\n"
                f"Provide your reasoning for this step."
            )

            # Execute LLM inference for this step
            result = await self._execute_llm_inference(
                {"prompt": step_prompt},
                config,
                context,
            )

            # Extract step output
            step_output = result["response"].content
            reasoning.append(step_output)

            # Update context for next step
            current_context = f"{question}\n\nPrevious reasoning:\n" + "\n".join(
                reasoning
            )

        # Final synthesis
        synthesis_prompt = (
            f"Based on the following reasoning steps, provide a final answer.\n\n"
            f"Question: {question}\n\n"
            f"Reasoning:\n" + "\n---\n".join(reasoning)
        )

        final = await self._execute_llm_inference(
            {"prompt": synthesis_prompt},
            config,
            context,
        )

        # Return results
        return {
            "reasoning": reasoning,
            "answer": final["response"].content,
            "usage": final["response"].usage or {},
        }

    def _validate_chain_of_thought(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.chain-of-thought node inputs and configuration.

        Required inputs:
        - question: The question to reason about

        Optional inputs:
        - steps: Number of reasoning steps (default: 3)

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "question" not in inputs:
            errors.append("Missing required input: question")
        elif not isinstance(inputs["question"], str):
            errors.append("Input 'question' must be a string")

        # Validate steps if provided
        if "steps" in inputs:
            steps = inputs["steps"]
            if not isinstance(steps, int):
                errors.append("Input 'steps' must be an integer")
            elif steps < 1:
                errors.append("Input 'steps' must be at least 1")
            elif steps > 10:
                errors.append("Input 'steps' must not exceed 10")

        return errors

    async def _classify(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.classify node.

        Classify text into predefined categories using LLM inference.

        Expected inputs:
        - text (required): Text to classify
        - categories (required): List of available category labels

        Expected config:
        - Same as ai.llm-inference (model, provider, temperature, etc.)
        - Note: temperature is forced to 0.1 for deterministic classification

        Returns:
            Dictionary with:
            - category: Selected category label
            - confidence: Classification confidence (0.0-1.0)
        """
        # Extract required inputs
        text = inputs["text"]
        categories = inputs["categories"]

        # Build classification prompt
        prompt = (
            f"Classify the following text into exactly one of these categories: "
            f"{', '.join(categories)}\n\n"
            f"Text: {text}\n\n"
            f"Respond with only the category name."
        )

        # Execute LLM inference with low temperature for deterministic classification
        result = await self._execute_llm_inference(
            {"prompt": prompt},
            {**config, "temperature": 0.1},
            context,
        )

        # Extract category from response
        category = result["response"].content.strip()

        # Return classification result
        return {
            "category": category,
            "confidence": 1.0,  # Placeholder — real confidence requires logprobs
        }

    async def _summarize(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.summarize node.

        Summarize text using LLM inference.

        Expected inputs:
        - text (required): Text to summarize
        - max_length (optional): Target summary length in words (default: 200)

        Expected config:
        - Same as ai.llm-inference (model, provider, temperature, etc.)

        Returns:
            Dictionary with:
            - summary: Summarized text
        """
        # Extract required inputs
        text = inputs["text"]

        # Extract optional inputs
        max_length = inputs.get("max_length", 200)

        # Build summarization prompt
        prompt = (
            f"Summarize the following text in approximately {max_length} words:\n\n"
            f"{text}"
        )

        # Execute LLM inference
        result = await self._execute_llm_inference(
            {"prompt": prompt},
            config,
            context,
        )

        # Return summary
        return {"summary": result["response"].content}

    def _validate_classify(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.classify node inputs and configuration.

        Required inputs:
        - text: Text to classify
        - categories: List of available category labels

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "text" not in inputs:
            errors.append("Missing required input: text")
        elif not isinstance(inputs["text"], str):
            errors.append("Input 'text' must be a string")

        if "categories" not in inputs:
            errors.append("Missing required input: categories")
        elif not isinstance(inputs["categories"], list):
            errors.append("Input 'categories' must be a list")
        elif len(inputs["categories"]) == 0:
            errors.append("Input 'categories' must not be empty")

        return errors

    def _validate_summarize(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.summarize node inputs and configuration.

        Required inputs:
        - text: Text to summarize

        Optional inputs:
        - max_length: Target summary length in words (default: 200)

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        if "text" not in inputs:
            errors.append("Missing required input: text")
        elif not isinstance(inputs["text"], str):
            errors.append("Input 'text' must be a string")

        # Validate max_length if provided
        if "max_length" in inputs:
            max_length = inputs["max_length"]
            if not isinstance(max_length, int):
                errors.append("Input 'max_length' must be an integer")
            elif max_length < 1:
                errors.append("Input 'max_length' must be at least 1")

        return errors

    async def _execute_orchestrate(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        """
        Execute ai.orchestrate node.

        Orchestrates multi-agent workflows using the Orchestrator engine.
        Supports three execution modes: sequential, parallel, and pipeline.

        Expected inputs:
        - agent_names (required): List of agent names to orchestrate
        - prompt (required): Input prompt for the workflow
        - mode (optional): Execution mode - "sequential", "parallel", or "pipeline" (default: "sequential")

        Expected config:
        - routing_overrides (optional): Dict mapping agent_name -> routing config
        - skip_on_error (optional): Continue execution on error (default: False)
        - fallback_map (optional): Dict mapping agent_name -> fallback_agent_name
        - timeout (optional): Timeout for parallel execution (default: 120.0)

        Returns:
            Dictionary with:
            - run_id: Unique identifier for this orchestration run
            - mode: Execution mode used
            - results: List of TaskResult objects from each agent
            - errors: List of error messages (if any)
        """
        from mascarade.orchestrator.engine import ExecutionMode

        # Check if orchestrator is available
        if self.orchestrator is None:
            raise RuntimeError(
                "Orchestrator not available - AIWorker was initialized without orchestrator"
            )

        # Extract required inputs
        agent_names = inputs["agent_names"]
        prompt = inputs["prompt"]

        # Extract optional inputs with defaults
        mode_str = inputs.get("mode", "sequential")
        mode = ExecutionMode(mode_str)

        # Extract config parameters
        routing_overrides = config.get("routing_overrides")
        skip_on_error = config.get("skip_on_error", False)
        fallback_map = config.get("fallback_map")

        # Execute orchestration
        orchestration_run = await self.orchestrator.run(
            agent_names=agent_names,
            prompt=prompt,
            mode=mode,
            routing_overrides=routing_overrides,
            skip_on_error=skip_on_error,
            fallback_map=fallback_map,
        )

        # Convert TaskResult objects to serializable dictionaries
        results = []
        errors = []
        for task_result in orchestration_run.results:
            result_dict = {
                "agent_name": task_result.agent_name,
                "response": {
                    "content": task_result.response.content,
                    "model": task_result.response.model,
                    "provider": task_result.response.provider,
                    "usage": task_result.response.usage or {},
                },
                "step": task_result.step,
                "error": task_result.error,
                "remote": task_result.remote,
                "selected_by": task_result.selected_by,
                "peer_id": task_result.peer_id,
                "node_id": task_result.node_id,
                "role": task_result.role,
                "transport": task_result.transport,
                "latency_ms": task_result.latency_ms,
                "fallback_used": task_result.fallback_used,
                "fallback_agent": task_result.fallback_agent,
            }
            results.append(result_dict)
            if task_result.error:
                errors.append(task_result.error)

        # Return orchestration results
        return {
            "run_id": orchestration_run.run_id,
            "mode": orchestration_run.mode.value,
            "results": results,
            "errors": errors,
        }

    def _validate_orchestrate(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.orchestrate node inputs and configuration.

        Required inputs:
        - agent_names: List of agent names to orchestrate
        - prompt: Input prompt for the workflow

        Optional inputs:
        - mode: Execution mode - "sequential", "parallel", or "pipeline"

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        # Check if orchestrator is available
        if self.orchestrator is None:
            errors.append(
                "Orchestrator not available - AIWorker requires orchestrator for ai.orchestrate nodes"
            )
            return errors

        # Validate agent_names
        if "agent_names" not in inputs:
            errors.append("Missing required input: agent_names")
        elif not isinstance(inputs["agent_names"], list):
            errors.append("Input 'agent_names' must be a list")
        elif len(inputs["agent_names"]) == 0:
            errors.append("Input 'agent_names' must not be empty")
        else:
            # Validate each agent exists in registry
            for agent_name in inputs["agent_names"]:
                if not isinstance(agent_name, str):
                    errors.append(
                        f"Agent name must be a string, got: {type(agent_name).__name__}"
                    )
                    continue
                try:
                    self.registry.get(agent_name)
                except (KeyError, ValueError):
                    errors.append(f"Agent '{agent_name}' not found in registry")

        # Validate prompt
        if "prompt" not in inputs:
            errors.append("Missing required input: prompt")
        elif not isinstance(inputs["prompt"], str):
            errors.append("Input 'prompt' must be a string")

        # Validate mode if provided
        if "mode" in inputs:
            mode = inputs["mode"]
            if not isinstance(mode, str):
                errors.append("Input 'mode' must be a string")
            elif mode not in {"sequential", "parallel", "pipeline"}:
                errors.append(
                    f"Input 'mode' must be one of: sequential, parallel, pipeline. Got: {mode}"
                )

        return errors

    def _router_select(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute ai.router-select node.

        Selects a provider and model based on routing strategy without executing
        an inference call. This is useful for understanding which provider would
        be selected for a given strategy before making an actual LLM call.

        Expected inputs:
        - strategy (required): Routing strategy - "cheapest", "fastest", "best", "specific"
        - provider_name (optional): For "specific" strategy, the provider to use
        - domain (optional): Domain hint for domain-aware routing

        Expected config:
        - constraints (optional): Additional constraints (reserved for future use)

        Returns:
            Dictionary with:
            - provider: Selected provider name
            - model: Selected model identifier (default model for the provider)
        """
        from mascarade.router.router import Strategy

        # Extract strategy from inputs
        strategy_str = inputs["strategy"]
        strategy = Strategy(strategy_str)

        # Extract optional parameters
        provider_name = inputs.get("provider_name")
        domain = inputs.get("domain")

        # Use Router's internal provider selection logic
        # This mirrors the selection that would happen during an actual inference call
        selected_provider = self.router._select_provider(
            strategy=strategy,
            provider_name=provider_name,
            domain=domain,
        )

        # Get the default model for the selected provider
        # Providers expose their available models via available_models()
        available_models = selected_provider.available_models()
        default_model = available_models[0] if available_models else ""

        # Return the selected provider and model
        return {
            "provider": selected_provider.name,
            "model": default_model,
        }

    def _validate_router_select(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> list[str]:
        """Validate ai.router-select node inputs and configuration.

        Required inputs:
        - strategy: Routing strategy - "cheapest", "fastest", "best", "specific"

        Optional inputs:
        - provider_name: For "specific" strategy, the provider to use
        - domain: Domain hint for domain-aware routing

        Args:
            inputs: Dictionary of input port values
            config: Node configuration parameters

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: list[str] = []

        # Validate required strategy input
        if "strategy" not in inputs:
            errors.append("Missing required input: strategy")
        elif not isinstance(inputs["strategy"], str):
            errors.append("Input 'strategy' must be a string")
        else:
            # Validate strategy value
            valid_strategies = {"cheapest", "fastest", "best", "specific"}
            strategy = inputs["strategy"]
            if strategy not in valid_strategies:
                errors.append(
                    f"Input 'strategy' must be one of: {', '.join(sorted(valid_strategies))}. Got: {strategy}"
                )

            # If strategy is "specific", provider_name is required
            if strategy == "specific" and "provider_name" not in inputs:
                errors.append(
                    "Input 'provider_name' is required when strategy is 'specific'"
                )

        # Validate provider_name if provided
        if "provider_name" in inputs:
            provider_name = inputs["provider_name"]
            if not isinstance(provider_name, str):
                errors.append("Input 'provider_name' must be a string")
            elif provider_name not in self.router.available_providers:
                errors.append(
                    f"Provider '{provider_name}' not available. "
                    f"Available providers: {', '.join(self.router.available_providers)}"
                )

        # Validate domain if provided
        if "domain" in inputs:
            domain = inputs["domain"]
            if not isinstance(domain, str):
                errors.append("Input 'domain' must be a string")

        return errors
