import logging
from typing import Optional
from app.core.config import settings
from app.core.ai_provider import AIProvider, OllamaProvider, OpenRouterProvider, AIProviderUnavailableError

import time

logger = logging.getLogger(__name__)

class ModelGateway:
    def __init__(self):
        self.ollama_provider = OllamaProvider()
        self.openrouter_provider = OpenRouterProvider()
        self._cached_provider: Optional[AIProvider] = None
        self._cache_err: Optional[AIProviderUnavailableError] = None
        self._last_check_time: float = 0.0

    async def get_active_provider(self) -> AIProvider:
        now = time.time()
        # Return cached provider or error if within 15 seconds
        if now - self._last_check_time < 15.0:
            if self._cache_err is not None:
                raise self._cache_err
            if self._cached_provider is not None:
                return self._cached_provider

        self._last_check_time = now
        self._cached_provider = None
        self._cache_err = None

        # Check if forced via config
        if settings.AI_PROVIDER == "openrouter":
            health = await self.openrouter_provider.check_health()
            if health.get("status") == "healthy":
                self._cached_provider = self.openrouter_provider
                return self.openrouter_provider
            err = AIProviderUnavailableError("OpenRouter explicitly configured but unhealthy or missing API key.")
            self._cache_err = err
            raise err

        # Default: Ollama first
        health = await self.ollama_provider.check_health()
        if health.get("status") == "healthy":
            self._cached_provider = self.ollama_provider
            return self.ollama_provider

        # Fallback to OpenRouter
        if settings.OPENROUTER_API_KEY:
            or_health = await self.openrouter_provider.check_health()
            if or_health.get("status") == "healthy":
                logger.info("Ollama unavailable. Falling back to OpenRouter.")
                self._cached_provider = self.openrouter_provider
                return self.openrouter_provider

        err = AIProviderUnavailableError("No AI Provider is available (Ollama unreachable, OpenRouter unconfigured/unreachable).")
        self._cache_err = err
        raise err

    async def check_all_providers() -> dict:
        ollama_h = await self.ollama_provider.check_health()
        openrouter_h = await self.openrouter_provider.check_health()
        return {
            "ollama": ollama_h,
            "openrouter": openrouter_h,
            "active_provider_configured": settings.AI_PROVIDER
        }

model_gateway = ModelGateway()
