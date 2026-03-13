"""End-to-end tests for domain-aware routing (without live services).

These tests verify the complete domain routing pipeline using mocks,
suitable for CI environments where Ollama and cloud providers are not available.
"""

import asyncio

from mascarade.router.domain_detector import DomainDetector
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router, Strategy


class MockOllamaProvider(LLMProvider):
    """Mock Ollama provider with mascarade-* models."""

    def __init__(self):
        self.name = "ollama"
        self.default_model = "qwen3.5:9b"
        self.cost_per_million = (0.0, 0.0)
        self.speed_rank = 1
        self.quality_rank = 2
        self.models_available = [
            "mascarade-kicad",
            "mascarade-spice",
            "mascarade-freecad",
            "mascarade-iot",
        ]
        self.last_call = {}

    async def send(self, messages, **kwargs):
        model = kwargs.get("model") or self.default_model
        self.last_call = {"messages": messages, "model": model, "kwargs": kwargs}
        return LLMResponse(
            content=f"Ollama response from {model}",
            model=model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream(self, messages, **kwargs):
        model = kwargs.get("model", self.default_model)
        yield f"token from {model}"

    def available_models(self):
        return self.models_available

    def is_model_available(self, model_name: str) -> bool:
        return model_name in self.models_available


class MockClaudeProvider(LLMProvider):
    """Mock Claude provider for fallback testing."""

    name = "claude"
    default_model = "claude-3.5-sonnet"
    cost_per_million = (5.0, 10.0)
    speed_rank = 2
    quality_rank = 3  # Higher quality for fallback

    async def send(self, messages, **kwargs):
        return LLMResponse(
            content="Claude response",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream(self, messages, **kwargs):
        yield "claude token"

    def available_models(self):
        return [self.default_model]


def test_e2e_kicad_query_routes_to_mascarade_kicad():
    """E2E: KiCad query routes to mascarade-kicad model via Ollama."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    claude = MockClaudeProvider()
    router.register(ollama)
    router.register(claude)

    detector = DomainDetector()

    # User query
    query = "How do I create a footprint in KiCad for a custom connector?"

    # Detect domain
    domain = detector.detect_domain(query)
    assert domain == "kicad"

    # Get model for domain
    model = detector.get_model_for_domain(domain)
    assert model == "mascarade-kicad"

    # Route query
    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
            max_tokens=100,
        )
    )

    # Verify routing
    assert response.provider == "ollama"
    assert response.model == "mascarade-kicad"
    assert "Ollama response from mascarade-kicad" in response.content


def test_e2e_spice_query_routes_to_mascarade_spice():
    """E2E: SPICE query routes to mascarade-spice model via Ollama."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    claude = MockClaudeProvider()
    router.register(ollama)
    router.register(claude)

    detector = DomainDetector()

    query = "Analyze this SPICE netlist for a low-pass filter circuit"
    domain = detector.detect_domain(query)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
        )
    )

    assert domain == "spice"
    assert model == "mascarade-spice"
    assert response.provider == "ollama"
    assert response.model == "mascarade-spice"


def test_e2e_freecad_query_routes_to_mascarade_freecad():
    """E2E: FreeCAD query routes to mascarade-freecad model via Ollama."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    claude = MockClaudeProvider()
    router.register(ollama)
    router.register(claude)

    detector = DomainDetector()

    query = "Create a parametric 3D model of a mounting bracket in FreeCAD"
    domain = detector.detect_domain(query)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
        )
    )

    assert domain == "freecad"
    assert model == "mascarade-freecad"
    assert response.provider == "ollama"
    assert response.model == "mascarade-freecad"


def test_e2e_stm32_query_routes_to_mascarade_iot():
    """E2E: STM32 query routes to mascarade-iot model via Ollama."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    claude = MockClaudeProvider()
    router.register(ollama)
    router.register(claude)

    detector = DomainDetector()

    query = "Configure STM32 UART with DMA using HAL library"
    domain = detector.detect_domain(query)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
        )
    )

    assert domain == "stm32"
    assert model == "mascarade-iot"
    assert response.provider == "ollama"
    assert response.model == "mascarade-iot"


