import logging
import time
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.ai_provider import AIProvider, OllamaProvider, OpenRouterProvider, AIProviderUnavailableError

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
        # Return cached provider or cached error if checked within 15 seconds
        if now - self._last_check_time < 15.0:
            if self._cache_err is not None:
                raise self._cache_err
            if self._cached_provider is not None:
                return self._cached_provider

        self._last_check_time = now
        self._cached_provider = None
        self._cache_err = None

        # 1. PRODUCTION MODE: AI_PROVIDER == "openrouter"
        if settings.AI_PROVIDER == "openrouter":
            if settings.OPENROUTER_API_KEY and len(settings.OPENROUTER_API_KEY.strip()) > 0:
                self._cached_provider = self.openrouter_provider
                return self.openrouter_provider
            
            err = AIProviderUnavailableError("AI_PROVIDER is set to 'openrouter' but OPENROUTER_API_KEY is missing or empty.")
            self._cache_err = err
            raise err

        # 2. LOCAL MODE: AI_PROVIDER == "ollama"
        health = await self.ollama_provider.check_health()
        if health.get("status") == "healthy":
            self._cached_provider = self.ollama_provider
            return self.ollama_provider

        # Fallback to OpenRouter in local dev if Ollama is down and key exists
        if settings.OPENROUTER_API_KEY and len(settings.OPENROUTER_API_KEY.strip()) > 0:
            logger.info("Local Ollama unavailable; falling back to configured OpenRouter provider.")
            self._cached_provider = self.openrouter_provider
            return self.openrouter_provider

        err = AIProviderUnavailableError("No AI Provider is available (Ollama unreachable at localhost:11434, OpenRouter unconfigured).")
        self._cache_err = err
        raise err

    async def check_all_providers(self) -> Dict[str, Any]:
        """Checks status of all configured AI providers without raising exceptions."""
        ollama_h = await self.ollama_provider.check_health()
        openrouter_h = await self.openrouter_provider.check_health()
        
        active_provider_name = settings.AI_PROVIDER
        active_status = "unhealthy"
        
        if active_provider_name == "openrouter":
            active_status = openrouter_h.get("status", "unhealthy")
        elif active_provider_name == "ollama":
            active_status = ollama_h.get("status", "unhealthy")

        return {
            "active_provider": active_provider_name,
            "active_status": active_status,
            "ollama": ollama_h,
            "openrouter": openrouter_h
        }

model_gateway = ModelGateway()
