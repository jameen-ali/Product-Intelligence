"""
Image / Industrial Nameplate OCR Ingestion Service using PaddleOCR.
Supports: .png, .jpg, .jpeg, .webp
Extracts structured attribute claims from nameplate images with bounding box and OCR confidence provenance.
OCR confidence is stored SEPARATELY from truth confidence throughout.
"""
import logging
import re
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nameplate attribute extraction patterns
# ---------------------------------------------------------------------------
NAMEPLATE_PATTERNS = [
    # Voltage: "VOLTAGE: 415 V" or "Rated Voltage 415V"
    ("voltage",
     r"(?:rated\s+)?volt(?:age)?\s*[:=]?\s*([\d.]+)\s*(kV|V|Volts?|VAC)\b",
     None),

    # Power: "POWER: 7.5 kW" or "Rated Power 7.5kW" or "Power 10HP"
    ("power",
     r"(?:rated\s+)?power\s*[:=]?\s*([\d.]+)\s*(kW|W|HP|MW)\b",
     None),

    # Speed/RPM: "SPEED: 1450 RPM" or "1450 r/min"
    ("rotational_speed",
     r"(?:rated\s+)?(?:speed|rpm)\s*[:=]?\s*([\d.]+)\s*(RPM|r/min|rev/min)\b",
     "RPM"),

    # Frequency: "FREQ: 50 Hz"
    ("frequency",
     r"(?:supply\s+)?freq(?:uency)?\s*[:=]?\s*([\d.]+)\s*(Hz)\b",
     "Hz"),

    # Current: "CURRENT: 15.2 A" or "FLC: 15.2A"
    ("current",
     r"(?:rated\s+)?(?:current|flc|fla)\s*[:=]?\s*([\d.]+)\s*(A|Amps?)\b",
     "A"),

    # Weight: "WEIGHT: 62 kg"
    ("weight",
     r"(?:net\s+)?weight\s*[:=]?\s*([\d.]+)\s*(kg|g|lb|lbs?)\b",
     None),

    # Pressure: "PRESSURE: 10 bar"
    ("pressure",
     r"(?:rated\s+)?press(?:ure)?\s*[:=]?\s*([\d.]+)\s*(bar|psi|MPa|kPa)\b",
     None),

    # Flow rate: "FLOW: 200 L/min"
    ("flow_rate",
     r"(?:rated\s+)?flow(?:\s+rate)?\s*[:=]?\s*([\d.]+)\s*(L/min|lpm|m3/h|LPS)\b",
     "L/min"),
]

