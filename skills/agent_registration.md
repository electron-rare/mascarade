# Agent Registration System

## Overview
Mascarade uses an AgentRegistry to manage and orchestrate multiple agents with different capabilities.

## Agent Registry Structure

### File: `core/mascarade/agents/registry.py`
```python
from typing import Dict, Type, Optional
from .base import BaseAgent

class AgentRegistry:
    """Central registry for all available agents"""
    
    def __init__(self):
        self._agents: Dict[str, Type[BaseAgent]] = {}
        self._instances: Dict[str, BaseAgent] = {}
    
    def register(self, agent_id: str, agent_class: Type[BaseAgent]):
        """Register a new agent class"""
        if agent_id in self._agents:
            raise ValueError(f"Agent {agent_id} already registered")
        self._agents[agent_id] = agent_class
    
    def get(self, agent_id: str) -> BaseAgent:
        """Get agent instance (creates if doesn't exist)"""
        if agent_id not in self._agents:
            raise KeyError(f"Agent {agent_id} not found")
        
        if agent_id not in self._instances:
            self._instances[agent_id] = self._agents[agent_id]()
        
        return self._instances[agent_id]
    
    def list_agents(self) -> list[str]:
        """List all registered agent IDs"""
        return list(self._agents.keys())
    
    def unregister(self, agent_id: str):
        """Remove an agent from registry"""
        if agent_id in self._agents:
            del self._agents[agent_id]
        if agent_id in self._instances:
            del self._instances[agent_id]
```

## Base Agent Interface

### File: `core/mascarade/agents/base.py`
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncIterator
from pydantic import BaseModel

class AgentConfig(BaseModel):
    name: str
    description: str = ""
    capabilities: list[str] = []

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = AgentConfig(**config) if config else AgentConfig(name=self.__class__.__name__)
        self.initialized = False
    
    async def initialize(self):
        """Initialize agent resources"""
        self.initialized = True
    
    @abstractmethod
    async def execute(
        self,
        input: Dict[str, Any],
        strategy: str = "best"
    ) -> Dict[str, Any]:
        """Execute agent with given input"""
        pass
    
    @abstractmethod
    async def stream(
        self,
        input: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream execution results"""
        pass
    
    def can_handle(self, capability: str) -> bool:
        """Check if agent can handle capability"""
        return capability in self.config.capabilities
```

## Creating a New Agent

### Example: Research Agent
```python
from .base import BaseAgent
from ..router import LLMRouter

class ResearchAgent(BaseAgent):
    """Agent for research tasks"""
    
    def __init__(self):
        config = {
            "name": "research_agent",
            "description": "Performs web research and analysis",
            "capabilities": ["research", "analysis", "summarization"]
        }
        super().__init__(config)
    
    async def execute(self, input: Dict[str, Any], strategy: str = "best") -> Dict[str, Any]:
        router = LLMRouter(strategy=strategy)
        
        # Use LLM for research
        prompt = f"Research: {input['topic']}\n\n{input['question']}"
        result = await router.generate(prompt)
        
        return {
            "research_results": result,
            "sources": input.get("sources", []),
            "confidence": 0.85
        }
    
    async def stream(self, input: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        # Stream research progress
        yield {"status": "starting", "progress": 0}
        
        # Simulate research steps
        for step in ["gathering_sources", "analyzing", "summarizing"]:
            yield {"status": step, "progress": 0.3 * (step.index + 1)}
        
        # Final result
        result = await self.execute(input)
        yield {"status": "completed", "result": result}
```

## Registering Agents

### In Application Initialization
```python
# core/mascarade/__init__.py
from .agents.registry import AgentRegistry
from .agents.research import ResearchAgent
from .agents.analysis import AnalysisAgent

# Create global registry
agent_registry = AgentRegistry()

# Register built-in agents
def register_default_agents():
    agent_registry.register("research", ResearchAgent)
    agent_registry.register("analysis", AnalysisAgent)
    # Add more agents...
```

## Using Agents in Orchestrator

### Example: Agent Execution
```python
from ..agents.registry import agent_registry

class Orchestrator:
    async def execute_agent(self, agent_id: str, input_data: dict, strategy: str = "best"):
        try:
            agent = agent_registry.get(agent_id)
            
            # Initialize if needed
            if not agent.initialized:
                await agent.initialize()
            
            # Execute agent
            result = await agent.execute(input_data, strategy)
            return {"success": True, "result": result}
            
        except KeyError:
            return {"success": False, "error": "Agent not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

## Dynamic Agent Loading

### Loading from Plugins
```python
import importlib
from pathlib import Path

def load_plugin_agents(plugin_dir: str = "plugins"):
    """Load agents from plugin directory"""
    plugin_path = Path(plugin_dir)
    
    for plugin_file in plugin_path.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue
            
        module_name = f"plugins.{plugin_file.stem}"
        module = importlib.import_module(module_name)
        
        # Find and register agent classes
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (inspect.isclass(attr) and 
                issubclass(attr, BaseAgent) and 
                attr != BaseAgent):
                
                agent_id = getattr(attr, "AGENT_ID", attr.__name__.lower())
                agent_registry.register(agent_id, attr)
```

## Best Practices

1. **Agent Isolation**: Each agent should have a single responsibility
2. **Configuration**: Use Pydantic models for agent configs
3. **Error Handling**: Graceful degradation when agents fail
4. **Capabilities**: Clearly define what each agent can do
5. **Testing**: Mock LLM calls in agent tests
6. **Documentation**: Each agent should have clear docs on inputs/outputs