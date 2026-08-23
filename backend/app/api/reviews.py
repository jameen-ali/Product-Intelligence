import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Claim, Review, Product

router = APIRouter(prefix="/reviews", tags=["Reviews"])


class ReviewAction(BaseModel):
    reviewer_id: str = "demo_user"
    notes: Optional[str] = None


@router.get("/status")
def reviews_status():
    return {"status": "ready"}


@router.post("/claims/{claim_id}/approve")
def approve_claim(claim_id: uuid.UUID, action: ReviewAction, db: Session = Depends(get_db)):
    """Approve a claim as canonical — marks claim status VERIFIED, marks other claims for attribute REJECTED."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Mark approved claim as VERIFIED
    claim.status = "VERIFIED"

    # Mark other competing claims under the same attribute as REJECTED
    other_claims = db.query(Claim).filter(
        Claim.product_id == claim.product_id,
        Claim.attribute_id == claim.attribute_id,
        Claim.id != claim.id
    ).all()
    for oc in other_claims:
        if oc.status != "UNKNOWN":
            oc.status = "REJECTED"

    # Avoid duplicate review history entries for exact same action
    existing = db.query(Review).filter(
        Review.claim_id == claim.id,
        Review.action == "APPROVED"
    ).first()
    if not existing:
        review = Review(
            claim_id=claim.id,
            reviewer_id=action.reviewer_id,
            action="APPROVED",
            notes=action.notes or "Human review: Approved as canonical value",
        )
        db.add(review)
    else:
        review = existing

    db.commit()
    db.refresh(claim)

    return {
        "review_id": str(review.id),
        "claim_id": str(claim_id),
        "action": "APPROVED",
        "reviewer_id": action.reviewer_id,
        "message": "Decision saved: Claim approved as canonical value.",
    }


@router.post("/claims/{claim_id}/reject")
def reject_claim(claim_id: uuid.UUID, action: ReviewAction, db: Session = Depends(get_db)):
    """Reject a claim — marks claim status REJECTED."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim.status = "REJECTED"

    existing = db.query(Review).filter(
        Review.claim_id == claim.id,
        Review.action == "REJECTED"
    ).first()
    if not existing:
        review = Review(
            claim_id=claim.id,
            reviewer_id=action.reviewer_id,
            action="REJECTED",
            notes=action.notes or "Human review: Claim rejected",
        )
        db.add(review)
    else:
        review = existing

    db.commit()
    db.refresh(claim)

    return {
        "review_id": str(review.id),
        "claim_id": str(claim_id),
        "action": "REJECTED",
        "reviewer_id": action.reviewer_id,
        "message": "Decision saved: Claim rejected.",
    }


@router.post("/claims/{claim_id}/mark-unknown")
def mark_unknown(claim_id: uuid.UUID, action: ReviewAction, db: Session = Depends(get_db)):
    """Mark a claim and attribute as UNKNOWN."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    attr_claims = db.query(Claim).filter(
        Claim.product_id == claim.product_id,
        Claim.attribute_id == claim.attribute_id
    ).all()
    for ac in attr_claims:
        ac.status = "UNKNOWN"

    existing = db.query(Review).filter(
        Review.claim_id == claim.id,
        Review.action == "OVERRIDDEN"
    ).first()
    if not existing:
        review = Review(
            claim_id=claim.id,
            reviewer_id=action.reviewer_id,
            action="OVERRIDDEN",
            notes=f"Marked UNKNOWN. {action.notes or ''}".strip(),
        )
        db.add(review)
    else:
        review = existing

    db.commit()
    db.refresh(claim)

    return {
        "review_id": str(review.id),
        "claim_id": str(claim_id),
        "action": "MARK_UNKNOWN",
        "reviewer_id": action.reviewer_id,
        "message": "Decision saved: Attribute marked UNKNOWN.",
    }


@router.get("/products/{product_id}")
def get_product_reviews(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return review history for a product's claims."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    claims = db.query(Claim).filter(Claim.product_id == product_id).all()
    claim_ids = [c.id for c in claims]

    reviews = db.query(Review).filter(Review.claim_id.in_(claim_ids)).all() if claim_ids else []
    return {
        "product_id": str(product_id),
        "review_count": len(reviews),
        "reviews": [
            {
                "review_id": str(r.id),
                "claim_id": str(r.claim_id),
                "reviewer_id": r.reviewer_id,
                "action": r.action,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
    }


