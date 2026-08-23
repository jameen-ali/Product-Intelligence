from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, Dict
import re
import json
import logging
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)

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

def extract_json_from_response(text: str) -> Optional[Any]:
    """Helper to extract JSON object or array from LLM response text."""
    if not text:
        return None
    cleaned = text.strip()
    
    # Check for markdown code blocks
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if code_block_match:
        cleaned = code_block_match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract first {...} or [...] substring
    obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if obj_match:
        try:
            return json.loads(obj_match.group(1))
        except json.JSONDecodeError:
            pass

    return None

class OllamaProvider(AIProvider):
    """Local development AI Provider using Ollama at localhost:11434."""
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, model: str = settings.OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def check_health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    return {"status": "healthy", "provider": "ollama", "models_count": len(models), "active": True}
                return {"status": "unhealthy", "provider": "ollama", "error": f"HTTP {res.status_code}", "active": False}
        except Exception as e:
            return {"status": "unhealthy", "provider": "ollama", "error": str(e), "active": False}

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
        parsed = extract_json_from_response(raw_text)
        if parsed is not None:
            if isinstance(parsed, dict):
                return schema.model_validate(parsed)
            elif isinstance(parsed, str):
                return schema.model_validate_json(parsed)
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
                parsed = extract_json_from_response(response_text)
                if parsed and isinstance(parsed, dict):
                    return schema.model_validate(parsed)
                return schema.model_validate_json(response_text)
            return response_text

class OpenRouterProvider(AIProvider):
    """Production hosted open-source AI Provider using OpenRouter API."""
    def __init__(
        self,
        api_key: str = settings.OPENROUTER_API_KEY or "",
        model: str = settings.OPENROUTER_MODEL,
        fallback_model: str = settings.OPENROUTER_FALLBACK_MODEL,
        base_url: str = settings.OPENROUTER_BASE_URL,
        vision_model: Optional[str] = settings.OPENROUTER_VISION_MODEL
    ):
        self.api_key = api_key.strip()
        self.model = model
        self.fallback_model = fallback_model
        self.base_url = base_url.rstrip("/")
        self.vision_model = vision_model

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://product-intelligence-e2wa-eight.vercel.app",
            "X-Title": "Industrial Product Truth Engine"
        }

    async def check_health(self) -> dict:
        if not self.api_key:
            return {
                "status": "unconfigured",
                "provider": "openrouter",
                "active": False,
                "error": "OPENROUTER_API_KEY is missing or empty"
            }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(
                    f"{self.base_url}/models",
                    headers=self._get_headers()
                )
                if res.status_code in (200, 401, 402):  # 200 = OK, 401/402 = Key valid format but account needs balance
                    return {
                        "status": "healthy" if res.status_code == 200 else "unconfigured",
                        "provider": "openrouter",
                        "active": True if res.status_code == 200 else False,
                        "model": self.model,
                        "fallback_model": self.fallback_model,
                        "error": None if res.status_code == 200 else f"OpenRouter API returned HTTP {res.status_code}"
                    }
                return {
                    "status": "unhealthy",
                    "provider": "openrouter",
                    "active": False,
                    "error": f"OpenRouter returned HTTP {res.status_code}"
                }
        except Exception as e:
            return {"status": "unhealthy", "provider": "openrouter", "active": False, "error": str(e)}

    async def _call_completion(self, target_model: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.1
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload
            )
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]

    async def generate(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            raise AIProviderUnavailableError("OPENROUTER_API_KEY is not configured")

        last_error = None
        # 1. Try primary model with 1 retry
        for attempt in range(2):
            try:
                logger.info(f"OpenRouter prompt call using primary model '{self.model}' (attempt {attempt+1})")
                return await self._call_completion(self.model, prompt)
            except Exception as err:
                last_error = err
                logger.warning(f"Primary model '{self.model}' attempt {attempt+1} failed: {err}")

        # 2. Try fallback model if specified
        if self.fallback_model and self.fallback_model != self.model:
            try:
                logger.info(f"Primary model failed. Trying fallback OpenRouter model '{self.fallback_model}'")
                return await self._call_completion(self.fallback_model, prompt)
            except Exception as err:
                logger.error(f"Fallback OpenRouter model '{self.fallback_model}' failed: {err}")
                last_error = err

        raise AIProviderUnavailableError(f"OpenRouter generation failed on primary and fallback models: {last_error}")

    async def generate_structured(self, prompt: str, schema: Type[BaseModel], **kwargs) -> BaseModel:
        system_instr = "You are a precise technical data extraction system. You MUST output ONLY valid JSON matching the requested schema."
        full_prompt = f"{prompt}\n\nReturn JSON ONLY:"
        
        raw_text = await self.generate(full_prompt, **kwargs)
        parsed = extract_json_from_response(raw_text)

        if parsed is not None:
            try:
                if isinstance(parsed, dict):
                    return schema.model_validate(parsed)
                elif isinstance(parsed, str):
                    return schema.model_validate_json(parsed)
            except ValidationError as ve:
                logger.warning(f"Structured JSON validation error: {ve}")

        # Retry once with strict correction prompt
        correction_prompt = f"The previous response was invalid. Please return ONLY a valid JSON object matching the required schema.\n\nOriginal Text:\n{prompt[:1500]}"
        raw_text_2 = await self.generate(correction_prompt, **kwargs)
        parsed_2 = extract_json_from_response(raw_text_2)

        if parsed_2 is not None:
            if isinstance(parsed_2, dict):
                return schema.model_validate(parsed_2)
            elif isinstance(parsed_2, str):
                return schema.model_validate_json(parsed_2)

        return schema.model_validate_json(raw_text_2)

    async def embed(self, text: str) -> List[float]:
        """
        Generates 768-dim deterministic vector embedding for Qdrant vector indexing
        when running hosted OpenRouter.
        """
        import hashlib
        import math

        EMBEDDING_DIM = 768
        clean_text = text.strip().lower()
        if not clean_text:
            return [0.0] * EMBEDDING_DIM

        # Generate a deterministic pseudo-random float vector from text hash
        words = clean_text.split()
        vec = [0.0] * EMBEDDING_DIM
        
        for idx, word in enumerate(words):
            word_hash = hashlib.sha256(f"{idx}:{word}".encode("utf-8")).digest()
            for dim_idx in range(EMBEDDING_DIM):
                byte_val = word_hash[dim_idx % len(word_hash)]
                val = (byte_val / 127.5) - 1.0
                vec[dim_idx] += val

        # L2 Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    async def vision_generate(self, image_bytes: bytes, prompt: str, schema: Optional[Type[BaseModel]] = None) -> Any:
        import base64
        if not self.vision_model or not self.api_key:
            raise NotImplementedError("OpenRouter vision model not configured; use PaddleOCR fallback")

        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{b64_img}"

        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}}
                    ]
                }
            ]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload
            )
            res.raise_for_status()
            text_resp = res.json()["choices"][0]["message"]["content"]
            if schema:
                parsed = extract_json_from_response(text_resp)
                if parsed and isinstance(parsed, dict):
                    return schema.model_validate(parsed)
                return schema.model_validate_json(text_resp)
            return text_resp
