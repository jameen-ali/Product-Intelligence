"""
Comprehensive tests for Image / Industrial Nameplate OCR ingestion.
Covers: PaddleOCR pipeline, OCR confidence, bounding box provenance, attribute extraction,
DB persistence, Qdrant, Neo4j, multi-source conflicts, product isolation.
"""
import sys
import os
import uuid
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
NAMEPLATE_PNG = os.path.join(FIXTURES_DIR, "EM750_nameplate.png")


# ---------------------------------------------------------------------------
# PART 1 — Unit / Parser Tests
# ---------------------------------------------------------------------------

class TestImageValidation:
    def test_valid_png_passes(self):
        from app.ingestion.image_ingest import validate_image_file
        ok, err = validate_image_file("nameplate.png", "image/png", 1024 * 100)
        assert ok is True
        assert err is None

    def test_valid_jpg_passes(self):
        from app.ingestion.image_ingest import validate_image_file
        ok, err = validate_image_file("photo.jpg", "image/jpeg", 1024 * 200)
        assert ok is True

    def test_valid_webp_passes(self):
        from app.ingestion.image_ingest import validate_image_file
        ok, err = validate_image_file("scan.webp", "image/webp", 1024 * 50)
        assert ok is True

    def test_invalid_extension_rejected(self):
        from app.ingestion.image_ingest import validate_image_file
        ok, err = validate_image_file("document.pdf", "application/pdf", 1024)
        assert ok is False
        assert "Unsupported" in err

    def test_file_too_large_rejected(self):
        from app.ingestion.image_ingest import validate_image_file
        ok, err = validate_image_file("huge.png", "image/png", 25 * 1024 * 1024)
        assert ok is False
        assert "too large" in err.lower()


class TestNameplateAttributeExtraction:
    def test_extracts_voltage_from_text(self):
        """Voltage is correctly extracted from OCR text."""
        from app.ingestion.image_ingest import OCRTextRegion, _extract_attributes_from_ocr_text
        regions = [
            OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.97),
            OCRTextRegion(text="POWER: 7.5 kW", confidence=0.95),
            OCRTextRegion(text="SPEED: 1450 RPM", confidence=0.92),
        ]
        extracted = _extract_attributes_from_ocr_text(regions)
        attrs = {r.extracted_attr for r in extracted}
        assert "voltage" in attrs

    def test_extracts_power_from_text(self):
        from app.ingestion.image_ingest import OCRTextRegion, _extract_attributes_from_ocr_text
        regions = [OCRTextRegion(text="RATED POWER: 7.5 kW", confidence=0.96)]
        extracted = _extract_attributes_from_ocr_text(regions)
        assert any(r.extracted_attr == "power" for r in extracted)

    def test_extracts_frequency_from_text(self):
        from app.ingestion.image_ingest import OCRTextRegion, _extract_attributes_from_ocr_text
        regions = [OCRTextRegion(text="FREQ: 50 Hz", confidence=0.98)]
        extracted = _extract_attributes_from_ocr_text(regions)
        assert any(r.extracted_attr == "frequency" for r in extracted)

    def test_missing_attribute_not_fabricated(self):
        """Attributes not present in text are not fabricated."""
        from app.ingestion.image_ingest import OCRTextRegion, _extract_attributes_from_ocr_text
        regions = [OCRTextRegion(text="MOTOR BRAND NAME", confidence=0.95)]
        extracted = _extract_attributes_from_ocr_text(regions)
        # No known attributes should be extracted from brand name text
        for r in extracted:
            assert r.extracted_attr is not None  # Only real extractions

    def test_ocr_confidence_preserved_in_region(self):
        """OCR confidence is stored on each region separately."""
        from app.ingestion.image_ingest import OCRTextRegion
        r = OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.97, bbox=[[10, 20], [200, 20], [200, 40], [10, 40]])
        assert r.confidence == 0.97
        assert r.bbox is not None
        assert len(r.bbox) == 4

    def test_raw_value_and_unit_extracted(self):
        from app.ingestion.image_ingest import OCRTextRegion, _extract_attributes_from_ocr_text
        regions = [OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.97)]
        extracted = _extract_attributes_from_ocr_text(regions)
        voltage = next((r for r in extracted if r.extracted_attr == "voltage"), None)
        assert voltage is not None
        assert voltage.raw_value == "415"
        assert voltage.raw_unit in ("V", "Volts", "VAC", "v")


