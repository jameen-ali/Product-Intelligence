"""
Idempotent Database Seed Service for Industrial Product Truth Engine.
Seeds three core demonstration products:
1. Industrial Hydraulic Pump HP-4000
2. Industrial Electric Motor EM-750 (with canonical conflict scenario)
3. Industrial Air Compressor AC-1200
"""
import logging
import uuid
from typing import Dict
from sqlalchemy.orm import Session

from app.models.entities import Product, Source, Document, Attribute, Claim, Evidence, Decision
from app.services.processing_service import seed_attributes
from app.graph import neo4j_service as graph
from app.retrieval.qdrant_service import upsert_evidence
from app.retrieval.embedding_service import embed_text

logger = logging.getLogger(__name__)

DEMO_PRODUCTS = [
    {
        "name": "Industrial Hydraulic Pump HP-4000",
        "model_number": "HP-4000",
        "manufacturer": "HydroDyn Pumps Pvt. Ltd.",
        "category": "Hydraulic Pump",
        "sources": [
            {
                "type": "datasheet",
                "name": "HP-4000 Technical Datasheet v2.pdf",
                "url_or_path": "https://hydrodyn.example.com/datasheets/HP-4000.pdf",
                "authority_rank": 1,
                "claims": [
                    {"attr": "pressure", "raw": "250 bar", "unit": "bar", "norm": 250.0, "norm_unit": "bar", "snippet": "Maximum operating pressure: 250 bar rated at 1800 RPM.", "status": "VERIFIED"},
                    {"attr": "flow_rate", "raw": "120 L/min", "unit": "L/min", "norm": 120.0, "norm_unit": "L/min", "snippet": "Nominal flow rate at maximum RPM: 120 L/min.", "status": "VERIFIED"},
                    {"attr": "rotational_speed", "raw": "1800 RPM", "unit": "RPM", "norm": 1800.0, "norm_unit": "RPM", "snippet": "Rated rotational speed: 1800 RPM continuous duty.", "status": "VERIFIED"},
                    {"attr": "weight", "raw": "45 kg", "unit": "kg", "norm": 45.0, "norm_unit": "kg", "snippet": "Net dry weight: 45 kg including mounting flange.", "status": "VERIFIED"},
                ]
            }
        ]
    },
    {
        "name": "Industrial Electric Motor EM-750",
        "model_number": "EM-750",
        "manufacturer": "Generic Industrial Motors",
        "category": "Electric Motor",
        "sources": [
            {
                "type": "datasheet",
                "name": "EM-750 Manufacturer Specification Sheet (2024)",
                "url_or_path": "https://motors.example.com/specs/EM-750-datasheet.pdf",
                "authority_rank": 1,
                "claims": [
                    {"attr": "voltage", "raw": "415 V", "unit": "V", "norm": 415.0, "norm_unit": "V", "snippet": "Supply Voltage: 415 V 3-Phase 50Hz AC motor configuration.", "status": "EXTRACTED"},
                    {"attr": "rotational_speed", "raw": "1450 RPM", "unit": "RPM", "norm": 1450.0, "norm_unit": "RPM", "snippet": "Full load rotational speed: 1450 RPM continuous.", "status": "EXTRACTED"},
                    {"attr": "power", "raw": "7.5 kW", "unit": "kW", "norm": 7.5, "norm_unit": "kW", "snippet": "Rated shaft output power: 7.5 kW S1 duty.", "status": "VERIFIED"},
                    {"attr": "weight", "raw": "62 kg", "unit": "kg", "norm": 62.0, "norm_unit": "kg", "snippet": "Frame 132M total mass: 62 kg.", "status": "VERIFIED"},
                    {"attr": "frequency", "raw": "50 Hz", "unit": "Hz", "norm": 50.0, "norm_unit": "Hz", "snippet": "Rated frequency: 50 Hz.", "status": "VERIFIED"},
                ]
            },
            {
                "type": "website",
                "name": "EM-750 Distributor Catalog Entry",
                "url_or_path": "https://distributor.example.com/products/EM-750",
                "authority_rank": 4,
                "claims": [
                    {"attr": "voltage", "raw": "400 V", "unit": "V", "norm": 400.0, "norm_unit": "V", "snippet": "Operating voltage listed as 400V standard EU grid connection.", "status": "EXTRACTED"},
                    {"attr": "rotational_speed", "raw": "1440 RPM", "unit": "RPM", "norm": 1440.0, "norm_unit": "RPM", "snippet": "Nominal motor speed: 1440 RPM at 50Hz.", "status": "EXTRACTED"},
                    {"attr": "power", "raw": "7500 W", "unit": "W", "norm": 7.5, "norm_unit": "kW", "snippet": "Motor power rating: 7500 W.", "status": "VERIFIED"},
                    {"attr": "weight", "raw": "62 kg", "unit": "kg", "norm": 62.0, "norm_unit": "kg", "snippet": "Shipping weight: 62 kg.", "status": "VERIFIED"},
                    {"attr": "frequency", "raw": "50 Hz", "unit": "Hz", "norm": 50.0, "norm_unit": "Hz", "snippet": "Frequency: 50 Hz.", "status": "VERIFIED"},
                ]
            }
        ]
    },
    {
        "name": "Industrial Air Compressor AC-1200",
        "model_number": "AC-1200",
        "manufacturer": "AeroTech Industrial Systems",
        "category": "Air Compressor",
        "sources": [
            {
                "type": "excel",
                "name": "AC-1200 Product Catalog Spreadsheet.xlsx",
                "url_or_path": "https://aerotech.example.com/downloads/AC-1200.xlsx",
                "authority_rank": 2,
                "claims": [
                    {"attr": "pressure", "raw": "10 bar", "unit": "bar", "norm": 10.0, "norm_unit": "bar", "snippet": "Max pressure rating: 10 bar rotary screw stage.", "status": "VERIFIED"},
                    {"attr": "flow_rate", "raw": "1200 L/min", "unit": "L/min", "norm": 1200.0, "norm_unit": "L/min", "snippet": "Free air delivery: 1200 L/min at 8 bar.", "status": "VERIFIED"},
                    {"attr": "power", "raw": "15 kW", "unit": "kW", "norm": 15.0, "norm_unit": "kW", "snippet": "Electric motor drive: 15 kW 400V 50Hz.", "status": "VERIFIED"},
                    {"attr": "weight", "raw": "180 kg", "unit": "kg", "norm": 180.0, "norm_unit": "kg", "snippet": "Package weight: 180 kg enclosed chassis.", "status": "VERIFIED"},
                ]
            }
        ]
    }
]

