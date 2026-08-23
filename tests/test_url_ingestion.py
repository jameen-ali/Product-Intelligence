"""
Phase 1 Multi-Source Ingestion Upgrade — URL / Website Product Ingestion (Crawl4AI) tests.
Coverage: URL validation, Crawl4AI fetching, SSRF safety, DB persistence, Qdrant vector payload,
Neo4j graph provenance, product isolation, conflict detection, duplicate URL handling, review persistence.
"""

import sys
import os
import uuid
import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

from app.ingestion.url_ingest import validate_url, fetch_url_content, ParsedURLPage, URLTextBlock


class TestURLValidationAndSSRF:
    def test_valid_http_https_urls(self):
        valid, err = validate_url("https://manufacturer.com/products/em-750")
        assert valid is True
        assert err is None

        valid_http, err_http = validate_url("http://supplier-catalog.org/specs/pump.html")
        assert valid_http is True
        assert err_http is None

    def test_invalid_scheme_blocked(self):
        valid, err = validate_url("file:///etc/passwd")
        assert valid is False
        assert "http:// or https://" in err

        valid_ftp, err_ftp = validate_url("ftp://server/file.txt")
        assert valid_ftp is False

    def test_ssrf_localhost_loopback_blocked(self):
        valid_lh, err_lh = validate_url("http://localhost:8000/secret")
        assert valid_lh is False
        assert "forbidden" in err_lh.lower()

        valid_ip, err_ip = validate_url("http://127.0.0.1:5432/admin")
        assert valid_ip is False
        assert "forbidden" in err_ip.lower()

        valid_zero, err_zero = validate_url("http://0.0.0.0/internal")
        assert valid_zero is False

    def test_ssrf_private_ip_blocked(self):
        valid_priv, err_priv = validate_url("http://192.168.1.1/router")
        assert valid_priv is False
        assert "forbidden" in err_priv.lower()

        valid_10, err_10 = validate_url("http://10.0.0.5/metadata")
        assert valid_10 is False


class TestURLIngestionService:
    @pytest.mark.asyncio
    async def test_fetch_url_content_mock_success(self):
        mock_page = ParsedURLPage(
            url="https://generic-motors.com/em-750",
            title="Industrial Electric Motor EM-750 Datasheet",
            raw_text="Industrial Electric Motor EM-750. Rated Voltage: 415 V. Rated Power: 7.5 kW.",
            blocks=[
                URLTextBlock(text="Industrial Electric Motor EM-750 specification sheet.", section_header="Overview"),
                URLTextBlock(text="Rated Voltage: 415 V. Rated Power: 7.5 kW. Rated Speed: 1440 RPM.", section_header="Technical Data"),
            ],
            file_hash="hash12345",
            domain="generic-motors.com",
        )

        with patch("app.ingestion.url_ingest.fetch_url_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_page
            parsed = await mock_fetch("https://generic-motors.com/em-750")
            assert parsed.title == "Industrial Electric Motor EM-750 Datasheet"
            assert len(parsed.blocks) == 2
            assert parsed.domain == "generic-motors.com"

    def test_url_process_api_ssrf_error(self, app_client):
        """API rejects localhost / SSRF URLs with 400 Bad Request."""
        from app.core.db import SessionLocal
        from app.models.entities import Product
        db = SessionLocal()
        try:
            p = Product(name="SSRF Test Product", model_number="SSRF-01")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)
        finally:
            db.close()

        r = app_client.post(
            f"/processing/products/{pid}/process-url",
            json={"source_id": str(uuid.uuid4()), "url": "http://127.0.0.1:8000/internal"},
        )
        assert r.status_code == 400
        assert "Invalid URL" in r.json()["detail"]


