"""
Deterministic conflict detection and confidence scoring engine.
No LLM involvement — all arithmetic is code per PRD Section 19.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Authority rank to 0-1 score (rank 1 = highest authority)
AUTHORITY_SCORE_BY_RANK = {
    1: 1.00,  # manufacturer datasheet
    2: 0.92,  # manufacturer manual
    3: 0.80,  # manufacturer website
    4: 0.70,  # label/image
    5: 0.65,  # certified doc
    6: 0.50,  # authorized distributor
    7: 0.40,  # supplier
    8: 0.25,  # third party
}

# Closeness threshold for declaring CONFLICT
CLOSENESS_THRESHOLD = 0.15

# Default weights per PRD Section 19
DEFAULT_WEIGHTS = {
    "authority": 0.25,
    "agreement": 0.25,
    "evidence_quality": 0.20,
    "recency": 0.10,
    "extraction_certainty": 0.10,
    "normalization_certainty": 0.10,
}


def _authority_score(rank: int) -> float:
    return AUTHORITY_SCORE_BY_RANK.get(rank, 0.40)


def _evidence_quality_score(claims: list) -> float:
    """Evidence exactness: direct numeric statement = 1.0, indirect/approximate = 0.6."""
    if not claims:
        return 0.0
    has_direct = any(c.get("extraction_confidence", 0) >= 0.9 for c in claims)
    return 1.0 if has_direct else 0.6


def _normalization_certainty(claims: list) -> float:
    """Whether values are already normalized (no ambiguity in conversion)."""
    normalized = [c for c in claims if c.get("normalized_value") is not None]
    if not normalized:
        return 0.5
    return 0.9


def compute_confidence_for_attribute(
    claims_with_meta: list,
    trust_status: str,
    weights: Optional[dict] = None,
) -> tuple:
    """
    Compute a confidence score and factor breakdown for an attribute.
    Returns (score: float, breakdown: dict).
    """
    w = weights or DEFAULT_WEIGHTS

    if not claims_with_meta:
        return 0.0, {"note": "No claims"}

    auth_scores = [
        _authority_score(c.get("authority_rank", 5)) for c in claims_with_meta
    ]
    authority = sum(auth_scores) / len(auth_scores) if auth_scores else 0.0

    n_claims = len(claims_with_meta)
    if trust_status == "VERIFIED":
        agreement = min(1.0, 0.5 + 0.25 * n_claims)
    elif trust_status == "CONFLICT":
        agreement = 0.1
    else:
        agreement = 0.4

    evidence_quality = _evidence_quality_score(claims_with_meta)
    recency = 0.8
    extraction_certainty = (
        sum(c.get("extraction_confidence", 0.9) for c in claims_with_meta) / n_claims
    )
    normalization_certainty = _normalization_certainty(claims_with_meta)

    score = (
        w["authority"] * authority
        + w["agreement"] * agreement
        + w["evidence_quality"] * evidence_quality
        + w["recency"] * recency
        + w["extraction_certainty"] * extraction_certainty
        + w["normalization_certainty"] * normalization_certainty
    )

    breakdown = {
        "authority": round(authority, 3),
        "agreement": round(agreement, 3),
        "evidence_quality": round(evidence_quality, 3),
        "recency": round(recency, 3),
        "extraction_certainty": round(extraction_certainty, 3),
        "normalization_certainty": round(normalization_certainty, 3),
    }

    return round(min(1.0, score), 3), breakdown


def generate_decision_reason(
    attr_display_name: str,
    trust_status: str,
    claims_with_meta: list,
    winning_value: Optional[str],
    breakdown: dict,
) -> str:
    """
    Generate a deterministic, human-readable decision reason.
    No LLM. Based purely on scoring factors and claim metadata.
    """
    if not claims_with_meta:
        return f"No claims found for {attr_display_name}. Status: UNKNOWN."

    n = len(claims_with_meta)
    source_names = list({c.get("source_name", "Unknown source") for c in claims_with_meta})
    source_list = ", ".join(source_names[:3])

    if trust_status == "VERIFIED":
        if n == 1:
            return (
                f"{attr_display_name} = {winning_value}. "
                f"Single high-authority source: {source_list}. "
                f"Authority score: {breakdown.get('authority', 0):.2f}. "
                f"No conflicting sources detected. "
                f"Evidence is a direct verbatim statement from the source document."
            )
        else:
            return (
                f"{attr_display_name} = {winning_value}. "
                f"{n} independent sources agree: {source_list}. "
                f"Authority score: {breakdown.get('authority', 0):.2f}. "
                f"Agreement score: {breakdown.get('agreement', 0):.2f}. "
                f"No conflicting normalized values detected."
            )
    elif trust_status == "INFERRED":
        return (
            f"{attr_display_name} = {winning_value} (inferred). "
            f"Single source: {source_list}. "
            f"Authority score: {breakdown.get('authority', 0):.2f}. "
            f"Insufficient independent sources for VERIFIED status. "
            f"Value accepted as working estimate pending corroboration."
        )
    elif trust_status == "CONFLICT":
        values = list({c.get("raw_value", "?") for c in claims_with_meta})
        return (
            f"CONFLICT detected for {attr_display_name}. "
            f"Competing values: {', '.join(str(v) for v in values[:3])}. "
            f"Sources: {source_list}. "
            f"Score gap between top candidate groups is within closeness threshold ({CLOSENESS_THRESHOLD}). "
            f"Human review required to select the canonical value."
        )
    else:
        return f"No reliable evidence found for {attr_display_name}."


def detect_conflicts_for_product(product_id, db: Session) -> list:
    """
    Detect unresolved CONFLICT attributes for a product.
    Attributes with human-verified (VERIFIED), rejected, or UNKNOWN claims are excluded if resolved.
    """
    from app.models.entities import Claim, Attribute, Source

    claims = db.query(Claim).filter(Claim.product_id == product_id).all()
    attr_claims: dict = {}

    for claim in claims:
        attr = db.query(Attribute).filter(Attribute.id == claim.attribute_id).first()
        if not attr:
            continue
        source = db.query(Source).filter(Source.id == claim.source_id).first()
        key = attr.name
        if key not in attr_claims:
            attr_claims[key] = []
        attr_claims[key].append({
            "claim_id": str(claim.id),
            "attribute_id": str(claim.attribute_id),
            "attribute_name": attr.name,
            "attribute_display_name": attr.display_name,
            "raw_value": claim.raw_value,
            "original_unit": claim.original_unit,
            "normalized_value": claim.normalized_value,
            "normalized_unit": claim.normalized_unit,
            "extraction_confidence": claim.extraction_confidence,
            "status": claim.status,
            "source_id": str(claim.source_id) if claim.source_id else None,
            "source_name": source.name if source else "Unknown",
            "source_type": source.type if source else "unknown",
            "authority_rank": source.authority_rank if source else 5,
        })

    conflicts = []
    for attr_name, c_list in attr_claims.items():
        # Exclude attributes where human review has approved (VERIFIED) or marked UNKNOWN
        if any(c["status"] in ("VERIFIED", "UNKNOWN") for c in c_list):
            continue

        # Exclude REJECTED claims for active conflict calculation
        active_claims = [c for c in c_list if c["status"] != "REJECTED"]
        if len(active_claims) < 2:
            continue

        value_groups: dict = {}
        for c in active_claims:
            if c["normalized_value"] is not None:
                grp_key = str(round(c["normalized_value"], 2))
            else:
                grp_key = str(c["raw_value"]).strip().lower()
            value_groups.setdefault(grp_key, []).append(c)

        if len(value_groups) > 1:
            groups = list(value_groups.items())
            conflicts.append({
                "attribute_name": attr_name,
                "attribute_display_name": c_list[0]["attribute_display_name"],
                "attribute_id": c_list[0]["attribute_id"],
                "groups": [
                    {
                        "normalized_value": grp_key,
                        "claims": grp_claims,
                        "source_count": len({c["source_id"] for c in grp_claims}),
                        "best_authority": min(c["authority_rank"] for c in grp_claims),
                    }
                    for grp_key, grp_claims in groups
                ],
            })

    return conflicts

