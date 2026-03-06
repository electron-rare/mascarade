from mascarade.router.providers.base import LLMProvider, LLMResponse

__all__ = ["LLMProvider", "LLMResponse"]

try:
    from mascarade.router.providers.claude import ClaudeProvider

    __all__.append("ClaudeProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.openai import OpenAIProvider

    __all__.append("OpenAIProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.mistral import MistralProvider

    __all__.append("MistralProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.bedrock import BedrockProvider

    __all__.append("BedrockProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.google import GoogleProvider

    __all__.append("GoogleProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.huggingface import HuggingFaceProvider

    __all__.append("HuggingFaceProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.ollama import OllamaProvider

    __all__.append("OllamaProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.apple_coreml import AppleCoreMLProvider

    __all__.append("AppleCoreMLProvider")
except ImportError:
    pass

try:
    from mascarade.router.providers.kicad_router import KiCadRouterProvider

    __all__.append("KiCadRouterProvider")
except ImportError:
    pass
