from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Product, Source
from app.schemas.domain import ProductCreate, ProductResponse, SourceCreate, SourceResponse
from app.graph import neo4j_service as graph

router = APIRouter(prefix="/products", tags=["Products"])

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(**{
        k: v for k, v in product.model_dump().items()
        if k not in ("id", "created_at", "updated_at")
    })
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    # Create Neo4j product node
    try:
        graph.create_product_node(
            db_product.id, str(db_product.name), db_product.model_number,
            db_product.manufacturer, db_product.category
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Neo4j create_product_node warning: {e}")

    # Seed default source and initial attribute claims for instant display
    try:
        from app.services.seed_service import seed_product_initial_attributes
        db_source = Source(
            product_id=db_product.id,
            type="datasheet",
            name=f"{db_product.name} Technical Specification.pdf",
            authority_rank=1
        )
        db.add(db_source)
        db.commit()
        db.refresh(db_source)

        try:
            graph.create_source_node(db_source.id, db_product.id, str(db_source.type), str(db_source.name), int(db_source.authority_rank or 1))
        except Exception:
            pass

        seed_product_initial_attributes(db, db_product, db_source)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Initial attribute seeding warning: {e}")

    return db_product

@router.get("", response_model=List[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 1. Delete from PostgreSQL (cascades to sources, claims, decisions, evidence, jobs)
    db.delete(product)
    db.commit()

    # 2. Cleanup Neo4j graph nodes
    try:
        graph.delete_product_graph(product_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Neo4j product cleanup error for {product_id}: {e}")

    # 3. Cleanup Qdrant vector index
    try:
        from app.retrieval import qdrant_service
        qdrant_service.delete_product_vectors(str(product_id))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Qdrant product cleanup error for {product_id}: {e}")

    return {
        "success": True,
        "message": "Product deleted successfully",
        "product_id": str(product_id)
    }

@router.post("/{product_id}/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def add_source(product_id: UUID, source: SourceCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    db_source = Source(
        product_id=product_id,
        type=source.type,
        name=source.name,
        url_or_path=source.url_or_path,
        authority_rank=source.authority_rank or 5,
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)

    # Create Neo4j source node
    try:
        graph.create_source_node(
            db_source.id, product_id, source.type, source.name, int(db_source.authority_rank or 5)
        )
    except Exception:
        pass
    return db_source

@router.get("/{product_id}/sources", response_model=List[SourceResponse])
def list_sources(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.query(Source).filter(Source.product_id == product_id).all()
