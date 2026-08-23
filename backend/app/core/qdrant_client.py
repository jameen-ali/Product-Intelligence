import logging
from typing import Dict, Any, Optional

try:
    from qdrant_client import QdrantClient as QClient
    from qdrant_client.http import models as qmodels
    QDRANT_AVAILABLE = True
except ImportError:
    QClient = None
    qmodels = None
    QDRANT_AVAILABLE = False

from app.core.config import settings


logger = logging.getLogger(__name__)

COLLECTION_NAME = "product_evidence"

class QdrantWrapper:
    def __init__(self):
        self.client: Optional[QClient] = None
        self._unreachable: bool = False
        self._last_fail_time: float = 0.0

    def connect(self):
        if not QDRANT_AVAILABLE:
            return
        if self.client:
            return

        import time
        now = time.time()
        if now - self._last_fail_time < 15.0:
            return

        try:
            self.client = QClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
                timeout=2.0
            )
            self.client.get_collections()
            self._unreachable = False
            logger.info(f"Connected to Qdrant at {settings.QDRANT_URL}")
        except Exception as e:
            logger.warning(f"Qdrant offline at {settings.QDRANT_URL}: {e}")
            self.client = None
            self._unreachable = True
            self._last_fail_time = now

    def check_health(self) -> Dict[str, Any]:
        if not QDRANT_AVAILABLE:
            return {"status": "unhealthy", "error": "qdrant-client package not installed"}
        try:
            if not self.client:
                self.connect()
            if not self.client:
                return {"status": "unhealthy", "error": "Qdrant client not initialized"}
            
            collections = self.client.get_collections()
            return {
                "status": "healthy",
                "url": settings.QDRANT_URL,
                "collection_count": len(collections.collections)
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def ensure_collection(self, vector_size: int = 768):
        """Creates product_evidence collection if it does not exist."""
        if not QDRANT_AVAILABLE:
            return
        if not self.client:
            self.connect()
        if not self.client:
            return
        
        try:
            collections = self.client.get_collections()
            existing_names = [c.name for c in collections.collections]
            if COLLECTION_NAME not in existing_names:
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=qmodels.VectorParams(
                        size=vector_size,
                        distance=qmodels.Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection '{COLLECTION_NAME}'")
        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection: {e}")


qdrant_wrapper = QdrantWrapper()
