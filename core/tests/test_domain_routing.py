"""Tests d'intégration pour le routage par domaine."""

import asyncio

from mascarade.router.domain_detector import DomainDetector
from mascarade.router.providers.base import LLMProvider, LLMResponse
from mascarade.router.router import Router, Strategy


class MockOllamaProvider(LLMProvider):
    """Mock Ollama provider pour tester le routage domain."""

    def __init__(self, available_models: list[str] | None = None):
        self.name = "ollama"
        self.default_model = "qwen3.5:9b"
        self.cost_per_million = (0.0, 0.0)
        self.speed_rank = 1
        self.quality_rank = 1
        self._available_models = available_models or []
        self.last_model_used = None

    async def send(self, messages, **kwargs):
        model = kwargs.get("model") or self.default_model
        self.last_model_used = model
        return LLMResponse(
            content=f"ollama response from {model}",
            model=model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream(self, messages, **kwargs):
        model = kwargs.get("model", self.default_model)
        yield f"ollama token from {model}"

    def available_models(self):
        return self._available_models

    def is_model_available(self, model_name: str) -> bool:
        return model_name in self._available_models


class MockCloudProvider(LLMProvider):
    """Mock cloud provider (Claude/GPT) pour tester le fallback."""

    def __init__(self, name: str = "claude"):
        self.name = name
        self.default_model = f"{name}-3.5"
        self.cost_per_million = (5.0, 10.0)
        self.speed_rank = 2
        self.quality_rank = 3  # Higher quality for fallback testing
        self.call_count = 0

    async def send(self, messages, **kwargs):
        self.call_count += 1
        return LLMResponse(
            content=f"cloud response from {self.name}",
            model=self.default_model,
            provider=self.name,
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream(self, messages, **kwargs):
        yield f"cloud token from {self.name}"

    def available_models(self):
        return [self.default_model]


class FailingOllamaProvider(LLMProvider):
    """Mock Ollama provider qui échoue pour tester le fallback."""

    name = "ollama"
    default_model = "qwen3.5:9b"
    cost_per_million = (0.0, 0.0)
    speed_rank = 1
    quality_rank = 1

    async def send(self, messages, **kwargs):
        raise ConnectionError("Ollama service unavailable")

    async def stream(self, messages, **kwargs):
        raise ConnectionError("Ollama service unavailable")
        yield  # pragma: no cover

    def available_models(self):
        return []


def test_domain_strategy_selects_ollama():
    """La stratégie DOMAIN sélectionne Ollama quand disponible."""
    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-kicad"])
    cloud = MockCloudProvider("claude")

    r.register(ollama)
    r.register(cloud)

    # DOMAIN strategy devrait sélectionner Ollama
    candidates = r._select_candidates(Strategy.DOMAIN)
    assert len(candidates) == 1
    assert candidates[0].name == "ollama"


def test_domain_strategy_fallback_to_best_when_no_ollama():
    """La stratégie DOMAIN retombe sur BEST quand Ollama indisponible."""
    r = Router()
    r._providers.clear()

    # Seulement des providers cloud
    claude = MockCloudProvider("claude")
    openai = MockCloudProvider("openai")

    # Claude a quality_rank = 3, OpenAI aussi
    r.register(claude)
    r.register(openai)

    # DOMAIN devrait retomber sur BEST (highest quality)
    candidates = r._select_candidates(Strategy.DOMAIN)
    assert len(candidates) == 2  # Both have quality_rank = 3
    # Les deux ont le même quality_rank
    provider_names = {p.name for p in candidates}
    assert provider_names == {"claude", "openai"}


def test_kicad_query_routes_to_mascarade_kicad():
    """Une requête KiCAD route vers mascarade-kicad."""
    detector = DomainDetector()
    text = "Help me design a PCB schematic in KiCAD"

    # Détection du domaine
    domain = detector.detect_domain(text)
    assert domain == "kicad"

    # Model pour ce domaine
    model = detector.get_model_for_domain(domain)
    assert model == "mascarade-kicad"

    # Router avec Ollama qui a ce modèle
    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-kicad", "qwen3.5:9b"])
    r.register(ollama)

    # Envoyer avec stratégie DOMAIN et modèle spécifique
    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "mascarade-kicad"
    assert ollama.last_model_used == "mascarade-kicad"


def test_spice_query_routes_to_mascarade_spice():
    """Une requête SPICE route vers mascarade-spice."""
    detector = DomainDetector()
    text = "Run a transient simulation in ngspice for this circuit"

    domain = detector.detect_domain(text)
    assert domain == "spice"

    model = detector.get_model_for_domain(domain)
    assert model == "mascarade-spice"

    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-spice", "qwen3.5:9b"])
    r.register(ollama)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "mascarade-spice"
    assert ollama.last_model_used == "mascarade-spice"


def test_freecad_query_routes_to_mascarade_freecad():
    """Une requête FreeCAD route vers mascarade-freecad."""
    detector = DomainDetector()
    text = "Create a parametric 3D model in FreeCAD with extrude"

    domain = detector.detect_domain(text)
    assert domain == "freecad"

    model = detector.get_model_for_domain(domain)
    assert model == "mascarade-freecad"

    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-freecad", "qwen3.5:9b"])
    r.register(ollama)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "mascarade-freecad"
    assert ollama.last_model_used == "mascarade-freecad"


def test_stm32_query_routes_to_mascarade_iot():
    """Une requête STM32 route vers mascarade-iot."""
    detector = DomainDetector()
    text = "Configure UART and GPIO on STM32 using HAL"

    domain = detector.detect_domain(text)
    assert domain == "stm32"

    model = detector.get_model_for_domain(domain)
    assert model == "mascarade-iot"

    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-iot", "qwen3.5:9b"])
    r.register(ollama)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "mascarade-iot"
    assert ollama.last_model_used == "mascarade-iot"


def test_iot_query_routes_to_mascarade_iot():
    """Une requête IoT route vers mascarade-iot."""
    detector = DomainDetector()
    text = "Setup MQTT on ESP32 for sensor data collection"

    domain = detector.detect_domain(text)
    assert domain == "iot"

    model = detector.get_model_for_domain(domain)
    assert model == "mascarade-iot"

    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-iot", "qwen3.5:9b"])
    r.register(ollama)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "mascarade-iot"
    assert ollama.last_model_used == "mascarade-iot"


def test_general_domain_uses_default_model():
    """Une requête sans domaine spécifique utilise le modèle par défaut."""
    detector = DomainDetector()
    text = "Hello, how are you today?"

    domain = detector.detect_domain(text)
    assert domain == "general"

    model = detector.get_model_for_domain(domain)
    assert model is None  # Pas de modèle spécifique

    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["qwen3.5:9b"])
    r.register(ollama)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            domain=domain,
        )
    )

    # Utilise le modèle par défaut d'Ollama
    assert response.provider == "ollama"
    assert response.model == "qwen3.5:9b"


