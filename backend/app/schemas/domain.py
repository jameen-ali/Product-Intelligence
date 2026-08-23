from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# Health Schema
class ComponentHealth(BaseModel):
    status: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    application: str
    timestamp: datetime
    services: Dict[str, ComponentHealth]

# Product Schemas
class ProductBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    name: str
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

# Source Schemas
class SourceCreate(BaseModel):
    product_id: Optional[UUID] = None
    type: str
    name: str
    url_or_path: Optional[str] = None
    authority_rank: Optional[int] = 5

class SourceResponse(SourceCreate):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Claim Schemas
class ClaimResponse(BaseModel):
    id: UUID
    product_id: UUID
    attribute_id: UUID
    source_id: UUID
    raw_value: str
    original_unit: Optional[str] = None
    normalized_value: Optional[float] = None
    normalized_unit: Optional[str] = None
    extraction_confidence: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Evidence Schemas
class EvidenceResponse(BaseModel):
    id: UUID
    claim_id: UUID
    text_snippet: str
    page_number: Optional[int] = None
    section_header: Optional[str] = None
    content_type: str

    model_config = ConfigDict(from_attributes=True)

# Decision Schemas
class DecisionResponse(BaseModel):
    id: UUID
    product_id: UUID
    attribute_id: UUID
    canonical_value: Optional[str] = None
    canonical_unit: Optional[str] = None
    trust_status: str
    confidence_score: float
    decision_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