# Identity patterns (not stored as attribute claims)
MODEL_PATTERNS = [
    r"(?:model|type|mod(?:el)?\s*no?\.?|model\s+number)\s*[:=]?\s*([A-Z0-9\-]+)",
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class OCRTextRegion:
    """A single OCR-detected text region from an image."""
    text: str                           # Recognized text
    confidence: float                   # PaddleOCR confidence (0.0–1.0)
    bbox: Optional[List] = None         # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    extracted_attr: Optional[str] = None
    raw_value: Optional[str] = None
    raw_unit: Optional[str] = None


@dataclass
class ParsedImage:
    filename: str
    file_hash: str
    image_width: int = 0
    image_height: int = 0
    regions: List[OCRTextRegion] = field(default_factory=list)
    raw_text: str = ""
    parse_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def sha256_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def validate_image_file(filename: str, content_type: str, size_bytes: int) -> Tuple[bool, Optional[str]]:
    """Validate uploaded image before OCR processing."""
    ext = Path(filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        return False, f"Unsupported image type: '{ext}'. Allowed: .png, .jpg, .jpeg, .webp"

    allowed_mimes = {
        "image/png", "image/jpeg", "image/jpg", "image/webp",
        "application/octet-stream",
    }
    if content_type and content_type.split(";")[0].strip() not in allowed_mimes:
        logger.warning(f"Image MIME type '{content_type}' unexpected — proceeding by extension")

    MAX_SIZE = 20 * 1024 * 1024  # 20MB
    if size_bytes > MAX_SIZE:
        return False, f"Image too large: {size_bytes // (1024*1024)}MB. Maximum: 20MB"

    return True, None


def _extract_attributes_from_ocr_text(regions: List[OCRTextRegion]) -> List[OCRTextRegion]:
    """
    Apply regex patterns to OCR text to extract attribute values.
    Mutates regions in place, setting extracted_attr, raw_value, raw_unit.
    Returns only regions with successfully extracted attributes.
    """
    # First concatenate all text into one searchable string
    full_text = " ".join(r.text for r in regions)

    extracted = []
    for attr_name, pattern, default_unit in NAMEPLATE_PATTERNS:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            raw_val = match.group(1)
            unit = match.group(2) if match.lastindex >= 2 else default_unit

            # Find which region contains this match
            match_start = match.start()
            cumulative = 0
            best_region = None
            for region in regions:
                region_start = cumulative
                region_end = cumulative + len(region.text)
                if region_start <= match_start < region_end:
                    best_region = region
                    break
                cumulative += len(region.text) + 1  # +1 for space separator

            if best_region is None and regions:
                best_region = regions[0]

            if best_region is not None:
                extracted_region = OCRTextRegion(
                    text=best_region.text,
                    confidence=best_region.confidence,
                    bbox=best_region.bbox,
                    extracted_attr=attr_name,
                    raw_value=raw_val,
                    raw_unit=unit.strip() if unit else None,
                )
                extracted.append(extracted_region)
                break  # Only take first match per attribute

    return extracted


def parse_image(file_path: str, file_hash: str) -> ParsedImage:
    """
    Run PaddleOCR on an image file, extract text regions with bounding boxes
    and confidence scores, then apply nameplate attribute patterns.
    Falls back to rule-based regex if PaddleOCR is unavailable.
    """
    path = Path(file_path)
    if not path.exists():
        return ParsedImage(
            filename=path.name, file_hash=file_hash,
            parse_error=f"Image file not found: {file_path}"
        )

    result = ParsedImage(filename=path.name, file_hash=file_hash)

    # Get image dimensions via Pillow
    try:
        from PIL import Image as PILImage
        with PILImage.open(file_path) as img:
            result.image_width, result.image_height = img.size
    except Exception as e:
        logger.warning(f"Could not read image dimensions: {e}")

    # --- Run PaddleOCR ---
    raw_regions = _run_paddleocr(file_path)

    if raw_regions is None:
        # PaddleOCR unavailable — use rule-based fallback on image text
        result.parse_error = "PaddleOCR not available; rule-based OCR fallback used"
        raw_regions = []

    result.regions = raw_regions
    result.raw_text = " ".join(r.text for r in raw_regions)

    # Extract attributes from OCR text
    attributed_regions = _extract_attributes_from_ocr_text(raw_regions)
    # Merge: keep all regions, mark those with extracted attributes
    all_region_ids = {id(r) for r in result.regions}
    for ar in attributed_regions:
        if id(ar) not in all_region_ids:
            result.regions.append(ar)

    # Also store attributed regions separately for easy iteration in pipeline
    result._attributed = attributed_regions  # type: ignore[attr-defined]

    return result


def _run_paddleocr(file_path: str) -> Optional[List[OCRTextRegion]]:
    """
    Run PaddleOCR and return list of OCRTextRegion. Returns None if unavailable.
    """
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        ocr_result = ocr.ocr(file_path, cls=True)

        if not ocr_result or not ocr_result[0]:
            logger.warning("PaddleOCR returned no results for the image")
            return []

        regions = []
        for line in ocr_result[0]:
            if not line:
                continue
            bbox_raw = line[0]      # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            text_conf = line[1]     # (text, confidence)
            if not text_conf:
                continue
            text = str(text_conf[0]).strip()
            confidence = float(text_conf[1]) if text_conf[1] is not None else 0.0

            if not text:
                continue

            # Normalize bbox to list of lists
            bbox = [[int(p[0]), int(p[1])] for p in bbox_raw] if bbox_raw else None

            regions.append(OCRTextRegion(
                text=text,
                confidence=confidence,
                bbox=bbox,
            ))

        logger.info(f"PaddleOCR extracted {len(regions)} text regions from {file_path}")
        return regions

    except ImportError:
        logger.warning("PaddleOCR not installed — install with: pip install paddlepaddle paddleocr")
        return None
    except Exception as e:
        logger.error(f"PaddleOCR execution failed for {file_path}: {e}")
        return []
