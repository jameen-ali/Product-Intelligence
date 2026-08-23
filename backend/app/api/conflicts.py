import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Product
from app.conflict.engine import detect_conflicts_for_product

router = APIRouter(prefix="/conflicts", tags=["Conflicts"])


@router.get("/status")
def conflicts_status():
    return {"status": "ready"}


@router.get("/products/{product_id}")
def get_product_conflicts(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return all detected CONFLICT attributes for a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    conflicts = detect_conflicts_for_product(product_id, db)
    return {
        "product_id": str(product_id),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
    }

