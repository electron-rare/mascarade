"""Tests end-to-end pour le routage domain-aware du router."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from mascarade.router.model_registry import ModelRegistry
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router


class MockOllamaProvider(LLMProvider):
    """Mock provider pour les tests."""

    def __init__(self, name: str = "ollama"):
        self.name = name
        self.default_model = "test-model"
        self.cost_per_million = (0.0, 0.0)
        self.speed_rank = 1
        self.quality_rank = 1

    @property
    def is_configured(self) -> bool:
        return True

    def available_models(self) -> list[str]:
        return ["test-model"]

    async def send(self, messages, **kwargs) -> LLMResponse:
        return LLMResponse(
            content="mock response",
            model="test-model",
            provider=self.name,
            usage={"total_tokens": 10},
        )

    async def stream(self, messages, **kwargs):
        yield "mock"


def test_router_domain_filtering():
    """Vérifier que le router filtre les providers par domaine."""
    # Create a temporary registry for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_models.json"

        # Create router with custom registry path
        router = Router()
        router.model_registry = ModelRegistry(storage_path=registry_path)

        # Register a test fine-tuned model with domain metadata
        router.register_finetuned_model(
            "test-stm32-model:latest",
            domain="stm32",
            provider="ollama",
            deployment_url=None,  # Skip health check
            verify_health=False,
        )

        # Verify model was registered
        models = router.model_registry.get_models()
        assert len(models) == 1
        assert models[0].model_id == "test-stm32-model:latest"
        assert models[0].domain == "stm32"
        assert models[0].provider == "ollama"

        # Mark model as healthy (simulate successful deployment)
        router.model_registry.register_model(
            "test-stm32-model:latest",
            {"health_status": "healthy"}
        )

        # Verify health status updated
        updated_models = router.model_registry.get_models()
        assert updated_models[0].health_status == "healthy"


def test_router_lists_domain_models():
    """Vérifier que le router peut lister les modèles par domaine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_models.json"

        router = Router()
        router.model_registry = ModelRegistry(storage_path=registry_path)

        # Register multiple models with different domains
        router.register_finetuned_model(
            "model-stm32:v1",
            domain="stm32",
            provider="ollama",
            verify_health=False,
        )
        router.register_finetuned_model(
            "model-spice:v1",
            domain="spice",
            provider="ollama",
            verify_health=False,
        )
        router.register_finetuned_model(
            "model-general:v1",
            domain=None,
            provider="ollama",
            verify_health=False,
        )

        # Mark stm32 and spice models as healthy
        router.model_registry.register_model(
            "model-stm32:v1",
            {"health_status": "healthy"}
        )
        router.model_registry.register_model(
            "model-spice:v1",
            {"health_status": "healthy"}
        )

        # Get all models
        all_models = router.model_registry.get_models()
        assert len(all_models) == 3

        # Filter by domain
        stm32_models = [m for m in all_models if m.domain == "stm32" and m.health_status == "healthy"]
        assert len(stm32_models) == 1
        assert stm32_models[0].model_id == "model-stm32:v1"

        spice_models = [m for m in all_models if m.domain == "spice" and m.health_status == "healthy"]
        assert len(spice_models) == 1
        assert spice_models[0].model_id == "model-spice:v1"


def test_router_domain_provider_filtering():
    """Vérifier que _select_candidates filtre les providers par domaine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_models.json"

        router = Router()
        router.model_registry = ModelRegistry(storage_path=registry_path)

        # Manually register mock providers for testing
        ollama_provider = MockOllamaProvider("ollama")
        claude_provider = MockOllamaProvider("claude")

        router.register(ollama_provider)
        router.register(claude_provider)

        # Register a model with domain
        router.register_finetuned_model(
            "test-electronics:v1",
            domain="electronics",
            provider="ollama",
            verify_health=False,
        )

        # Mark as healthy
        router.model_registry.register_model(
            "test-electronics:v1",
            {"health_status": "healthy"}
        )

        # Get initial provider count (should have 2 mock providers)
        all_candidates = router._select_candidates()
        assert len(all_candidates) == 2

        # When filtering by domain, should only get ollama provider
        domain_candidates = router._select_candidates(domain="electronics")

        # Should have filtered to only providers hosting domain models
        # In this case, only ollama should remain
        assert len(domain_candidates) == 1
        assert domain_candidates[0].name == "ollama"


def test_router_domain_filtering_fallback():
    """Vérifier que le router utilise tous les providers si aucun modèle domaine n'est healthy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "test_models.json"

        router = Router()
        router.model_registry = ModelRegistry(storage_path=registry_path)

        # Manually register mock providers
        ollama_provider = MockOllamaProvider("ollama")
        claude_provider = MockOllamaProvider("claude")

        router.register(ollama_provider)
        router.register(claude_provider)

        # Register a model but mark it as unhealthy
        router.register_finetuned_model(
            "test-electronics:v1",
            domain="electronics",
            provider="ollama",
            verify_health=False,
        )

        router.model_registry.register_model(
            "test-electronics:v1",
            {"health_status": "unhealthy"}
        )

        # When no healthy domain models exist, should fall back to all providers
        domain_candidates = router._select_candidates(domain="electronics")
        assert len(domain_candidates) == 2  # Falls back to all providers
