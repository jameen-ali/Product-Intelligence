import uuid
from fastapi import APIRouter, HTTPException
from app.graph.neo4j_service import get_product_graph

router = APIRouter(prefix="/products", tags=["Graph"])

@router.get("/{product_id}/graph")
def get_graph(product_id: uuid.UUID):
    """Return the Product Truth Graph for visualisation."""
    result = get_product_graph(product_id)
    if "error" in result and not result["nodes"]:
        raise HTTPException(status_code=503, detail=f"Graph unavailable: {result['error']}")
    return {"product_id": str(product_id), **result}
