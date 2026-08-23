"""
Core pipeline orchestration service for Segment 2 vertical slice.
Runs: PDF parse → claim extraction → normalization → PostgreSQL persist → Qdrant index → Neo4j graph
"""
import logging
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.ingestion.pdf_ingest import parse_pdf
from app.ingestion.hashing import sha256_file
from app.extraction.claim_extractor import (
    extract_product_identity, extract_attributes_from_block, ATTRIBUTE_UNIT_TYPE
)
from app.normalization.units import normalise_to_canonical
from app.retrieval.embedding_service import embed_text
from app.retrieval.qdrant_service import upsert_evidence
from app.graph import neo4j_service as graph
from app.models.entities import (
    Product, Source, Document, Attribute, Claim, Evidence, ProcessingJob
)

logger = logging.getLogger(__name__)

# Core attribute registry — seeded on first use
CORE_ATTRIBUTES = [
    {"name": "voltage", "display_name": "Rated Voltage", "unit_type": "voltage", "default_unit": "V"},
    {"name": "power", "display_name": "Rated Power", "unit_type": "power", "default_unit": "kW"},
    {"name": "pressure", "display_name": "Max Operating Pressure", "unit_type": "pressure", "default_unit": "bar"},
    {"name": "flow_rate", "display_name": "Flow Rate", "unit_type": "flow", "default_unit": "L/min"},
    {"name": "rotational_speed", "display_name": "Rotational Speed", "unit_type": "rotational_speed", "default_unit": "RPM"},
    {"name": "weight", "display_name": "Net Weight", "unit_type": "mass", "default_unit": "kg"},
    {"name": "length", "display_name": "Length", "unit_type": "length", "default_unit": "mm"},
    {"name": "width", "display_name": "Width", "unit_type": "length", "default_unit": "mm"},
    {"name": "height", "display_name": "Height", "unit_type": "length", "default_unit": "mm"},
    {"name": "temperature_min", "display_name": "Min Operating Temperature", "unit_type": "temperature_min", "default_unit": "°C"},
    {"name": "temperature_max", "display_name": "Max Operating Temperature", "unit_type": "temperature_max", "default_unit": "°C"},
    {"name": "current", "display_name": "Rated Current", "unit_type": "current", "default_unit": "A"},
    {"name": "frequency", "display_name": "Supply Frequency", "unit_type": None, "default_unit": "Hz"},
]

def seed_attributes(db: Session) -> dict[str, Attribute]:
    """Ensure all core attributes exist in PostgreSQL. Returns name→Attribute map."""
    attr_map = {}
    for spec in CORE_ATTRIBUTES:
        existing = db.query(Attribute).filter(Attribute.name == spec["name"]).first()
        if not existing:
            attr = Attribute(
                name=spec["name"],
                display_name=spec["display_name"],
                unit_type=spec["unit_type"],
                default_unit=spec["default_unit"],
            )
            db.add(attr)
            db.flush()
            existing = attr
        attr_map[spec["name"]] = existing
    db.commit()
    return attr_map