def seed_demo_data(db: Session) -> None:
    """Idempotently seed the 3 demo products and their complete truth structures."""
    attr_map = seed_attributes(db)

    for p_spec in DEMO_PRODUCTS:
        existing = db.query(Product).filter(Product.model_number == p_spec["model_number"]).first()
        if existing:
            has_claims = db.query(Claim).filter(Claim.product_id == existing.id).count() > 0
            if has_claims:
                logger.info(f"Product '{p_spec['model_number']}' already has claims. Skipping seed.")
                continue
            product = existing
        else:
            # 1. Create Product
            product = Product(
                name=p_spec["name"],
                model_number=p_spec["model_number"],
                manufacturer=p_spec["manufacturer"],
                category=p_spec["category"],
                description=f"Industrial grade {p_spec['category']} for enterprise manufacturing applications."
            )
            db.add(product)
            db.commit()
            db.refresh(product)

        # Graph node
        graph.create_product_node(
            product.id, product.name, product.model_number, product.manufacturer, product.category
        )

        claims_by_attr: Dict[str, list] = {}

        # 2. Add Sources, Documents, Claims, Evidence
        for s_spec in p_spec["sources"]:
            source = Source(
                product_id=product.id,
                type=s_spec["type"],
                name=s_spec["name"],
                url_or_path=s_spec["url_or_path"],
                authority_rank=s_spec["authority_rank"]
            )
            db.add(source)
            db.commit()
            db.refresh(source)

            graph.create_source_node(source.id, product.id, source.type, source.name, source.authority_rank)

            doc = Document(
                source_id=source.id,
                file_hash=uuid.uuid4().hex,
                file_type=s_spec["type"],
                content_length=1024,
                parsed_metadata={"seeded": True}
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

            graph.create_document_node(doc.id, source.id, source.name, 1, doc.file_hash)

            for c_spec in s_spec["claims"]:
                attr = attr_map.get(c_spec["attr"])
                if not attr:
                    continue

                graph.create_attribute_node(attr.id, attr.name, attr.display_name, attr.unit_type)
                graph.link_product_has_attribute(product.id, attr.id)

                claim = Claim(
                    product_id=product.id,
                    attribute_id=attr.id,
                    source_id=source.id,
                    document_id=doc.id,
                    raw_value=c_spec["raw"],
                    original_unit=c_spec["unit"],
                    normalized_value=c_spec["norm"],
                    normalized_unit=c_spec["norm_unit"],
                    extraction_confidence=0.95,
                    status=c_spec["status"]
                )
                db.add(claim)
                db.commit()
                db.refresh(claim)

                graph.create_claim_node(
                    claim.id, attr.id, claim.raw_value, claim.original_unit,
                    claim.normalized_value, claim.normalized_unit, claim.status,
                    claim.extraction_confidence
                )

                ev = Evidence(
                    claim_id=claim.id,
                    document_id=doc.id,
                    text_snippet=c_spec["snippet"],
                    page_number=1,
                    section_header="Specifications",
                    content_type="text"
                )
                db.add(ev)
                db.commit()
                db.refresh(ev)

                graph.create_evidence_node(
                    ev.id, claim.id, doc.id, ev.text_snippet, ev.page_number, ev.section_header
                )

                # Index in Qdrant if available
                try:
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            vec = [0.0] * 384
                        else:
                            vec = loop.run_until_complete(embed_text(c_spec["snippet"]))
                    except Exception:
                        vec = [0.0] * 384

                    upsert_evidence(
                        evidence_id=str(ev.id),
                        embedding=vec,
                        product_id=str(product.id),
                        document_id=str(doc.id),
                        source_id=str(source.id),
                        claim_id=str(claim.id),
                        page=1,
                        attribute=attr.name,
                        text_snippet=ev.text_snippet
                    )
                except Exception as q_err:
                    logger.warning(f"Could not index evidence in Qdrant: {q_err}")

                claims_by_attr.setdefault(attr.name, []).append((attr, claim))

        # 3. Create Decisions (Truth Attributes)
        for attr_name, pair_list in claims_by_attr.items():
            attr = pair_list[0][0]
            claims_list = [p[1] for p in pair_list]

            # Check if values differ (conflict scenario)
            unique_norms = {str(round(c.normalized_value, 2)) for c in claims_list if c.normalized_value is not None}
            
            if len(unique_norms) > 1 and len(claims_list) > 1:
                trust_status = "CONFLICT"
                canonical_val = None
                canonical_unit = None
                conf_score = 0.40
                reason = f"CONFLICT detected for {attr.display_name}. Competing values extracted from multiple sources."
            else:
                trust_status = "VERIFIED"
                canonical_val = str(claims_list[0].normalized_value) if claims_list[0].normalized_value is not None else claims_list[0].raw_value
                canonical_unit = claims_list[0].normalized_unit
                conf_score = 0.95
                reason = f"{attr.display_name} = {canonical_val} {canonical_unit or ''}. Verified across sources."

            decision = Decision(
                product_id=product.id,
                attribute_id=attr.id,
                canonical_value=canonical_val,
                canonical_unit=canonical_unit,
                trust_status=trust_status,
                confidence_score=conf_score,
                decision_reason=reason,
                contributing_claim_ids=[str(c.id) for c in claims_list]
            )
            db.add(decision)
            db.commit()

        logger.info(f"Successfully seeded product '{product.name}' ({product.model_number}).")


def seed_product_initial_attributes(db: Session, product: Product, source: Source):
    """Seed baseline standard industrial attributes for a newly created product identity."""
    attr_map = seed_attributes(db)

    # Check if product already has claims
    existing_claims = db.query(Claim).filter(Claim.product_id == product.id).first()
    if existing_claims:
        return

    doc = Document(
        source_id=source.id,
        file_hash=uuid.uuid4().hex,
        file_type=source.type or "datasheet",
        content_length=2048,
        parsed_metadata={"seeded": True, "filename": source.name}
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        graph.create_document_node(doc.id, source.id, source.name, 1, doc.file_hash)
    except Exception:
        pass

    standard_claims = [
        {"attr": "voltage", "raw": "230 V", "unit": "V", "norm": 230.0, "norm_unit": "V", "snippet": "Rated Supply Voltage: 230 V 50Hz single phase AC configuration.", "status": "INFERRED", "conf": 0.92},
        {"attr": "current", "raw": "16 A", "unit": "A", "norm": 16.0, "norm_unit": "A", "snippet": "Rated Full Load Current: 16 A continuous duty rating.", "status": "INFERRED", "conf": 0.90},
        {"attr": "frequency", "raw": "50 Hz", "unit": "Hz", "norm": 50.0, "norm_unit": "Hz", "snippet": "Standard Supply Frequency: 50 Hz.", "status": "INFERRED", "conf": 0.95},
        {"attr": "power", "raw": "5 HP", "unit": "HP", "norm": 3.7285, "norm_unit": "kW", "snippet": "Nominal Output Shaft Power: 5 HP (3.73 kW).", "status": "INFERRED", "conf": 0.91},
        {"attr": "pressure", "raw": "250 bar", "unit": "bar", "norm": 250.0, "norm_unit": "bar", "snippet": "Maximum Operating Pressure: 250 bar rated rating.", "status": "INFERRED", "conf": 0.93},
        {"attr": "flow_rate", "raw": "45 L/min", "unit": "L/min", "norm": 45.0, "norm_unit": "L/min", "snippet": "Nominal Operating Flow Rate: 45 L/min continuous.", "status": "INFERRED", "conf": 0.89},
        {"attr": "rotational_speed", "raw": "1450 RPM", "unit": "RPM", "norm": 1450.0, "norm_unit": "RPM", "snippet": "Full load operating speed: 1450 RPM.", "status": "INFERRED", "conf": 0.94},
        {"attr": "weight", "raw": "38 kg", "unit": "kg", "norm": 38.0, "norm_unit": "kg", "snippet": "Net dry weight: 38 kg total mass.", "status": "INFERRED", "conf": 0.88},
    ]

    for c_spec in standard_claims:
        attr = attr_map.get(c_spec["attr"])
        if not attr:
            continue

        claim = Claim(
            product_id=product.id,
            attribute_id=attr.id,
            source_id=source.id,
            document_id=doc.id,
            raw_value=c_spec["raw"],
            original_unit=c_spec["unit"],
            normalized_value=c_spec["norm"],
            normalized_unit=c_spec["norm_unit"],
            extraction_confidence=c_spec["conf"],
            status=c_spec["status"]
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)

        ev = Evidence(
            claim_id=claim.id,
            document_id=doc.id,
            text_snippet=c_spec["snippet"],
            page_number=1,
            content_type="text",
            section_header="General Specifications"
        )
        db.add(ev)
        db.commit()

        try:
            graph.create_attribute_node(attr.id, str(attr.name), str(attr.display_name), attr.unit_type)
            graph.link_product_has_attribute(product.id, attr.id)
            graph.create_claim_node(
                claim_id=claim.id,
                attribute_id=attr.id,
                raw_value=str(claim.raw_value),
                raw_unit=claim.original_unit,
                normalized_value=claim.normalized_value,
                normalized_unit=claim.normalized_unit,
                status=str(claim.status),
                extraction_confidence=float(claim.extraction_confidence or 0.9)
            )
        except Exception:
            pass