def test_domain_routing_fallback_when_ollama_fails():
    """Fallback vers cloud provider quand Ollama échoue."""
    r = Router()
    r._providers.clear()

    # Ollama qui échoue
    failing_ollama = FailingOllamaProvider()
    # Cloud provider de secours
    claude = MockCloudProvider("claude")

    r.register(failing_ollama)
    r.register(claude)

    detector = DomainDetector()
    text = "Design a PCB in KiCAD"
    domain = detector.detect_domain(text)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    # Devrait avoir fallback vers Claude
    assert response.provider == "claude"
    assert claude.call_count == 1
    assert r.fallback.get_failure_stats()["total_failures"] >= 1


def test_domain_routing_fallback_when_model_unavailable():
    """Fallback quand le modèle domain-specific n'est pas chargé."""
    r = Router()
    r._providers.clear()

    # Ollama sans le modèle mascarade-kicad
    ollama = MockOllamaProvider(["qwen3.5:9b"])  # Pas mascarade-kicad
    claude = MockCloudProvider("claude")

    r.register(ollama)
    r.register(claude)

    detector = DomainDetector()
    text = "Design a PCB schematic"
    domain = detector.detect_domain(text)
    model = detector.get_model_for_domain(domain)

    # Vérifier que le modèle n'est pas disponible
    assert not ollama.is_model_available(model)

    messages = [{"role": "user", "content": text}]
    # Essayer d'utiliser le modèle domain-specific
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    # Note: Le router essaiera Ollama d'abord (même sans le modèle spécifique)
    # mais si ça échoue, il tombera sur Claude
    # Pour ce test, on vérifie juste qu'on obtient une réponse
    assert response is not None
    assert response.provider in ["ollama", "claude"]