async def process_pdf_for_product(
    product_id: str,
    source_id: str,
    pdf_path: str,
    db: Session,
) -> dict:
    """
    Full pipeline: PDF → parse → extract → normalize → persist → index → graph.
    Returns a summary dict with counts and status.
    """
    result = {
        "status": "STARTED",
        "product_id": product_id,
        "pdf_path": pdf_path,
        "parse_error": None,
        "blocks_parsed": 0,
        "claims_extracted": 0,
        "evidence_stored": 0,
        "qdrant_indexed": 0,
        "neo4j_nodes": 0,
        "errors": [],
    }

    # --- 1. Hash & parse PDF ---
    try:
        file_hash = sha256_file(pdf_path)
    except Exception as e:
        result["status"] = "FAILED"
        result["parse_error"] = f"Cannot hash file: {e}"
        return result

    # Dedup check
    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing_doc:
        result["status"] = "DEDUPLICATED"
        result["document_id"] = str(existing_doc.id)
        logger.info(f"File already ingested (hash={file_hash}), reusing document {existing_doc.id}")
        return result

    parsed = parse_pdf(pdf_path, file_hash)
    if parsed.parse_error:
        result["status"] = "FAILED"
        result["parse_error"] = parsed.parse_error
        return result

    result["blocks_parsed"] = len(parsed.blocks)

    # --- 2. Persist Document in PostgreSQL ---
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        source_id=uuid.UUID(source_id),
        file_hash=file_hash,
        file_type="pdf",
        content_length=len(parsed.raw_text),
        parsed_metadata={
            "filename": parsed.filename,
            "page_count": parsed.page_count,
            "block_count": len(parsed.blocks),
        },
    )
    db.add(doc)
    db.flush()

    # --- 3. Create Neo4j Document + Source nodes ---
    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if source:
        graph.create_source_node(source.id, uuid.UUID(product_id), source.type, source.name, source.authority_rank or 5)
        graph.create_document_node(doc_id, uuid.UUID(source_id), parsed.filename,
                                   parsed.page_count, file_hash)

    # --- 4. Extract product identity from first ~1000 chars ---
    header_text = " ".join(b.text for b in parsed.blocks[:5] if b.text)[:1500]
    identity = await extract_product_identity(header_text)

    # Update product with extracted identity if not already set
    product = db.query(Product).filter(Product.id == uuid.UUID(product_id)).first()
    if product and identity.model_number and not product.model_number:
        product.model_number = identity.model_number
    if product and identity.manufacturer and not product.manufacturer:
        product.manufacturer = identity.manufacturer
    db.flush()

    # --- 5. Seed/get attribute map ---
    attr_map = seed_attributes(db)

    # Update Neo4j product node
    if product:
        graph.create_product_node(
            product.id, product.name, product.model_number,
            product.manufacturer, product.category
        )

    # --- 6. Extract claims block by block ---
    all_candidates = []
    for block in parsed.blocks:
        if not block.text or len(block.text) < 20:
            continue
        candidates = await extract_attributes_from_block(block.text, block.page)
        # Attach section context
        for c in candidates:
            c._section = block.section_header
        all_candidates.extend(candidates)

    logger.info(f"Total raw candidates extracted: {len(all_candidates)}")

    # --- 7. Deduplicate candidates (keep highest confidence per attribute) ---
    best: dict[str, any] = {}
    for c in all_candidates:
        key = c.attribute
        if key not in best or c.confidence > best[key].confidence:
            best[key] = c

    # --- 8. Persist Claims, Evidence, Qdrant, Neo4j ---
    for attr_name, candidate in best.items():
        attr = attr_map.get(attr_name)
        if not attr:
            continue

        # Parse numeric value
        raw_numeric = None
        try:
            import re
            nums = re.findall(r"[-+]?\d*\.?\d+", candidate.raw_value.replace(",", ""))
            if nums:
                raw_numeric = float(nums[0])
        except Exception:
            pass

        # Normalize
        norm_value = None
        norm_unit = None
        norm_status = "NOT_NUMERIC"
        if raw_numeric is not None and candidate.raw_unit:
            unit_type = ATTRIBUTE_UNIT_TYPE.get(attr_name)
            nr = normalise_to_canonical(raw_numeric, candidate.raw_unit, unit_type)
            norm_value = nr.normalized_value
            norm_unit = nr.normalized_unit
            norm_status = nr.status

        # Create Claim in PostgreSQL
        claim_id = uuid.uuid4()
        claim = Claim(
            id=claim_id,
            product_id=uuid.UUID(product_id),
            attribute_id=attr.id,
            source_id=uuid.UUID(source_id),
            document_id=doc_id,
            raw_value=candidate.raw_value,
            original_unit=candidate.raw_unit,
            normalized_value=norm_value,
            normalized_unit=norm_unit,
            location_reference=f"page {candidate.page}",
            extraction_confidence=candidate.confidence,
            status="EXTRACTED",
        )
        db.add(claim)
        db.flush()

        # Create Evidence in PostgreSQL
        ev_id = uuid.uuid4()
        ev = Evidence(
            id=ev_id,
            claim_id=claim_id,
            document_id=doc_id,
            text_snippet=candidate.evidence_text[:1000],
            page_number=candidate.page,
            section_header=getattr(candidate, "_section", None),
            content_type="text",
        )
        db.add(ev)
        db.flush()
        result["evidence_stored"] += 1
        result["claims_extracted"] += 1

        # Create Neo4j nodes
        graph.create_attribute_node(attr.id, attr.name, attr.display_name, attr.unit_type)
        graph.link_product_has_attribute(uuid.UUID(product_id), attr.id)
        graph.create_claim_node(
            claim_id, attr.id, candidate.raw_value, candidate.raw_unit,
            norm_value, norm_unit, "EXTRACTED", candidate.confidence
        )
        graph.create_evidence_node(
            ev_id, claim_id, doc_id, candidate.evidence_text[:500],
            candidate.page, getattr(candidate, "_section", None)
        )
        result["neo4j_nodes"] += 1

        # Index evidence in Qdrant
        embedding = await embed_text(candidate.evidence_text)
        qdrant_ok = upsert_evidence(
            evidence_id=str(ev_id),
            embedding=embedding,
            product_id=product_id,
            document_id=str(doc_id),
            source_id=source_id,
            claim_id=str(claim_id),
            page=candidate.page,
            attribute=attr_name,
            text_snippet=candidate.evidence_text,
        )
        if qdrant_ok:
            result["qdrant_indexed"] += 1

    db.commit()
    result["status"] = "COMPLETED"
    result["document_id"] = str(doc_id)
    logger.info(f"Processing complete: {result}")
    return result


