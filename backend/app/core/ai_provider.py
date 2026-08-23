from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type
import httpx
from pydantic import BaseModel

from app.core.config import settings

class AIProviderUnavailableError(Exception):
    """Raised when no AI provider is available or configured."""
    pass

class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Type[BaseModel], **kwargs) -> BaseModel:
        pass

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def vision_generate(self, image_bytes: bytes, prompt: str, schema: Optional[Type[BaseModel]] = None) -> Any:
        pass

    @abstractmethod
    async def check_health(self) -> dict:
        pass

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def check_health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    return {"status": "healthy", "provider": "ollama", "models_count": len(models)}
                return {"status": "unhealthy", "provider": "ollama", "error": f"HTTP {res.status_code}"}
        except Exception as e:
            return {"status": "unhealthy", "provider": "ollama", "error": str(e)}

    async def generate(self, prompt: str, **kwargs) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False}
            )
            res.raise_for_status()
            return res.json().get("response", "")

    async def generate_structured(self, prompt: str, schema: Type[BaseModel], **kwargs) -> BaseModel:
        raw_text = await self.generate(prompt, **kwargs)
        # Validate Pydantic model
        return schema.model_validate_json(raw_text)

    async def embed(self, text: str) -> List[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": settings.EMBEDDING_MODEL, "prompt": text}
            )
            res.raise_for_status()
            return res.json().get("embedding", [])

    async def vision_generate(self, image_bytes: bytes, prompt: str, schema: Optional[Type[BaseModel]] = None) -> Any:
        import base64
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": settings.OLLAMA_VISION_MODEL,
                    "prompt": prompt,
                    "images": [b64_img],
                    "stream": False
                }
            )
            res.raise_for_status()
            response_text = res.json().get("response", "")
            if schema:
                return schema.model_validate_json(response_text)
            return response_text

class OpenRouterProvider(AIProvider):
    def __init__(self, api_key: str = settings.OPENROUTER_API_KEY or "", model: str = settings.OPENROUTER_MODEL or "qwen/qwen-2.5-72b-instruct"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    async def check_health(self) -> dict:
        if not self.api_key:
            return {"status": "unconfigured", "provider": "openrouter", "error": "API key not set"}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                if res.status_code == 200:
                    return {"status": "healthy", "provider": "openrouter"}
                return {"status": "unhealthy", "provider": "openrouter", "error": f"HTTP {res.status_code}"}
        except Exception as e:
            return {"status": "unhealthy", "provider": "openrouter", "error": str(e)}

    async def generate(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            raise AIProviderUnavailableError("OpenRouter API key is missing")
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]

    async def generate_structured(self, prompt: str, schema: Type[BaseModel], **kwargs) -> BaseModel:
        raw_text = await self.generate(prompt, **kwargs)
        return schema.model_validate_json(raw_text)

    async def embed(self, text: str) -> List[float]:
        raise NotImplementedError("Embeddings via OpenRouter fallback not configured")

    async def vision_generate(self, image_bytes: bytes, prompt: str, schema: Optional[Type[BaseModel]] = None) -> Any:
        raise NotImplementedError("Vision via OpenRouter fallback not configured")
