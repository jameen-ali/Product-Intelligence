"""
Claim extractor — orchestrates LLM extraction through the ModelGateway.
Produces RawAttributeCandidate objects with embedded evidence.
Implements retry-once with correction prompt on JSON validation failure.
"""
import json
import logging
import re
from typing import Optional
from pydantic import BaseModel, Field

from app.core.model_gateway import model_gateway
from app.core.ai_provider import AIProviderUnavailableError
from app.extraction.prompts import (
    PRODUCT_IDENTITY_PROMPT,
    ATTRIBUTE_EXTRACTION_PROMPT,
    ATTRIBUTE_EXTRACTION_CORRECTION_PROMPT,
)

logger = logging.getLogger(__name__)

SUPPORTED_ATTRIBUTES = {
    "voltage", "power", "pressure", "flow_rate", "rotational_speed",
    "weight", "length", "width", "height", "temperature_min",
    "temperature_max", "current", "frequency",
}

# Attribute → unit_type mapping for normalisation
ATTRIBUTE_UNIT_TYPE = {
    "voltage": "voltage",
    "power": "power",
    "pressure": "pressure",
    "flow_rate": "flow",
    "rotational_speed": "rotational_speed",
    "weight": "mass",
    "length": "length",
    "width": "length",
    "height": "length",
    "temperature_min": "temperature_min",
    "temperature_max": "temperature_max",
    "current": "current",
    "frequency": None,
}

class ProductIdentity(BaseModel):
    product_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    category: Optional[str] = None
    sku: Optional[str] = None

class RawAttributeCandidate(BaseModel):
    attribute: str
    raw_value: str
    raw_unit: Optional[str] = None
    evidence_text: str
    page: int
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)

def _extract_json_array(text: str) -> Optional[list]:
    """Extract JSON array from LLM response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = text.rstrip("`").strip()
    # Find first [ and last ]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return None

def _extract_json_object(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response."""
    text = text.strip()
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = text.rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return None

async def extract_product_identity(text: str) -> ProductIdentity:
    """Extract product identity from document header text."""
    try:
        provider = await model_gateway.get_active_provider()
        prompt = PRODUCT_IDENTITY_PROMPT.format(text=text[:2000])
        raw = await provider.generate(prompt)
        obj = _extract_json_object(raw)
        if obj:
            return ProductIdentity(**{k: v for k, v in obj.items() if k in ProductIdentity.model_fields})
    except AIProviderUnavailableError:
        logger.warning("AI provider unavailable for product identity extraction")
    except Exception as e:
        logger.error(f"Product identity extraction error: {e}")
    return ProductIdentity()

async def extract_attributes_from_block(
    text: str, page: int
) -> list[RawAttributeCandidate]:
    """
    Extract attribute claims from a single document block.
    Retries once with correction prompt on JSON validation failure.
    Returns only valid candidates with non-empty evidence_text.
    """
    candidates = []

    try:
        provider = await model_gateway.get_active_provider()
    except AIProviderUnavailableError:
        logger.warning("AI provider unavailable — using deterministic rule-based extraction fallback")
        return _extract_attributes_rule_based(text, page)

    prompt = ATTRIBUTE_EXTRACTION_PROMPT.format(text=text[:3000], page=page)

    raw = None
    try:
        raw = await provider.generate(prompt)
        data = _extract_json_array(raw)

        if data is None:
            # Retry once with correction prompt
            correction = ATTRIBUTE_EXTRACTION_CORRECTION_PROMPT.format(
                error="Could not parse JSON array from response",
                text=text[:1500]
            )
            raw = await provider.generate(correction)
            data = _extract_json_array(raw)

        if data is None:
            logger.warning(f"Could not parse extraction output for page {page}; skipping block")
            return []

        for item in data:
            if not isinstance(item, dict):
                continue
            attr = str(item.get("attribute", "")).strip().lower()
            raw_val = str(item.get("raw_value", "")).strip()
            evidence = str(item.get("evidence_text", "")).strip()

            # Skip: unknown attribute, empty value, or missing evidence
            if attr not in SUPPORTED_ATTRIBUTES:
                continue
            if not raw_val or raw_val in ("null", "None"):
                continue
            if not evidence or len(evidence) < 3:
                logger.debug(f"Skipping claim for '{attr}' — evidence_text missing or too short")
                continue

            candidates.append(RawAttributeCandidate(
                attribute=attr,
                raw_value=raw_val,
                raw_unit=item.get("raw_unit") or None,
                evidence_text=evidence,
                page=item.get("page", page),
                confidence=min(max(float(item.get("confidence", 0.9)), 0.0), 1.0),
            ))

    except Exception as e:
        logger.warning(f"Attribute extraction LLM generation warning for page {page}: {e}. Using rule-based fallback...")
        return _extract_attributes_rule_based(text, page)

    return candidates