def test_e2e_iot_query_routes_to_mascarade_iot():
    """E2E: IoT query routes to mascarade-iot model via Ollama."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    claude = MockClaudeProvider()
    router.register(ollama)
    router.register(claude)

    detector = DomainDetector()

    query = "Set up MQTT communication on ESP32 with TLS encryption"
    domain = detector.detect_domain(query)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
        )
    )

    assert domain == "iot"
    assert model == "mascarade-iot"
    assert response.provider == "ollama"
    assert response.model == "mascarade-iot"


def test_e2e_fallback_when_ollama_unavailable():
    """E2E: Falls back to Claude when Ollama is not available."""
    router = Router()
    router._providers.clear()

    # Only register Claude (no Ollama)
    claude = MockClaudeProvider()
    router.register(claude)

    detector = DomainDetector()

    query = "Design a PCB in KiCad with differential pairs"
    domain = detector.detect_domain(query)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
            model=model,
        )
    )

    # Should fallback to BEST strategy (Claude)
    assert domain == "kicad"
    assert response.provider == "claude"


def test_e2e_multiple_domains_in_sequence():
    """E2E: Handle multiple domain queries in sequence."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    router.register(ollama)

    detector = DomainDetector()

    queries_and_expected = [
        ("KiCad PCB routing", "kicad", "mascarade-kicad"),
        ("SPICE simulation", "spice", "mascarade-spice"),
        ("FreeCAD parametric design", "freecad", "mascarade-freecad"),
        ("STM32 GPIO configuration", "stm32", "mascarade-iot"),
        ("ESP32 MQTT setup", "iot", "mascarade-iot"),
    ]

    for query, expected_domain, expected_model in queries_and_expected:
        domain = detector.detect_domain(query)
        model = detector.get_model_for_domain(domain)

        messages = [{"role": "user", "content": query}]
        response = asyncio.run(
            router.send(
                messages,
                strategy=Strategy.DOMAIN,
                domain=domain,
                model=model,
                max_tokens=50,
            )
        )

        assert domain == expected_domain
        assert model == expected_model
        assert response.provider == "ollama"
        assert response.model == expected_model


def test_e2e_general_query_without_domain():
    """E2E: General query without specific domain uses DOMAIN strategy fallback."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    claude = MockClaudeProvider()
    router.register(ollama)
    router.register(claude)

    detector = DomainDetector()

    query = "What is the capital of France?"
    domain = detector.detect_domain(query)

    # General domain should not have a specific model
    model = detector.get_model_for_domain(domain)

    assert domain == "general"
    assert model is None

    # When domain is general, router should still work (fallback to BEST)
    messages = [{"role": "user", "content": query}]
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
        )
    )

    # Should use Ollama (available) or fallback to Claude (higher quality)
    assert response.provider in ["ollama", "claude"]


def test_e2e_domain_metadata_in_trace():
    """E2E: Verify domain metadata is passed to router for tracing."""
    router = Router()
    router._providers.clear()

    ollama = MockOllamaProvider()
    router.register(ollama)

    query = "Design a PCB in KiCad"
    messages = [{"role": "user", "content": query}]

    # Pass domain metadata explicitly
    response = asyncio.run(
        router.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain="kicad",
            model="mascarade-kicad",
        )
    )

    # Verify the call was made
    assert response.provider == "ollama"
    assert response.model == "mascarade-kicad"

    # Note: Actual Langfuse trace verification would require
    # checking the Langfuse dashboard or mock trace capture


def test_e2e_performance_under_50ms():
    """E2E: Verify domain detection performance is under 50ms."""
    import time

    detector = DomainDetector()
    query = "How do I design a complex PCB in KiCad with multiple layers and high-speed differential pairs for USB 3.0?"

    # Warm-up
    detector.detect_domain(query)

    # Measure
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        detector.detect_domain(query)
    elapsed = (time.perf_counter() - start) * 1000

    avg_time = elapsed / iterations

    # Should be much faster than 50ms (likely <1ms)
    assert avg_time < 50.0, f"Detection took {avg_time:.2f}ms (target: <50ms)"
