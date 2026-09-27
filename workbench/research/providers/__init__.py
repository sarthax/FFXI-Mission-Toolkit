"""Research provider adapters."""
from .base import LLMProvider, ProviderCapabilities, ProviderResponse
from .openwebui import OpenWebUIProvider
from .ollama import OllamaDirectProvider, OllamaProviderError
from .factory import create_provider

__all__=[
    "LLMProvider",
    "ProviderCapabilities",
    "ProviderResponse",
    "OpenWebUIProvider",
    "OllamaDirectProvider",
    "OllamaProviderError",
    "create_provider",
]