async def process_url_for_product(
    product_id: str,
    source_id: str,
    url: str,
    db: Session,
) -> dict:
    """
    Full pipeline for URL webpage: URL → Crawl4AI fetch → parse blocks → extract claims → normalize → persist DB → index Qdrant → graph Neo4j.
    Preserves complete URL provenance (source_url, retrieved_at, title).
    """
    from app.ingestion.url_ingest import fetch_url_content
    import datetime

    result = {
        "status": "STARTED",
        "product_id": product_id,
        "source_url": url,
        "parse_error": None,
        "blocks_parsed": 0,
        "claims_extracted": 0,
        "evidence_stored": 0,
        "qdrant_indexed": 0,
        "neo4j_nodes": 0,
        "errors": [],
    }

    # 1. Validate & fetch URL via Crawl4AI / fallback
    parsed = await fetch_url_content(url)
    if parsed.parse_error:
        result["status"] = "FAILED"
        result["parse_error"] = parsed.parse_error
        return result

    file_hash = parsed.file_hash
    result["blocks_parsed"] = len(parsed.blocks)

    # 2. Check deduplication by hash
    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing_doc:
        result["status"] = "DEDUPLICATED"
        result["document_id"] = str(existing_doc.id)
        logger.info(f"URL already ingested ({url}), reusing document {existing_doc.id}")
        return result

    # 3. Create Document in PostgreSQL
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        source_id=uuid.UUID(source_id),
        file_hash=file_hash,
        file_type="webpage",
        content_length=len(parsed.raw_text),
        parsed_metadata={
            "filename": parsed.title or url,
            "title": parsed.title,
            "url": url,
            "domain": parsed.domain,
            "retrieved_at": datetime.datetime.utcnow().isoformat(),
            "block_count": len(parsed.blocks),
        },
    )
    db.add(doc)

    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if source:
        source.url_or_path = url
        source.name = parsed.title or source.name
    db.flush()

    # 4. Create Neo4j Source + Document nodes
    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if source:
        graph.create_source_node(
            source.id, uuid.UUID(product_id), source.type or "url",
            source.name or parsed.title, source.authority_rank or 3
        )
        graph.create_document_node(
            doc_id, uuid.UUID(source_id), parsed.title or url,
            1, file_hash
        )

    # 5. Extract product identity & attributes
    attr_map = seed_attributes(db)
    product = db.query(Product).filter(Product.id == uuid.UUID(product_id)).first()
    if product:
        graph.create_product_node(
            product.id, product.name, product.model_number,
            product.manufacturer, product.category
        )

    all_candidates = []
    for block in parsed.blocks:
        if not block.text or len(block.text) < 15:
            continue
        candidates = await extract_attributes_from_block(block.text, 1)
        for c in candidates:
            c._section = block.section_header or "Webpage Content"
        all_candidates.extend(candidates)

    best: dict[str, any] = {}
    for c in all_candidates:
        key = c.attribute
        if key not in best or c.confidence > best[key].confidence:
            best[key] = c

    # 6. Persist Claims, Evidence, Qdrant, Neo4j
    for attr_name, candidate in best.items():
        attr = attr_map.get(attr_name)
        if not attr:
            continue

        raw_numeric = None
        try:
            import re
            nums = re.findall(r"[-+]?\d*\.?\d+", candidate.raw_value.replace(",", ""))
            if nums:
                raw_numeric = float(nums[0])
        except Exception:
            pass

        norm_value = None
        norm_unit = None
        if raw_numeric is not None and candidate.raw_unit:
            unit_type = ATTRIBUTE_UNIT_TYPE.get(attr_name)
            nr = normalise_to_canonical(raw_numeric, candidate.raw_unit, unit_type)
            norm_value = nr.normalized_value
            norm_unit = nr.normalized_unit

        claim_id = uuid.uuid4()
        claim = Claim(
            id=claim_id,
            product_id=uuid.UUID(product_id),
            attribute_id=attr.id,
            source_id=uuid.UUID(source_id),
            document_id=doc_id,
            raw_value=candidate.raw_value,
            original_unit=candidate.raw_unit,
            normalized_value=norm_value,
            normalized_unit=norm_unit,
            location_reference=f"URL: {url}",
            extraction_confidence=candidate.confidence,
            status="EXTRACTED",
        )
        db.add(claim)
        db.flush()

        ev_id = uuid.uuid4()
        ev = Evidence(
            id=ev_id,
            claim_id=claim_id,
            document_id=doc_id,
            text_snippet=candidate.evidence_text[:1000],
            page_number=1,
            section_header=getattr(candidate, "_section", "Webpage Content"),
            content_type="webpage",
        )
        db.add(ev)
        db.flush()
        result["evidence_stored"] += 1
        result["claims_extracted"] += 1

        # Create Neo4j nodes
        graph.create_attribute_node(attr.id, attr.name, attr.display_name, attr.unit_type)
        graph.link_product_has_attribute(uuid.UUID(product_id), attr.id)
        graph.create_claim_node(
            claim_id, attr.id, candidate.raw_value, candidate.raw_unit,
            norm_value, norm_unit, "EXTRACTED", candidate.confidence
        )
        graph.create_evidence_node(
            ev_id, claim_id, doc_id, candidate.evidence_text[:500],
            1, getattr(candidate, "_section", "Webpage Content")
        )
        result["neo4j_nodes"] += 1

        # Index evidence in Qdrant with source_url
        embedding = await embed_text(candidate.evidence_text)
        qdrant_ok = upsert_evidence(
            evidence_id=str(ev_id),
            embedding=embedding,
            product_id=product_id,
            document_id=str(doc_id),
            source_id=source_id,
            claim_id=str(claim_id),
            page=1,
            attribute=attr_name,
            text_snippet=f"{candidate.evidence_text} (Source: {url})",
        )
        if qdrant_ok:
            result["qdrant_indexed"] += 1

    db.commit()
    result["status"] = "COMPLETED"
    result["document_id"] = str(doc_id)
    return result


