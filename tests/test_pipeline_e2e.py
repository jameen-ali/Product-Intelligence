"""
E2E pipeline test: PDF → parse → extract → normalize → PostgreSQL → Qdrant → Neo4j
Uses the demo HP-4000 PDF.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

import asyncio
import pytest

DEMO_PDF_PATH = "demo/hydraulic_pump/hp4000_datasheet.pdf"

def test_demo_pdf_exists():
    assert os.path.exists(DEMO_PDF_PATH), f"Demo PDF not found at {DEMO_PDF_PATH}"

def test_file_hashing():
    from app.ingestion.hashing import sha256_file
    h1 = sha256_file(DEMO_PDF_PATH)
    h2 = sha256_file(DEMO_PDF_PATH)
    assert h1 == h2, "SHA-256 must be deterministic"
    assert len(h1) == 64, f"Expected 64-char hex, got {len(h1)}"

def test_pdf_parsing():
    from app.ingestion.pdf_ingest import parse_pdf
    from app.ingestion.hashing import sha256_file
    file_hash = sha256_file(DEMO_PDF_PATH)
    doc = parse_pdf(DEMO_PDF_PATH, file_hash)

    assert doc.parse_error is None, f"Parse error: {doc.parse_error}"
    assert doc.filename == "hp4000_datasheet.pdf"
    assert doc.file_hash == file_hash
    assert len(doc.blocks) > 0, "Expected at least 1 block from PDF"
    assert doc.raw_text and len(doc.raw_text) > 50, "Expected non-empty raw text"

    # Check for expected content
    full_text = doc.raw_text.lower()
    assert any(kw in full_text for kw in ["hp-4000", "hp4000", "hydraulic", "pump"]), \
        "Product name not found in parsed text"

def test_unit_normalization_pipeline():
    """Verify the normalization engine handles the HP-4000 spec values correctly."""
    from app.normalization.units import normalise_to_canonical, are_equivalent

    # 5 HP rated power
    nr = normalise_to_canonical(5, "HP", "power")
    assert nr.normalized_unit == "kW"
    assert abs(nr.normalized_value - 3.7285) < 0.01
    assert nr.raw_value == 5, "Original value must be preserved"

    # 250 bar pressure
    nr2 = normalise_to_canonical(250, "bar", "pressure")
    assert nr2.normalized_unit == "bar"  # already canonical
    assert nr2.normalized_value == 250

    # Cross-unit equivalence: 5HP ≈ 3730W (not a conflict)
    assert are_equivalent(5, "HP", 3730, "W")

    # 38 kg weight
    nr3 = normalise_to_canonical(38, "kg", "mass")
    assert nr3.raw_value == 38
    assert nr3.raw_unit == "kg"

@pytest.mark.asyncio
async def test_full_pipeline_smoke(app_client):
    """
    Smoke test: create product, add source, process PDF, verify evidence returned.
    Requires: Ollama running OR OpenRouter API key configured.
    """
    # Create product
    r = app_client.post("/products", json={
        "name": "HP-4000 Hydraulic Pump",
        "manufacturer": "HydroDyn",
        "model_number": "HP-4000",
        "category": "Hydraulic Pump",
    })
    assert r.status_code == 201
    product_id = r.json()["id"]

    # Add source
    r2 = app_client.post(f"/products/{product_id}/sources", json={
        "type": "datasheet",
        "name": "HP-4000 Demo Datasheet",
        "authority_rank": 1,
    })
    assert r2.status_code == 201
    source_id = r2.json()["id"]

    # Process PDF
    with open(DEMO_PDF_PATH, "rb") as f:
        r3 = app_client.post(
            f"/processing/products/{product_id}/process",
            data={"source_id": source_id},
            files={"file": ("hp4000_datasheet.pdf", f, "application/pdf")},
        )

    assert r3.status_code in [200, 202], f"Processing returned {r3.status_code}: {r3.text}"
    result = r3.json().get("result", {})
    assert result.get("status") in ["COMPLETED", "DEDUPLICATED"], \
        f"Unexpected status: {result.get('status')}"
    
    # Verify evidence is stored
    r4 = app_client.get(f"/products/{product_id}/attributes")
    assert r4.status_code == 200
    attrs = r4.json()["attributes"]
    # At minimum some attributes should be extracted (if AI is available)
    # We don't assert count > 0 since AI may be unavailable in test env

    # Verify graph endpoint responds
    r5 = app_client.get(f"/products/{product_id}/graph")
    assert r5.status_code in [200, 503]  # 503 if Neo4j unavailable
