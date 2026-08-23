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
    graph.create_product_node(
        db_product.id, db_product.name, db_product.model_number,
        db_product.manufacturer, db_product.category
    )
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
    graph.create_source_node(
        db_source.id, product_id, source.type, source.name, db_source.authority_rank
    )
    return db_source

@router.get("/{product_id}/sources", response_model=List[SourceResponse])
def list_sources(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.query(Source).filter(Source.product_id == product_id).all()