async def process_excel_for_product(
    product_id: str,
    source_id: str,
    file_path: str,
    file_type: str,
    db: Session,
) -> dict:
    """
    Full pipeline for Excel/CSV: parse → extract cell records → normalize → persist → index → graph.
    Each cell value becomes a Claim + Evidence with sheet/row/column provenance.
    """
    from app.ingestion.excel_ingest import parse_excel
    from app.ingestion.hashing import sha256_file

    result = {
        "status": "STARTED",
        "product_id": product_id,
        "file_path": file_path,
        "parse_error": None,
        "rows_parsed": 0,
        "claims_extracted": 0,
        "evidence_stored": 0,
        "qdrant_indexed": 0,
        "neo4j_nodes": 0,
        "validation_messages": [],
        "errors": [],
    }

    # 1. Hash & dedup check
    try:
        file_hash = sha256_file(file_path)
    except Exception as e:
        result["status"] = "FAILED"
        result["parse_error"] = f"Cannot hash file: {e}"
        return result

    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing_doc:
        result["status"] = "DEDUPLICATED"
        result["document_id"] = str(existing_doc.id)
        return result

    # 2. Parse spreadsheet
    parsed = parse_excel(file_path, file_hash)
    result["validation_messages"] = parsed.validation_messages

    if parsed.parse_error:
        result["status"] = "FAILED"
        result["parse_error"] = parsed.parse_error
        return result

    result["rows_parsed"] = parsed.row_count

    # 3. Create Document in PostgreSQL
    doc_id = uuid.uuid4()
    import os
    filename = os.path.basename(file_path)
    doc = Document(
        id=doc_id,
        source_id=uuid.UUID(source_id),
        file_hash=file_hash,
        file_type=file_type,
        content_length=len(parsed.raw_text),
        parsed_metadata={
            "filename": filename,
            "file_type": file_type,
            "sheet_names": parsed.sheet_names,
            "row_count": parsed.row_count,
            "record_count": len(parsed.records),
            "validation_messages": parsed.validation_messages,
        },
    )
    db.add(doc)

    # Update source path
    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if source:
        source.url_or_path = filename
    db.flush()

    # 4. Neo4j source + document nodes
    if source:
        graph.create_source_node(source.id, uuid.UUID(product_id), source.type or "excel", source.name, source.authority_rank or 6)
        graph.create_document_node(doc_id, uuid.UUID(source_id), filename, 1, file_hash)

    # 5. Seed attributes, update product node
    attr_map = seed_attributes(db)
    product = db.query(Product).filter(Product.id == uuid.UUID(product_id)).first()
    if product:
        graph.create_product_node(product.id, product.name, product.model_number, product.manufacturer, product.category)

    # 6. Process each extracted cell record
    # Deduplicate WITHIN this document only (keep first occurrence per attribute in this file).
    # We do NOT deduplicate across sources — each source produces its own independent claims
    # so that conflict detection can compare them.
    seen_in_doc: set = set()
    best: dict[str, any] = {}
    for cell in parsed.records:
        if cell.canonical_attr not in seen_in_doc:
            seen_in_doc.add(cell.canonical_attr)
            best[cell.canonical_attr] = cell

    for attr_name, cell in best.items():
        attr = attr_map.get(attr_name)
        if not attr:
            continue

        # Normalize
        norm_value = None
        norm_unit = None
        if cell.numeric_value is not None and cell.raw_unit:
            unit_type = ATTRIBUTE_UNIT_TYPE.get(attr_name)
            nr = normalise_to_canonical(cell.numeric_value, cell.raw_unit, unit_type)
            norm_value = nr.normalized_value
            norm_unit = nr.normalized_unit

        location_ref = f"Sheet:{cell.sheet_name} Row:{cell.row_number} Col:{cell.column_name}"
        evidence_text = f"{cell.column_name}: {cell.raw_value} (Sheet: {cell.sheet_name}, Row: {cell.row_number})"

        # Create Claim
        claim_id = uuid.uuid4()
        claim = Claim(
            id=claim_id,
            product_id=uuid.UUID(product_id),
            attribute_id=attr.id,
            source_id=uuid.UUID(source_id),
            document_id=doc_id,
            raw_value=cell.raw_value,
            original_unit=cell.raw_unit,
            normalized_value=norm_value,
            normalized_unit=norm_unit,
            location_reference=location_ref,
            extraction_confidence=0.95,  # Deterministic extraction = high confidence
            status="EXTRACTED",
        )
        db.add(claim)
        db.flush()

        # Create Evidence with Excel provenance
        ev_id = uuid.uuid4()
        ev = Evidence(
            id=ev_id,
            claim_id=claim_id,
            document_id=doc_id,
            text_snippet=evidence_text[:1000],
            page_number=cell.row_number,
            section_header=cell.sheet_name,
            content_type="spreadsheet",
            bbox={
                "sheet": cell.sheet_name,
                "row": cell.row_number,
                "column": cell.column_name,
                "original_value": cell.raw_value,
            },
        )
        db.add(ev)
        db.flush()
        result["evidence_stored"] += 1
        result["claims_extracted"] += 1

        # Neo4j nodes
        graph.create_attribute_node(attr.id, attr.name, attr.display_name, attr.unit_type)
        graph.link_product_has_attribute(uuid.UUID(product_id), attr.id)
        graph.create_claim_node(claim_id, attr.id, cell.raw_value, cell.raw_unit, norm_value, norm_unit, "EXTRACTED", 0.95)
        graph.create_evidence_node(ev_id, claim_id, doc_id, evidence_text[:500], cell.row_number, cell.sheet_name)
        result["neo4j_nodes"] += 1

        # Qdrant index
        qdrant_text = f"{attr.display_name}: {cell.raw_value} (Source: {filename}, Sheet: {cell.sheet_name})"
        embedding = await embed_text(qdrant_text)
        qdrant_ok = upsert_evidence(
            evidence_id=str(ev_id),
            embedding=embedding,
            product_id=product_id,
            document_id=str(doc_id),
            source_id=source_id,
            claim_id=str(claim_id),
            page=cell.row_number,
            attribute=attr_name,
            text_snippet=qdrant_text,
        )
        if qdrant_ok:
            result["qdrant_indexed"] += 1

    db.commit()
    result["status"] = "COMPLETED"
    result["document_id"] = str(doc_id)
    logger.info(f"Excel processing complete: {result}")
    return result


