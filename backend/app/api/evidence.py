import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Product, Claim, Evidence, Attribute, Source, Document

router = APIRouter(prefix="/products", tags=["Evidence & Claims"])

@router.get("/{product_id}/attributes")
def get_product_attributes(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return all attributes with their claims and evidence for a product."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    claims = (
        db.query(Claim)
        .filter(Claim.product_id == product_id)
        .all()
    )

    attr_map = {}
    for claim in claims:
        attr = db.query(Attribute).filter(Attribute.id == claim.attribute_id).first()
        if not attr:
            continue

        evidences = db.query(Evidence).filter(Evidence.claim_id == claim.id).all()
        source = db.query(Source).filter(Source.id == claim.source_id).first()
        document = db.query(Document).filter(Document.id == claim.document_id).first()

        claim_dict = {
            "claim_id": str(claim.id),
            "raw_value": claim.raw_value,
            "original_unit": claim.original_unit,
            "normalized_value": claim.normalized_value,
            "normalized_unit": claim.normalized_unit,
            "extraction_confidence": claim.extraction_confidence,
            "status": claim.status,
            "location_reference": claim.location_reference,
            "source": {
                "id": str(source.id) if source else None,
                "name": source.name if source else None,
                "type": source.type if source else None,
            },
            "document": {
                "id": str(document.id) if document else None,
                "filename": document.parsed_metadata.get("filename") if document and document.parsed_metadata else None,
            },
            "evidence": [
                {
                    "evidence_id": str(e.id),
                    "text_snippet": e.text_snippet,
                    "page_number": e.page_number,
                    "section_header": e.section_header,
                    "content_type": e.content_type,
                }
                for e in evidences
            ],
        }

        attr_key = attr.name
        if attr_key not in attr_map:
            attr_map[attr_key] = {
                "attribute_id": str(attr.id),
                "name": attr.name,
                "display_name": attr.display_name,
                "unit_type": attr.unit_type,
                "default_unit": attr.default_unit,
                "trust_status": "UNKNOWN",
                "claims": [],
            }
        attr_map[attr_key]["claims"].append(claim_dict)

    # Compute trust status, confidence, and decision reason per attribute
    from app.conflict.engine import compute_confidence_for_attribute, generate_decision_reason

    for attr_name, attr_data in attr_map.items():
        n = len(attr_data["claims"])
        claims_meta = [
            {
                "authority_rank": c["source"].get("authority_rank", 5) if c.get("source") else 5,
                "extraction_confidence": c.get("extraction_confidence", 0.9),
                "normalized_value": c.get("normalized_value"),
                "raw_value": c.get("raw_value", ""),
                "source_name": c["source"].get("name", "Unknown") if c.get("source") else "Unknown",
            }
            for c in attr_data["claims"]
        ]

        # Check for human review decisions
        verified_claim = next((c for c in attr_data["claims"] if c["status"] == "VERIFIED"), None)
        unknown_claim = next((c for c in attr_data["claims"] if c["status"] == "UNKNOWN"), None)

        if verified_claim:
            trust_status = "VERIFIED"
            canonical_claim = verified_claim
        elif unknown_claim and all(c["status"] == "UNKNOWN" for c in attr_data["claims"]):
            trust_status = "UNKNOWN"
            canonical_claim = None
        else:
            active_claims = [c for c in attr_data["claims"] if c["status"] != "REJECTED"]
            if not active_claims:
                trust_status = "UNKNOWN"
                canonical_claim = None
            elif len(active_claims) == 1:
                trust_status = "INFERRED"
                canonical_claim = active_claims[0]
            else:
                norms = set(
                    round(c["normalized_value"], 2) if c["normalized_value"] is not None else c["raw_value"]
                    for c in active_claims
                )
                if len(norms) == 1:
                    trust_status = "VERIFIED"
                    canonical_claim = active_claims[0]
                else:
                    trust_status = "CONFLICT"
                    canonical_claim = active_claims[0]

        attr_data["trust_status"] = trust_status

        # Confidence score + breakdown
        confidence, breakdown = compute_confidence_for_attribute(claims_meta, trust_status)
        attr_data["confidence"] = confidence
        attr_data["confidence_breakdown"] = breakdown

        # Canonical value
        canonical_value = None
        if canonical_claim:
            if canonical_claim.get("normalized_value") is not None:
                canonical_value = f"{canonical_claim['normalized_value']} {canonical_claim.get('normalized_unit', '')}".strip()
            else:
                canonical_value = f"{canonical_claim['raw_value']} {canonical_claim.get('original_unit', '')}".strip()

        # Decision reason
        if verified_claim:
            decision_reason = (
                f"{attr_data['display_name']} = {canonical_value}. "
                f"Human review decision: APPROVED. "
                f"Value approved by human review as canonical."
            )
        elif unknown_claim and trust_status == "UNKNOWN":
            decision_reason = (
                f"{attr_data['display_name']} marked UNKNOWN by human review. "
                f"Evidence judged unreliable pending further documentation."
            )
        else:
            decision_reason = generate_decision_reason(
                attr_display_name=attr_data["display_name"],
                trust_status=trust_status,
                claims_with_meta=claims_meta,
                winning_value=canonical_value,
                breakdown=breakdown,
            )

        attr_data["decision_reason"] = decision_reason
        attr_data["canonical_value"] = canonical_value

    return {"product_id": str(product_id), "attributes": list(attr_map.values())}



@router.get("/{product_id}/claims")
def get_product_claims(product_id: uuid.UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    claims = db.query(Claim).filter(Claim.product_id == product_id).all()
    return [
        {
            "claim_id": str(c.id),
            "attribute_id": str(c.attribute_id),
            "raw_value": c.raw_value,
            "original_unit": c.original_unit,
            "normalized_value": c.normalized_value,
            "normalized_unit": c.normalized_unit,
            "extraction_confidence": c.extraction_confidence,
            "status": c.status,
            "location_reference": c.location_reference,
        }
        for c in claims
    ]


@router.get("/{product_id}/evidence")
def get_product_evidence(product_id: uuid.UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    claims = db.query(Claim).filter(Claim.product_id == product_id).all()
    all_evidence = []
    for claim in claims:
        evidences = db.query(Evidence).filter(Evidence.claim_id == claim.id).all()
        attr = db.query(Attribute).filter(Attribute.id == claim.attribute_id).first()
        for e in evidences:
            all_evidence.append({
                "evidence_id": str(e.id),
                "claim_id": str(claim.id),
                "attribute": attr.name if attr else None,
                "raw_value": claim.raw_value,
                "original_unit": claim.original_unit,
                "text_snippet": e.text_snippet,
                "page_number": e.page_number,
                "section_header": e.section_header,
                "content_type": e.content_type,
            })
    return {"product_id": str(product_id), "evidence": all_evidence}
