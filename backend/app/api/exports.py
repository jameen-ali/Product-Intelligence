import csv
import io
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Product, Source, Document, Claim, Evidence, Attribute

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("/status")
def exports_status():
    return {"status": "ready"}


def _build_export_records(product_id: uuid.UUID, db: Session) -> list:
    """Build structured export records from PostgreSQL truth data."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    claims = db.query(Claim).filter(Claim.product_id == product_id).all()

    # Group claims by attribute
    attr_claim_map: dict = {}
    for claim in claims:
        attr = db.query(Attribute).filter(Attribute.id == claim.attribute_id).first()
        source = db.query(Source).filter(Source.id == claim.source_id).first()
        document = db.query(Document).filter(Document.id == claim.document_id).first() if claim.document_id else None
        evidences = db.query(Evidence).filter(Evidence.claim_id == claim.id).all()

        if not attr:
            continue

        attr_key = attr.name
        if attr_key not in attr_claim_map:
            attr_claim_map[attr_key] = {
                "attribute": attr.name,
                "display_name": attr.display_name,
                "unit_type": attr.unit_type,
                "claims": [],
            }

        attr_claim_map[attr_key]["claims"].append({
            "claim_id": str(claim.id),
            "raw_value": claim.raw_value,
            "original_unit": claim.original_unit,
            "normalized_value": claim.normalized_value,
            "normalized_unit": claim.normalized_unit,
            "status": claim.status,
            "extraction_confidence": claim.extraction_confidence,
            "source_id": str(claim.source_id) if claim.source_id else None,
            "source_name": source.name if source else None,
            "source_type": source.type if source else None,
            "document_id": str(document.id) if document else None,
            "document_filename": document.parsed_metadata.get("filename") if document and document.parsed_metadata else None,
            "evidence": [
                {
                    "evidence_id": str(e.id),
                    "text_snippet": e.text_snippet,
                    "page_number": e.page_number,
                    "section_header": e.section_header,
                }
                for e in evidences
            ],
        })

    # Compute trust status per attribute
    from app.conflict.engine import compute_confidence_for_attribute
    records = []
    for attr_key, attr_data in attr_claim_map.items():
        n = len(attr_data["claims"])
        claims_meta = [
            {
                "authority_rank": 1,  # default if no source rank
                "extraction_confidence": c.get("extraction_confidence", 0.9),
                "normalized_value": c.get("normalized_value"),
            }
            for c in attr_data["claims"]
        ]

        if n == 0:
            trust_status = "UNKNOWN"
        elif n == 1:
            trust_status = "INFERRED"
        else:
            norms = set(
                round(c["normalized_value"], 2) if c["normalized_value"] is not None
                else attr_data["claims"][i]["raw_value"]
                for i, c in enumerate(claims_meta)
            )
            trust_status = "VERIFIED" if len(norms) == 1 else "CONFLICT"

        confidence, breakdown = compute_confidence_for_attribute(claims_meta, trust_status)

        best = attr_data["claims"][0] if attr_data["claims"] else {}
        canonical_value = (
            f"{best.get('normalized_value')} {best.get('normalized_unit', '')}".strip()
            if best.get("normalized_value") is not None
            else f"{best.get('raw_value', '')} {best.get('original_unit', '')}".strip()
        )

        records.append({
            "product_id": str(product_id),
            "product_name": product.name,
            "model_number": product.model_number,
            "manufacturer": product.manufacturer,
            "attribute": attr_data["attribute"],
            "display_name": attr_data["display_name"],
            "canonical_value": canonical_value,
            "trust_status": trust_status,
            "confidence": confidence,
            "confidence_breakdown": breakdown,
            "claims": attr_data["claims"],
        })

    return records


@router.get("/products/{product_id}/json")
def export_json(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Export full product truth record as JSON."""
    records = _build_export_records(product_id, db)

    product = db.query(Product).filter(Product.id == product_id).first()
    export = {
        "export_version": "1.0",
        "product": {
            "id": str(product_id),
            "name": product.name,
            "model_number": product.model_number,
            "manufacturer": product.manufacturer,
            "category": product.category,
        },
        "attributes": records,
        "meta": {
            "total_attributes": len(records),
            "verified": sum(1 for r in records if r["trust_status"] == "VERIFIED"),
            "inferred": sum(1 for r in records if r["trust_status"] == "INFERRED"),
            "conflict": sum(1 for r in records if r["trust_status"] == "CONFLICT"),
            "unknown": sum(1 for r in records if r["trust_status"] == "UNKNOWN"),
        },
    }

    content = json.dumps(export, indent=2, default=str)
    return StreamingResponse(
        io.StringIO(content),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=product_truth_{product_id}.json"},
    )


@router.get("/products/{product_id}/csv")
def export_csv(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Export product truth attributes as CSV."""
    records = _build_export_records(product_id, db)

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "product_name", "model_number", "manufacturer",
            "attribute", "display_name", "canonical_value",
            "trust_status", "confidence",
            "raw_value", "original_unit", "normalized_value", "normalized_unit",
            "source_name", "source_type",
            "document_filename", "page_number", "evidence_text",
        ]
    )
    writer.writeheader()

    for rec in records:
        for claim in rec.get("claims", []):
            first_ev = claim["evidence"][0] if claim.get("evidence") else {}
            writer.writerow({
                "product_name": rec["product_name"],
                "model_number": rec["model_number"],
                "manufacturer": rec["manufacturer"],
                "attribute": rec["attribute"],
                "display_name": rec["display_name"],
                "canonical_value": rec["canonical_value"],
                "trust_status": rec["trust_status"],
                "confidence": rec["confidence"],
                "raw_value": claim.get("raw_value", ""),
                "original_unit": claim.get("original_unit", ""),
                "normalized_value": claim.get("normalized_value", ""),
                "normalized_unit": claim.get("normalized_unit", ""),
                "source_name": claim.get("source_name", ""),
                "source_type": claim.get("source_type", ""),
                "document_filename": claim.get("document_filename", ""),
                "page_number": first_ev.get("page_number", ""),
                "evidence_text": first_ev.get("text_snippet", ""),
            })

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=product_truth_{product_id}.csv"},
    )