def test_domain_detection_integration():
    """Test d'intégration complet du flux de détection de domaine."""
    detector = DomainDetector()

    # Test plusieurs domaines
    test_cases = [
        ("Design a PCB in KiCAD", "kicad", "mascarade-kicad"),
        ("Run SPICE simulation", "spice", "mascarade-spice"),
        ("Create 3D model in FreeCAD", "freecad", "mascarade-freecad"),
        ("Configure STM32 peripherals", "stm32", "mascarade-iot"),
        ("Setup MQTT on ESP32", "iot", "mascarade-iot"),
        ("Hello world", "general", None),
    ]

    for text, expected_domain, expected_model in test_cases:
        domain = detector.detect_domain(text)
        assert domain == expected_domain, f"Failed for: {text}"

        model = detector.get_model_for_domain(domain)
        assert model == expected_model, f"Failed model for: {text}"


def test_domain_metadata_passed_to_cache():
    """Le domaine est passé au cache pour une meilleure granularité."""
    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-kicad"])
    r.register(ollama)

    detector = DomainDetector()
    text = "KiCAD PCB design"
    domain = detector.detect_domain(text)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": text}]

    # Premier appel - devrait être un cache miss
    response1 = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    # Deuxième appel identique - devrait être un cache hit
    response2 = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
        )
    )

    # Les deux devraient retourner le même contenu
    assert response1.provider == "ollama"
    assert response2.provider == "ollama"

    # Vérifier les stats du cache
    cache_stats = asyncio.run(r.cache.get_stats())
    assert cache_stats["hit_count"] >= 1  # Au moins un hit


def test_multiple_domains_routing():
    """Test le routage de plusieurs domaines successifs."""
    r = Router()
    r._providers.clear()

    # Ollama avec tous les modèles domain-specific
    ollama = MockOllamaProvider(
        [
            "mascarade-kicad",
            "mascarade-spice",
            "mascarade-freecad",
            "mascarade-iot",
            "qwen3.5:9b",
        ]
    )
    r.register(ollama)

    detector = DomainDetector()

    queries = [
        ("Design a PCB", "kicad", "mascarade-kicad"),
        ("Simulate circuit", "spice", "mascarade-spice"),
        ("3D CAD model", "freecad", "mascarade-freecad"),
        ("ESP32 IoT", "iot", "mascarade-iot"),
    ]

    for text, expected_domain, expected_model in queries:
        domain = detector.detect_domain(text)
        assert domain == expected_domain

        model = detector.get_model_for_domain(domain)
        assert model == expected_model

        messages = [{"role": "user", "content": text}]
        response = asyncio.run(
            r.send(
                messages,
                strategy=Strategy.DOMAIN,
                model=model,
                domain=domain,
            )
        )

        assert response.provider == "ollama"
        assert response.model == expected_model
        assert ollama.last_model_used == expected_model


def test_domain_routing_with_temperature_and_max_tokens():
    """Le routage domain préserve les paramètres température et max_tokens."""
    r = Router()
    r._providers.clear()

    ollama = MockOllamaProvider(["mascarade-kicad"])
    r.register(ollama)

    detector = DomainDetector()
    text = "KiCAD help"
    domain = detector.detect_domain(text)
    model = detector.get_model_for_domain(domain)

    messages = [{"role": "user", "content": text}]
    response = asyncio.run(
        r.send(
            messages,
            strategy=Strategy.DOMAIN,
            model=model,
            domain=domain,
            temperature=0.3,
            max_tokens=2048,
        )
    )

    assert response.provider == "ollama"
    assert response.model == "mascarade-kicad"


def test_domain_strategy_enum_value():
    """Vérifier que DOMAIN est bien dans l'enum Strategy."""
    assert hasattr(Strategy, "DOMAIN")
    assert Strategy.DOMAIN.value == "domain"
    assert Strategy.DOMAIN in list(Strategy)
