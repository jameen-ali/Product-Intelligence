from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.core.db import check_postgres_connection
from app.core.neo4j_client import neo4j_client
from app.core.qdrant_client import qdrant_wrapper
from app.core.ai_provider import OllamaProvider, OpenRouterProvider
from app.schemas.domain import HealthResponse, ComponentHealth

router = APIRouter()

@router.get("/health")
async def get_health():
    commit_tag = "commit-8b3672f-v2"
    # 1. PostgreSQL
    pg_res = check_postgres_connection()
    pg_health = ComponentHealth(
        status=pg_res.get("status", "unhealthy"),
        details={"url": pg_res.get("url")},
        error=pg_res.get("error")
    )

    # 2. Neo4j
    neo_res = neo4j_client.check_health()
    neo_health = ComponentHealth(
        status=neo_res.get("status", "unhealthy"),
        details={"uri": neo_res.get("uri")},
        error=neo_res.get("error")
    )

    # 3. Qdrant
    qdrant_res = qdrant_wrapper.check_health()
    qdrant_health = ComponentHealth(
        status=qdrant_res.get("status", "unhealthy"),
        details={"url": qdrant_res.get("url"), "collection_count": qdrant_res.get("collection_count")},
        error=qdrant_res.get("error")
    )

    # 4 & 5. AI Providers (Environment-aware)
    active_provider = settings.AI_PROVIDER.lower()
    
    ollama_prov = OllamaProvider()
    ollama_res = await ollama_prov.check_health()
    
    openrouter_prov = OpenRouterProvider()
    openrouter_res = await openrouter_prov.check_health()

    if active_provider == "openrouter":
        openrouter_health = ComponentHealth(
            status=openrouter_res.get("status", "unhealthy"),
            details={"provider": "openrouter", "configured": bool(settings.OPENROUTER_API_KEY), "model": settings.OPENROUTER_MODEL},
            error=openrouter_res.get("error")
        )
        ollama_health = ComponentHealth(
            status="unconfigured",
            details={"provider": "ollama", "base_url": settings.OLLAMA_BASE_URL, "active": False},
            error="Ollama is inactive in production (AI_PROVIDER=openrouter)"
        )
        ai_ok = openrouter_health.status == "healthy"
    else:
        # Default: Ollama primary, with optional OpenRouter fallback
        ollama_health = ComponentHealth(
            status=ollama_res.get("status", "unhealthy"),
            details={"provider": "ollama", "base_url": settings.OLLAMA_BASE_URL, "active": True},
            error=ollama_res.get("error")
        )
        openrouter_health = ComponentHealth(
            status=openrouter_res.get("status", "unconfigured"),
            details={"provider": "openrouter", "configured": bool(settings.OPENROUTER_API_KEY)},
            error=openrouter_res.get("error")
        )
        # AI is healthy if Ollama is healthy OR if OpenRouter fallback is healthy
        ai_ok = (ollama_health.status == "healthy") or (bool(settings.OPENROUTER_API_KEY) and openrouter_health.status == "healthy")

    # Overall Status: Healthy if active production dependencies are healthy
    all_ok = pg_health.status == "healthy" and neo_health.status == "healthy" and qdrant_health.status == "healthy" and ai_ok
    overall_status = "healthy" if all_ok else "degraded"

    return HealthResponse(
        status=overall_status,
        application=settings.PROJECT_NAME,
        version=commit_tag,
        timestamp=datetime.now(timezone.utc),
        services={
            "postgresql": pg_health,
            "neo4j": neo_health,
            "qdrant": qdrant_health,
            "ollama": ollama_health,
            "openrouter": openrouter_health
        }
    )
