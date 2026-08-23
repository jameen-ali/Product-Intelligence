import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, JSON, types
from sqlalchemy.orm import relationship
import enum

from app.core.db import BaseModel


class GUID(types.TypeDecorator):
    """Cross-database UUID column: native UUID for PostgreSQL, CHAR(36) for SQLite."""
    impl = types.CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(str(value))

    @staticmethod
    def new():
        return uuid.uuid4()


class TrustStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"

class ProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Product(BaseModel):
    __tablename__ = "products"

    name = Column(String(255), nullable=False)
    manufacturer = Column(String(255), nullable=True)
    model_number = Column(String(255), nullable=True, index=True)
    sku = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    sources = relationship("Source", back_populates="product", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="product", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="product", cascade="all, delete-orphan")
    versions = relationship("ProductVersion", back_populates="product", cascade="all, delete-orphan")
    jobs = relationship("ProcessingJob", back_populates="product", cascade="all, delete-orphan")

class Source(BaseModel):
    __tablename__ = "sources"

    product_id = Column(GUID(), ForeignKey("products.id"), nullable=False)
    type = Column(String(100), nullable=False) # datasheet, website, excel, manual, image
    name = Column(String(255), nullable=False)
    url_or_path = Column(Text, nullable=True)
    authority_rank = Column(Integer, default=5)

    product = relationship("Product", back_populates="sources")
    documents = relationship("Document", back_populates="source", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="source", cascade="all, delete-orphan")

class Document(BaseModel):
    __tablename__ = "documents"

    source_id = Column(GUID(), ForeignKey("sources.id"), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_type = Column(String(50), nullable=False)
    content_length = Column(Integer, nullable=True)
    parsed_metadata = Column(JSON, nullable=True)

    source = relationship("Source", back_populates="documents")
    claims = relationship("Claim", back_populates="document", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="document", cascade="all, delete-orphan")

class Attribute(BaseModel):
    __tablename__ = "attributes"

    name = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    unit_type = Column(String(50), nullable=True) # voltage, power, pressure, etc.
    default_unit = Column(String(50), nullable=True)

    claims = relationship("Claim", back_populates="attribute")
    decisions = relationship("Decision", back_populates="attribute")

class Claim(BaseModel):
    __tablename__ = "claims"

    product_id = Column(GUID(), ForeignKey("products.id"), nullable=False)
    attribute_id = Column(GUID(), ForeignKey("attributes.id"), nullable=False)
    source_id = Column(GUID(), ForeignKey("sources.id"), nullable=False)
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=True)

    raw_value = Column(String(255), nullable=False)
    original_unit = Column(String(50), nullable=True)
    normalized_value = Column(Float, nullable=True)
    normalized_unit = Column(String(50), nullable=True)
    
    location_reference = Column(String(255), nullable=True)
    extraction_confidence = Column(Float, default=1.0)
    status = Column(String(50), default="EXTRACTED")

    product = relationship("Product", back_populates="claims")
    attribute = relationship("Attribute", back_populates="claims")
    source = relationship("Source", back_populates="claims")
    document = relationship("Document", back_populates="claims")
    evidence_items = relationship("Evidence", back_populates="claim", cascade="all, delete-orphan")

class Evidence(BaseModel):
    __tablename__ = "evidence"

    claim_id = Column(GUID(), ForeignKey("claims.id"), nullable=False)
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=True)

    text_snippet = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_header = Column(String(255), nullable=True)
    bbox = Column(JSON, nullable=True)
    content_type = Column(String(50), default="text")

    claim = relationship("Claim", back_populates="evidence_items")
    document = relationship("Document", back_populates="evidence_items")

class Decision(BaseModel):
    __tablename__ = "decisions"

    product_id = Column(GUID(), ForeignKey("products.id"), nullable=False)
    attribute_id = Column(GUID(), ForeignKey("attributes.id"), nullable=False)

    canonical_value = Column(String(255), nullable=True)
    canonical_unit = Column(String(50), nullable=True)
    trust_status = Column(String(50), default="UNKNOWN")
    confidence_score = Column(Float, default=0.0)
    decision_reason = Column(Text, nullable=True)
    contributing_claim_ids = Column(JSON, nullable=True)

    product = relationship("Product", back_populates="decisions")
    attribute = relationship("Attribute", back_populates="decisions")

class Review(BaseModel):
    __tablename__ = "reviews"

    claim_id = Column(GUID(), ForeignKey("claims.id"), nullable=True)
    decision_id = Column(GUID(), ForeignKey("decisions.id"), nullable=True)
    reviewer_id = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False) # APPROVED, REJECTED, OVERRIDDEN
    notes = Column(Text, nullable=True)
    decision_override = Column(JSON, nullable=True)

class ProductVersion(BaseModel):
    __tablename__ = "product_versions"

    product_id = Column(GUID(), ForeignKey("products.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    changelog_summary = Column(Text, nullable=True)

    product = relationship("Product", back_populates="versions")
    changes = relationship("Change", back_populates="version", cascade="all, delete-orphan")

class Change(BaseModel):
    __tablename__ = "changes"

    product_version_id = Column(GUID(), ForeignKey("product_versions.id"), nullable=False)
    attribute_id = Column(GUID(), ForeignKey("attributes.id"), nullable=False)
    
    change_type = Column(String(50), nullable=False) # ADDED, MODIFIED, REMOVED
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    impact_level = Column(String(50), default="MEDIUM")

    version = relationship("ProductVersion", back_populates="changes")

class Asset(BaseModel):
    __tablename__ = "assets"

    name = Column(String(255), nullable=False)
    asset_type = Column(String(100), nullable=False) # CATALOG_PAGE, DISTRIBUTOR_FEED, SPEC_SHEET
    uri = Column(Text, nullable=True)

class ProcessingJob(BaseModel):
    __tablename__ = "processing_jobs"

    product_id = Column(GUID(), ForeignKey("products.id"), nullable=False)
    status = Column(String(50), default="PENDING")
    current_step = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    product = relationship("Product", back_populates="jobs")

class SourceAuthorityConfig(BaseModel):
    __tablename__ = "source_authority_configs"

    source_type = Column(String(100), nullable=False, unique=True)
    rank = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
