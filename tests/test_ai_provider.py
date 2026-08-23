import pytest
from unittest.mock import patch, AsyncMock
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.ai_provider import (
    AIProviderUnavailableError,
    OllamaProvider,
    OpenRouterProvider,
    extract_json_from_response,
)
from app.core.model_gateway import model_gateway

class DummySchema(BaseModel):
    name: str
    value: str

def test_extract_json_from_response():
    # 1. Plain JSON string
    text1 = '{"name": "rated_power", "value": "75 kW"}'
    parsed1 = extract_json_from_response(text1)
    assert parsed1 == {"name": "rated_power", "value": "75 kW"}

    # 2. Markdown fenced JSON block
    text2 = 'Here is the extracted JSON:\n```json\n{\n  "name": "voltage",\n  "value": "415 V"\n}\n```'
    parsed2 = extract_json_from_response(text2)
    assert parsed2 == {"name": "voltage", "value": "415 V"}

    # 3. Substring embedded JSON
    text3 = 'Sure, here is the result: {"name": "speed", "value": "1450 RPM"} Thanks!'
    parsed3 = extract_json_from_response(text3)
    assert parsed3 == {"name": "speed", "value": "1450 RPM"}

@pytest.mark.asyncio
async def test_openrouter_provider_unconfigured():
    provider = OpenRouterProvider(api_key="")
    health = await provider.check_health()
    assert health["status"] == "unconfigured"
    assert health["active"] is False

    with pytest.raises(AIProviderUnavailableError):
        await provider.generate("Test prompt")

@pytest.mark.asyncio
async def test_openrouter_provider_fallback():
    provider = OpenRouterProvider(
        api_key="test_key",
        model="primary_failing_model",
        fallback_model="secondary_working_model",
        base_url="https://openrouter.ai/api/v1"
    )

    call_count = 0

    async def mock_call(model, prompt, system_prompt=None):
        nonlocal call_count
        call_count += 1
        if model == "primary_failing_model":
            raise RuntimeError("Primary model transient error")
        return '{"name": "voltage", "value": "400 V"}'

    with patch.object(provider, "_call_completion", side_effect=mock_call):
        res_text = await provider.generate("Test prompt")
        assert res_text == '{"name": "voltage", "value": "400 V"}'
        assert call_count >= 2  # Tried primary, then fallback

@pytest.mark.asyncio
async def test_model_gateway_provider_selection():
    with patch.object(settings, "AI_PROVIDER", "openrouter"):
        with patch.object(settings, "OPENROUTER_API_KEY", "valid_key"):
            provider = await model_gateway.get_active_provider()
            assert isinstance(provider, OpenRouterProvider)

    with patch.object(settings, "AI_PROVIDER", "ollama"):
        model_gateway._last_check_time = 0.0
        with patch.object(model_gateway.ollama_provider, "check_health", return_value={"status": "healthy"}):
            provider = await model_gateway.get_active_provider()
            assert isinstance(provider, OllamaProvider)