def _extract_attributes_rule_based(text: str, page: int) -> list[RawAttributeCandidate]:
    """
    Deterministic rule-based pattern matching fallback when LLM is unavailable.
    Guarantees evidence-grounded claim extraction without LLM server.
    """
    candidates = []
    patterns = [
        ("voltage", r"(?:voltage|supply|rated voltage)[^\.\n]*?(\d+(?:\.\d+)?)\s*(V|Volts|VAC)", "V"),
        ("power", r"(?:power|rated power|output)[^\.\n]*?(\d+(?:\.\d+)?)\s*(HP|kW|W)", None),
        ("pressure", r"(?:pressure|operating pressure|max pressure)[^\.\n]*?(\d+(?:\.\d+)?)\s*(bar|psi|MPa)", None),
        ("flow_rate", r"(?:flow|flow rate|nominal flow)[^\.\n]*?(\d+(?:\.\d+)?)\s*(L/min|lpm|LPS)", "L/min"),
        ("rotational_speed", r"(?:speed|pump speed|rpm)[^\.\n]*?(\d+(?:\.\d+)?)\s*(RPM|rpm|r/min)", "RPM"),
        ("weight", r"(?:weight|net weight|mass)[^\.\n]*?(\d+(?:\.\d+)?)\s*(kg|lb|lbs)", None),
        ("current", r"(?:current|rated current)[^\.\n]*?(\d+(?:\.\d+)?)\s*(A|Amps)", "A"),
        ("frequency", r"(?:frequency|supply frequency)[^\.\n]*?(\d+(?:\.\d+)?)\s*(Hz)", "Hz"),
    ]

    # First attempt explicit keyword-anchored sentence patterns
    for attr, pat, default_unit in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            val_str = match.group(1)
            unit_str = match.group(2) if match.lastindex >= 2 else default_unit
            
            # Find enclosing sentence bounds
            start = max(text.rfind('.', 0, match.start()), text.rfind('\n', 0, match.start()))
            start = 0 if start == -1 else start + 1
            end = text.find('.', match.end())
            end = len(text) if end == -1 else end + 1
            sentence = text[start:end].strip()

            candidates.append(RawAttributeCandidate(
                attribute=attr,
                raw_value=val_str,
                raw_unit=unit_str,
                evidence_text=sentence,
                page=page,
                confidence=0.92
            ))

    # Fallback to general numeric patterns if no keyword matches found for an attribute
    extracted_attrs = {c.attribute for c in candidates}
    general_patterns = [
        ("voltage", r"(\d+(?:\.\d+)?)\s*(V|Volts|VAC)", "V"),
        ("power", r"(\d+(?:\.\d+)?)\s*(HP|kW|W)", None),
        ("pressure", r"(\d+(?:\.\d+)?)\s*(bar|psi|MPa)", None),
        ("flow_rate", r"(\d+(?:\.\d+)?)\s*(L/min|lpm|LPS)", "L/min"),
        ("rotational_speed", r"(\d+(?:\.\d+)?)\s*(RPM|rpm|r/min)", "RPM"),
        ("weight", r"(\d+(?:\.\d+)?)\s*(kg|lb|lbs)", None),
        ("current", r"(\d+(?:\.\d+)?)\s*(A|Amps)", "A"),
        ("frequency", r"(\d+(?:\.\d+)?)\s*(Hz)", "Hz"),
    ]

    for attr, pat, default_unit in general_patterns:
        if attr in extracted_attrs:
            continue
        for match in re.finditer(pat, text, re.IGNORECASE):
            # Ignore SKU strings like HDPUMP-4000-230V
            matched_prefix = text[max(0, match.start() - 10):match.start()]
            if "SKU" in matched_prefix or "HDPUMP" in matched_prefix or "-" in matched_prefix:
                continue

            val_str = match.group(1)
            unit_str = match.group(2) if match.lastindex >= 2 else default_unit
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            evidence = text[start:end].strip()

            candidates.append(RawAttributeCandidate(
                attribute=attr,
                raw_value=val_str,
                raw_unit=unit_str,
                evidence_text=evidence,
                page=page,
                confidence=0.85
            ))

    return candidates