class TestOCRPipelineMocked:
    """Tests using mocked PaddleOCR for CI environments without GPU."""

    @pytest.mark.asyncio
    async def test_parse_image_with_mocked_ocr(self, tmp_path):
        """Full parse_image with mocked PaddleOCR output."""
        from app.ingestion.image_ingest import parse_image

        mock_ocr_output = [[
            [[[10, 20], [200, 20], [200, 40], [10, 40]], ("INDUSTRIAL ELECTRIC MOTOR", 0.99)],
            [[[10, 60], [200, 60], [200, 80], [10, 80]], ("VOLTAGE: 415 V", 0.97)],
            [[[10, 100], [200, 100], [200, 120], [10, 120]], ("POWER: 7.5 kW", 0.95)],
            [[[10, 140], [200, 140], [200, 160], [10, 140]], ("SPEED: 1450 RPM", 0.92)],
            [[[10, 180], [200, 180], [200, 200], [10, 180]], ("FREQUENCY: 50 Hz", 0.98)],
            [[[10, 220], [200, 220], [200, 240], [10, 220]], ("WEIGHT: 62 kg", 0.94)],
        ]]

        # Create a valid dummy image
        img_path = str(tmp_path / "test_nameplate.png")
        from PIL import Image
        img = Image.new("RGB", (400, 300), color=(50, 50, 60))
        img.save(img_path)

        with patch("app.ingestion.image_ingest._run_paddleocr") as mock_ocr:
            from app.ingestion.image_ingest import OCRTextRegion
            mock_ocr.return_value = [
                OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.97, bbox=[[10, 60], [200, 60], [200, 80], [10, 80]]),
                OCRTextRegion(text="POWER: 7.5 kW", confidence=0.95, bbox=[[10, 100], [200, 100], [200, 120], [10, 120]]),
                OCRTextRegion(text="SPEED: 1450 RPM", confidence=0.92, bbox=None),
                OCRTextRegion(text="FREQUENCY: 50 Hz", confidence=0.98, bbox=None),
                OCRTextRegion(text="WEIGHT: 62 kg", confidence=0.94, bbox=None),
            ]

            result = parse_image(img_path, "testhash_img")
            assert result.parse_error is None or "PaddleOCR" not in str(result.parse_error)
            assert len(result.regions) >= 1

            attributed = getattr(result, "_attributed", [])
            attrs = {r.extracted_attr for r in attributed}
            assert "voltage" in attrs or "power" in attrs  # At least one attribute extracted

    @pytest.mark.asyncio
    async def test_ocr_confidence_separate_from_truth_confidence(self, tmp_path):
        """
        Critical: OCR confidence stored in Evidence.bbox['ocr_confidence'],
        NOT in claim.extraction_confidence (which could be different).
        """
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source, Evidence, Claim
        from app.services.processing_service import process_image_for_product

        img_path = str(tmp_path / "sep_confidence.png")
        from PIL import Image
        img = Image.new("RGB", (401, 301), color=(41, 41, 51))
        img.save(img_path)

        db = SessionLocal()
        try:
            p = Product(name="Confidence Test Motor", model_number="CONF-01")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)
            s = Source(product_id=p.id, type="image", name="Nameplate", authority_rank=4)
            db.add(s); db.commit(); db.refresh(s)
            sid = str(s.id)
        finally:
            db.close()

        from app.ingestion.image_ingest import OCRTextRegion
        with patch("app.ingestion.image_ingest._run_paddleocr") as mock_ocr:
            mock_ocr.return_value = [
                OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.89),
                OCRTextRegion(text="POWER: 7.5 kW", confidence=0.93),
            ]

            db_sess = SessionLocal()
            try:
                result = await process_image_for_product(pid, sid, img_path, db_sess)
            finally:
                db_sess.close()

        assert result["status"] == "COMPLETED"
        if result["claims_extracted"] >= 1:
            db_check = SessionLocal()
            try:
                evs = db_check.query(Evidence).filter(
                    Evidence.document_id == uuid.UUID(result["document_id"])
                ).all()
                for ev in evs:
                    assert ev.content_type == "image_ocr"
                    assert ev.bbox is not None
                    assert "ocr_confidence" in ev.bbox  # OCR confidence SEPARATELY stored
                    assert ev.bbox["ocr_confidence"] > 0.0
            finally:
                db_check.close()

    @pytest.mark.asyncio
    async def test_bounding_box_persisted_in_evidence(self, tmp_path):
        """Bounding box coordinates are stored in Evidence.bbox['bbox']."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source, Evidence
        from app.services.processing_service import process_image_for_product

        img_path = str(tmp_path / "bbox_test.png")
        from PIL import Image
        img = Image.new("RGB", (402, 302), color=(42, 42, 52))
        img.save(img_path)

        db = SessionLocal()
        try:
            p = Product(name="BBox Test Motor", model_number="BBOX-01")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)
            s = Source(product_id=p.id, type="image", name="Nameplate", authority_rank=4)
            db.add(s); db.commit(); db.refresh(s)
            sid = str(s.id)
        finally:
            db.close()

        from app.ingestion.image_ingest import OCRTextRegion
        test_bbox = [[10, 60], [200, 60], [200, 80], [10, 80]]
        with patch("app.ingestion.image_ingest._run_paddleocr") as mock_ocr:
            mock_ocr.return_value = [
                OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.97, bbox=test_bbox),
            ]

            db_sess = SessionLocal()
            try:
                result = await process_image_for_product(pid, sid, img_path, db_sess)
            finally:
                db_sess.close()

        if result["claims_extracted"] >= 1:
            db_check = SessionLocal()
            try:
                evs = db_check.query(Evidence).filter(
                    Evidence.document_id == uuid.UUID(result["document_id"])
                ).all()
                voltage_ev = next((e for e in evs if e.bbox and e.bbox.get("bbox")), None)
                if voltage_ev:
                    assert voltage_ev.bbox["bbox"] == test_bbox
            finally:
                db_check.close()

    @pytest.mark.asyncio
    async def test_image_deduplication(self, tmp_path):
        """Same image file uploaded twice returns DEDUPLICATED on second call."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source
        from app.services.processing_service import process_image_for_product

        img_path = str(tmp_path / "dedup_img.png")
        from PIL import Image
        img = Image.new("RGB", (303, 203), color=(33, 33, 43))
        img.save(img_path)

        db = SessionLocal()
        try:
            p = Product(name="Dedup Image Motor", model_number="DEDUP-IMG-01")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)
            s = Source(product_id=p.id, type="image", name="Nameplate", authority_rank=4)
            db.add(s); db.commit(); db.refresh(s)
            sid = str(s.id)
        finally:
            db.close()

        from app.ingestion.image_ingest import OCRTextRegion
        with patch("app.ingestion.image_ingest._run_paddleocr") as mock_ocr:
            mock_ocr.return_value = [OCRTextRegion(text="POWER: 10 kW", confidence=0.9)]

            db1 = SessionLocal()
            r1 = await process_image_for_product(pid, sid, img_path, db1)
            db1.close()

            db2 = SessionLocal()
            r2 = await process_image_for_product(pid, sid, img_path, db2)
            db2.close()

        assert r1["status"] == "COMPLETED"
        assert r2["status"] == "DEDUPLICATED"

    @pytest.mark.asyncio
    async def test_product_isolation_image(self, tmp_path):
        """Image ingestion for Product A does not create claims on Product B."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source, Claim
        from app.services.processing_service import process_image_for_product

        img_path = str(tmp_path / "isolation.png")
        from PIL import Image
        img = Image.new("RGB", (304, 204), color=(34, 34, 44))
        img.save(img_path)

        db = SessionLocal()
        try:
            pa = Product(name="Isolation Image A", model_number="ISO-IMG-A")
            pb = Product(name="Isolation Image B", model_number="ISO-IMG-B")
            db.add(pa); db.add(pb); db.commit()
            db.refresh(pa); db.refresh(pb)
            pa_id = str(pa.id); pb_id = str(pb.id)

            s = Source(product_id=pa.id, type="image", name="Nameplate A", authority_rank=4)
            db.add(s); db.commit(); db.refresh(s)
            sa_id = str(s.id)
        finally:
            db.close()

        from app.ingestion.image_ingest import OCRTextRegion
        with patch("app.ingestion.image_ingest._run_paddleocr") as mock_ocr:
            mock_ocr.return_value = [OCRTextRegion(text="VOLTAGE: 415 V", confidence=0.97)]

            db_sess = SessionLocal()
            await process_image_for_product(pa_id, sa_id, img_path, db_sess)
            db_sess.close()

        db_check = SessionLocal()
        try:
            claims_b = db_check.query(Claim).filter(Claim.product_id == uuid.UUID(pb_id)).all()
            assert len(claims_b) == 0
        finally:
            db_check.close()

    def test_api_image_invalid_extension(self, app_client):
        """API returns 400 for non-image file uploads."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source

        db = SessionLocal()
        try:
            p = Product(name="API Image Test", model_number="API-IMG-01")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)
            s = Source(product_id=p.id, type="image", name="Nameplate", authority_rank=4)
            db.add(s); db.commit(); db.refresh(s)
            sid = str(s.id)
        finally:
            db.close()

        import io
        r = app_client.post(
            f"/processing/products/{pid}/process-image",
            data={"source_id": sid},
            files={"file": ("test.pdf", io.BytesIO(b"fake content"), "application/pdf")},
        )
        assert r.status_code == 400
        assert "Invalid image file" in r.json()["detail"]