async def process_image_for_product(
    product_id: str,
    source_id: str,
    file_path: str,
    db: Session,
) -> dict:
    """
    Full pipeline for image/nameplate OCR: image → PaddleOCR → extract attributes → normalize → persist → index → graph.
    OCR confidence stored separately from truth confidence in Evidence.bbox.
    """
    from app.ingestion.image_ingest import parse_image
    from app.ingestion.hashing import sha256_file

    result = {
        "status": "STARTED",
        "product_id": product_id,
        "file_path": file_path,
        "parse_error": None,
        "ocr_regions": 0,
        "claims_extracted": 0,
        "evidence_stored": 0,
        "qdrant_indexed": 0,
        "neo4j_nodes": 0,
        "errors": [],
    }

    # 1. Hash & dedup
    try:
        file_hash = sha256_file(file_path)
    except Exception as e:
        result["status"] = "FAILED"
        result["parse_error"] = f"Cannot hash file: {e}"
        return result

    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing_doc:
        result["status"] = "DEDUPLICATED"
        result["document_id"] = str(existing_doc.id)
        return result

    # 2. Run OCR
    parsed = parse_image(file_path, file_hash)

    if parsed.parse_error and not parsed.regions:
        result["status"] = "FAILED"
        result["parse_error"] = parsed.parse_error
        return result

    result["ocr_regions"] = len(parsed.regions)

    # 3. Create Document
    doc_id = uuid.uuid4()
    import os
    filename = os.path.basename(file_path)
    doc = Document(
        id=doc_id,
        source_id=uuid.UUID(source_id),
        file_hash=file_hash,
        file_type="image",
        content_length=len(parsed.raw_text),
        parsed_metadata={
            "filename": filename,
            "image_width": parsed.image_width,
            "image_height": parsed.image_height,
            "ocr_region_count": len(parsed.regions),
            "raw_text": parsed.raw_text[:2000],
        },
    )
    db.add(doc)

    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if source:
        source.url_or_path = filename
    db.flush()

    # 4. Neo4j source + document nodes
    if source:
        graph.create_source_node(source.id, uuid.UUID(product_id), source.type or "image", source.name, source.authority_rank or 4)
        graph.create_document_node(doc_id, uuid.UUID(source_id), filename, 1, file_hash)

    # 5. Seed attributes
    attr_map = seed_attributes(db)
    product = db.query(Product).filter(Product.id == uuid.UUID(product_id)).first()
    if product:
        graph.create_product_node(product.id, product.name, product.model_number, product.manufacturer, product.category)

    # 6. Process attributed OCR regions
    attributed_regions = getattr(parsed, "_attributed", [])
    if not attributed_regions:
        # Try again in case _attributed wasn't set
        from app.ingestion.image_ingest import _extract_attributes_from_ocr_text
        attributed_regions = _extract_attributes_from_ocr_text(parsed.regions)

    # Deduplicate per attribute (keep highest OCR confidence)
    best: dict[str, any] = {}
    for region in attributed_regions:
        if region.extracted_attr and (
            region.extracted_attr not in best or region.confidence > best[region.extracted_attr].confidence
        ):
            best[region.extracted_attr] = region

    for attr_name, region in best.items():
        attr = attr_map.get(attr_name)
        if not attr:
            continue

        # Normalize
        norm_value = None
        norm_unit = None
        try:
            numeric = float(region.raw_value.replace(",", "")) if region.raw_value else None
        except (ValueError, AttributeError):
            numeric = None

        if numeric is not None and region.raw_unit:
            unit_type = ATTRIBUTE_UNIT_TYPE.get(attr_name)
            nr = normalise_to_canonical(numeric, region.raw_unit, unit_type)
            norm_value = nr.normalized_value
            norm_unit = nr.normalized_unit

        location_ref = f"Image:{filename} OCR_conf:{region.confidence:.2f}"
        evidence_text = f"{region.text} (OCR confidence: {region.confidence:.0%})"

        # Create Claim
        claim_id = uuid.uuid4()
        claim = Claim(
            id=claim_id,
            product_id=uuid.UUID(product_id),
            attribute_id=attr.id,
            source_id=uuid.UUID(source_id),
            document_id=doc_id,
            raw_value=region.raw_value or region.text,
            original_unit=region.raw_unit,
            normalized_value=norm_value,
            normalized_unit=norm_unit,
            location_reference=location_ref,
            extraction_confidence=region.confidence,  # OCR confidence as extraction confidence
            status="EXTRACTED",
        )
        db.add(claim)
        db.flush()

        # Create Evidence with OCR provenance
        # bbox JSON stores both bounding box AND ocr_confidence (separate from truth confidence)
        ev_id = uuid.uuid4()
        ev = Evidence(
            id=ev_id,
            claim_id=claim_id,
            document_id=doc_id,
            text_snippet=evidence_text[:1000],
            page_number=1,
            section_header="Nameplate OCR",
            content_type="image_ocr",
            bbox={
                "bbox": region.bbox,
                "ocr_confidence": region.confidence,  # SEPARATE from truth confidence
                "detected_text": region.text,
                "filename": filename,
            },
        )
        db.add(ev)
        db.flush()
        result["evidence_stored"] += 1
        result["claims_extracted"] += 1

        # Neo4j nodes
        graph.create_attribute_node(attr.id, attr.name, attr.display_name, attr.unit_type)
        graph.link_product_has_attribute(uuid.UUID(product_id), attr.id)
        graph.create_claim_node(claim_id, attr.id, region.raw_value or region.text, region.raw_unit, norm_value, norm_unit, "EXTRACTED", region.confidence)
        graph.create_evidence_node(ev_id, claim_id, doc_id, evidence_text[:500], 1, "Nameplate OCR")
        result["neo4j_nodes"] += 1

        # Qdrant index — full OCR text + attribute context
        qdrant_text = f"{attr.display_name}: {region.raw_value} {region.raw_unit or ''} (Image: {filename}, OCR: {region.text})"
        embedding = await embed_text(qdrant_text)
        qdrant_ok = upsert_evidence(
            evidence_id=str(ev_id),
            embedding=embedding,
            product_id=product_id,
            document_id=str(doc_id),
            source_id=source_id,
            claim_id=str(claim_id),
            page=1,
            attribute=attr_name,
            text_snippet=qdrant_text,
        )
        if qdrant_ok:
            result["qdrant_indexed"] += 1

    db.commit()
    result["status"] = "COMPLETED"
    result["document_id"] = str(doc_id)
    logger.info(f"Image OCR processing complete: {result}")
    return result
