"""
Qdrant evidence indexing and retrieval service.
Collection: product_evidence
"""
import logging
import uuid
from typing import Optional

from app.core.qdrant_client import qdrant_wrapper, COLLECTION_NAME

logger = logging.getLogger(__name__)


def _get_client():
    if not qdrant_wrapper.client:
        qdrant_wrapper.connect()
    if qdrant_wrapper.client:
        qdrant_wrapper.ensure_collection()
    return qdrant_wrapper.client


def upsert_evidence(
    evidence_id: str,
    embedding: list[float],
    product_id: str,
    document_id: str,
    source_id: str,
    claim_id: str,
    page: int,
    attribute: str,
    text_snippet: str,
) -> bool:
    """
    Upsert an evidence record into the product_evidence Qdrant collection.
    """
    client = _get_client()
    if not client:
        logger.error("Qdrant client not available for upsert_evidence")
        return False

    try:
        from qdrant_client.http import models as qmodels

        # Use deterministic int ID from UUID
        point_id = str(uuid.UUID(evidence_id).int % (2**63))
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                qmodels.PointStruct(
                    id=int(point_id),
                    vector=embedding,
                    payload={
                        "evidence_id": evidence_id,
                        "product_id": product_id,
                        "document_id": document_id,
                        "source_id": source_id,
                        "claim_id": claim_id,
                        "page": page,
                        "attribute": attribute,
                        "text_snippet": text_snippet[:500],
                    }
                )
            ]
        )
        return True
    except Exception as e:
        logger.error(f"Qdrant upsert_evidence failed: {e}")
        return False


def delete_product_vectors(product_id: str) -> bool:
    """
    Delete all vector points in Qdrant collection matching the product_id.
    """
    client = _get_client()
    if not client:
        logger.error("Qdrant client not available for delete_product_vectors")
        return False

    try:
        from qdrant_client.http import models as qmodels
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="product_id",
                            match=qmodels.MatchValue(value=str(product_id))
                        )
                    ]
                )
            )
        )
        logger.info(f"Qdrant vectors deleted for product_id {product_id}")
        return True
    except Exception as e:
        logger.error(f"Qdrant delete_product_vectors failed: {e}")
        return False


def search_evidence(
    product_id: str,
    query_embedding: list[float],
    attribute: Optional[str] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Search for evidence semantically, filtered by product_id (and optionally attribute).
    Returns ranked list of evidence dicts with metadata.
    """
    client = _get_client()
    if not client:
        logger.error("Qdrant client not available for search_evidence")
        return []

    try:
        from qdrant_client.http import models as qmodels

        must_conditions = [
            qmodels.FieldCondition(
                key="product_id",
                match=qmodels.MatchValue(value=product_id)
            )
        ]
        if attribute:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="attribute",
                    match=qmodels.MatchValue(value=attribute)
                )
            )

        try:
            res_raw = client.http.points_api.search_points(
                collection_name=COLLECTION_NAME,
                search_request=qmodels.SearchRequest(
                    vector=query_embedding,
                    filter=qmodels.Filter(must=must_conditions),
                    limit=top_k,
                    with_payload=True,
                )
            )
            results = res_raw.result
        except Exception:
            res_points, _ = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=qmodels.Filter(must=must_conditions),
                limit=top_k,
                with_payload=True,
            )
            results = res_points

        return [
            {
                "score": getattr(r, "score", 1.0),
                "evidence_id": r.payload.get("evidence_id") if r.payload else None,
                "claim_id": r.payload.get("claim_id") if r.payload else None,
                "product_id": r.payload.get("product_id") if r.payload else None,
                "document_id": r.payload.get("document_id") if r.payload else None,
                "source_id": r.payload.get("source_id") if r.payload else None,
                "page": r.payload.get("page") if r.payload else None,
                "attribute": r.payload.get("attribute") if r.payload else None,
                "text_snippet": r.payload.get("text_snippet") if r.payload else None,
            }
            for r in results
        ]
    except Exception as e:
        logger.error(f"Qdrant search_evidence failed: {e}")
        return []
