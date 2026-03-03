"""Tests pour le routeur LLM."""

from mascarade.router.router import Router, Strategy
from mascarade.router.providers.base import LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    def __init__(self, name: str, cost: tuple, speed: int, quality: int):
        self.name = name
        self.default_model = f"{name}-model"
        self.cost_per_million = cost
        self.speed_rank = speed
        self.quality_rank = quality

    async def send(self, messages, **kwargs):
        return LLMResponse(
            content=f"response from {self.name}",
            model=self.default_model,
            provider=self.name,
        )

    async def stream(self, messages, **kwargs):
        yield f"token from {self.name}"

    def available_models(self):
        return [self.default_model]


def _make_router() -> Router:
    r = Router()
    r._providers.clear()
    r.register(MockProvider("cheap", (1.0, 2.0), speed=2, quality=1))
    r.register(MockProvider("fast", (5.0, 10.0), speed=1, quality=2))
    r.register(MockProvider("best", (10.0, 20.0), speed=3, quality=3))
    return r


def test_available_providers():
    r = _make_router()
    assert set(r.available_providers) == {"cheap", "fast", "best"}


def test_select_cheapest():
    r = _make_router()
    provider = r._select_provider(Strategy.CHEAPEST)
    assert provider.name == "cheap"


def test_select_fastest():
    r = _make_router()
    provider = r._select_provider(Strategy.FASTEST)
    assert provider.name == "fast"


def test_select_best():
    r = _make_router()
    provider = r._select_provider(Strategy.BEST)
    assert provider.name == "best"


def test_select_specific():
    r = _make_router()
    provider = r._select_provider(Strategy.SPECIFIC, "fast")
    assert provider.name == "fast"


def test_select_specific_missing():
    r = _make_router()
    try:
        r._select_provider(Strategy.SPECIFIC, "nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


async def test_send():
    r = _make_router()
    resp = await r.send(
        [{"role": "user", "content": "hello"}],
        strategy="cheapest",
    )
    assert resp.provider == "cheap"
    assert resp.content == "response from cheap"
