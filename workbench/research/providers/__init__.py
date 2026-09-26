"""Research provider adapters."""
from .base import LLMProvider, ProviderCapabilities, ProviderResponse
from .openwebui import OpenWebUIProvider

__all__=[
    "LLMProvider",
    "ProviderCapabilities",
    "ProviderResponse",
    "OpenWebUIProvider",
]
