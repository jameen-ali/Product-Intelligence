"""
Embedding service — generates text embeddings via ModelGateway → OllamaProvider.
Falls back to a simple zero-vector if embedding model is unavailable.
"""
import logging
from typing import Optional

from app.core.model_gateway import model_gateway
from app.core.ai_provider import AIProviderUnavailableError

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 768  # nomic-embed-text dimension

async def embed_text(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text.
    Returns zero-vector of EMBEDDING_DIM if provider unavailable.
    """
    try:
        provider = await model_gateway.get_active_provider()
        embedding = await provider.embed(text[:2048])
        if embedding and len(embedding) > 0:
            # Pad or truncate to EMBEDDING_DIM for collection compatibility
            if len(embedding) < EMBEDDING_DIM:
                embedding = embedding + [0.0] * (EMBEDDING_DIM - len(embedding))
            elif len(embedding) > EMBEDDING_DIM:
                embedding = embedding[:EMBEDDING_DIM]
            return embedding
    except (AIProviderUnavailableError, NotImplementedError):
        logger.warning("Embedding provider unavailable; using zero-vector fallback")
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
    
    # Fallback: zero vector (evidence still stored, retrieval will rank it last)
    return [0.0] * EMBEDDING_DIM