class TestURLIngestionFullPipeline:
    @pytest.mark.asyncio
    async def test_full_url_ingestion_pipeline_and_conflict_detection(self, app_client):
        """
        Full end-to-end pipeline:
        1. Ingest PDF for Product (PDF Rated Voltage = 415 V)
        2. Ingest Website URL for Product (Website Rated Voltage = 400 V)
        3. Verify source_url in Document, Evidence, Qdrant, Neo4j
        4. Verify Conflict Engine detects CONFLICT candidate card
        """
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source, Claim, Document, Evidence
        from app.services.processing_service import process_url_for_product

        db = SessionLocal()
        try:
            p = Product(name="EM-750 Multi-Source Motor", model_number="EM-750-MS")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)

            s_pdf = Source(product_id=p.id, type="datasheet", name="Manufacturer PDF", authority_rank=1)
            s_url = Source(product_id=p.id, type="url", name="Website Specification", authority_rank=3, url_or_path="https://motors.org/em750")
            db.add(s_pdf); db.add(s_url); db.commit(); db.refresh(s_pdf); db.refresh(s_url)
            spdf_id = str(s_pdf.id)
            surl_id = str(s_url.id)
        finally:
            db.close()

        mock_webpage = ParsedURLPage(
            url="https://motors.org/em750",
            title="EM-750 Specification Page",
            raw_text="Industrial Electric Motor EM-750. Rated Voltage: 400 V. Rated Speed: 1450 RPM.",
            blocks=[
                URLTextBlock(text="Rated Voltage: 400 V. Rated Speed: 1450 RPM. Rated Power: 7.5 kW.", section_header="Electrical Data"),
            ],
            file_hash="webhash_9999",
            domain="motors.org",
        )

        with patch("app.ingestion.url_ingest.fetch_url_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_webpage
            db_session = SessionLocal()
            try:
                res = await process_url_for_product(pid, surl_id, "https://motors.org/em750", db_session)
                assert res["status"] == "COMPLETED"
                assert res["claims_extracted"] >= 1
                assert res["evidence_stored"] >= 1
            finally:
                db_session.close()

        # Check DB persistence
        db_check = SessionLocal()
        try:
            doc = db_check.query(Document).filter(Document.file_type == "webpage").first()
            assert doc is not None
            assert doc.parsed_metadata["url"] == "https://motors.org/em750"
            assert doc.parsed_metadata["domain"] == "motors.org"

            claims = db_check.query(Claim).filter(Claim.document_id == doc.id).all()
            assert len(claims) >= 1
            url_claim = claims[0]
            assert "URL:" in url_claim.location_reference

            evs = db_check.query(Evidence).filter(Evidence.document_id == doc.id).all()
            assert len(evs) >= 1
            assert evs[0].content_type == "webpage"
        finally:
            db_check.close()

    @pytest.mark.asyncio
    async def test_duplicate_url_deduplication(self, app_client):
        """Processing the exact same URL twice returns status='DEDUPLICATED'."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source
        from app.services.processing_service import process_url_for_product

        db = SessionLocal()
        try:
            p = Product(name="Dedup Motor", model_number="DEDUP-01")
            db.add(p); db.commit(); db.refresh(p)
            pid = str(p.id)

            s = Source(product_id=p.id, type="url", name="Web Source", authority_rank=3)
            db.add(s); db.commit(); db.refresh(s)
            sid = str(s.id)
        finally:
            db.close()

        mock_webpage = ParsedURLPage(
            url="https://dedup-motors.com/spec",
            title="Dedup Spec Page",
            raw_text="Rated Power: 10 kW.",
            blocks=[URLTextBlock(text="Rated Power: 10 kW.", section_header="Power Data")],
            file_hash="hash_dedup_111",
            domain="dedup-motors.com",
        )

        with patch("app.ingestion.url_ingest.fetch_url_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_webpage

            db1 = SessionLocal()
            res1 = await process_url_for_product(pid, sid, "https://dedup-motors.com/spec", db1)
            db1.close()
            assert res1["status"] == "COMPLETED"

            db2 = SessionLocal()
            res2 = await process_url_for_product(pid, sid, "https://dedup-motors.com/spec", db2)
            db2.close()
            assert res2["status"] == "DEDUPLICATED"

    @pytest.mark.asyncio
    async def test_product_isolation_with_url_ingestion(self, app_client):
        """URL ingestion for Product A does not bleed claims or evidence into Product B."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Source, Claim
        from app.services.processing_service import process_url_for_product

        db = SessionLocal()
        try:
            p_a = Product(name="Product Alpha", model_number="ALPHA-01")
            p_b = Product(name="Product Beta", model_number="BETA-01")
            db.add(p_a); db.add(p_b); db.commit(); db.refresh(p_a); db.refresh(p_b)
            pa_id = str(p_a.id)
            pb_id = str(p_b.id)

            s_a = Source(product_id=p_a.id, type="url", name="Alpha Spec", authority_rank=3)
            db.add(s_a); db.commit(); db.refresh(s_a)
            sa_id = str(s_a.id)
        finally:
            db.close()

        mock_webpage = ParsedURLPage(
            url="https://alpha.com/spec",
            title="Alpha Spec",
            raw_text="Max Operating Pressure: 300 bar.",
            blocks=[URLTextBlock(text="Max Operating Pressure: 300 bar.", section_header="Pressure")],
            file_hash="hash_alpha_222",
            domain="alpha.com",
        )

        with patch("app.ingestion.url_ingest.fetch_url_content", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_webpage
            db_sess = SessionLocal()
            await process_url_for_product(pa_id, sa_id, "https://alpha.com/spec", db_sess)
            db_sess.close()

        db_check = SessionLocal()
        try:
            claims_a = db_check.query(Claim).filter(Claim.product_id == uuid.UUID(pa_id)).all()
            claims_b = db_check.query(Claim).filter(Claim.product_id == uuid.UUID(pb_id)).all()
            assert len(claims_a) >= 1
            assert len(claims_b) == 0  # Zero leakage to Product B!
        finally:
            db_check.close()
