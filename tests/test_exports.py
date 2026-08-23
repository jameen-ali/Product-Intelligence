"""
Segment 3 -- Export tests.
Tests GET /exports/products/{id}/json and .../csv endpoints.
"""
import sys, os, uuid, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))


def _make_product_with_data(db, product_name="Export Test Pump"):
    """Create a product with a source and claim for export tests."""
    from app.models.entities import Product, Attribute, Source, Claim, Evidence, Document
    p = Product(name=product_name, model_number="EXP-001", manufacturer="ExportCo")
    db.add(p); db.commit(); db.refresh(p)

    src = Source(product_id=p.id, type="datasheet", name="Export Datasheet", authority_rank=1)
    db.add(src); db.commit(); db.refresh(src)

    attr = db.query(Attribute).first()
    if not attr:
        return p, None

    claim = Claim(
        product_id=p.id,
        attribute_id=attr.id,
        source_id=src.id,
        raw_value="5",
        original_unit="HP",
        normalized_value=3.73,
        normalized_unit="kW",
        extraction_confidence=0.92,
        status="VERIFIED",
    )
    db.add(claim); db.commit(); db.refresh(claim)

    ev = Evidence(
        claim_id=claim.id,
        text_snippet="Rated power output: 5 HP (3.73 kW)",
        page_number=3,
        section_header="Technical Specifications",
        content_type="table",
    )
    db.add(ev); db.commit()
    return p, claim


class TestExportsStatus:
    def test_status_endpoint(self, app_client):
        """Exports router is registered and responsive."""
        r = app_client.get("/exports/status")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestJsonExport:
    def test_json_export_empty_product(self, app_client):
        """Empty product exports valid JSON with zero attributes."""
        p = app_client.post("/products", json={"name": "Empty Export Pump"})
        assert p.status_code == 201
        pid = p.json()["id"]

        r = app_client.get(f"/exports/products/{pid}/json")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")

        data = r.json()
        assert "export_version" in data
        assert "product" in data
        assert "attributes" in data
        assert "meta" in data
        assert data["product"]["id"] == pid

    def test_json_export_meta_counts_valid(self, app_client):
        """meta counts in JSON export are non-negative integers."""
        p = app_client.post("/products", json={"name": "Meta Count Pump"})
        pid = p.json()["id"]
        r = app_client.get(f"/exports/products/{pid}/json")
        data = r.json()
        meta = data["meta"]
        assert meta["total_attributes"] >= 0
        assert meta["verified"] >= 0
        assert meta["inferred"] >= 0
        assert meta["conflict"] >= 0
        assert meta["unknown"] >= 0

    def test_json_export_with_claims(self, app_client):
        """JSON export includes claim data when claims exist."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            product, claim = _make_product_with_data(db, "JSON Claims Pump")
            pid = str(product.id)
        finally:
            db.close()

        r = app_client.get(f"/exports/products/{pid}/json")
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["total_attributes"] >= 1

    def test_json_export_product_info_correct(self, app_client):
        """JSON export product block has correct name and model."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            product, _ = _make_product_with_data(db, "Product Info Pump")
            pid = str(product.id)
        finally:
            db.close()

        r = app_client.get(f"/exports/products/{pid}/json")
        data = r.json()
        assert data["product"]["name"] == "Product Info Pump"
        assert data["product"]["model_number"] == "EXP-001"
        assert data["product"]["manufacturer"] == "ExportCo"

    def test_json_export_unknown_product_returns_404(self, app_client):
        """JSON export for unknown product returns 404."""
        r = app_client.get("/exports/products/" + str(uuid.uuid4()) + "/json")
        assert r.status_code == 404

    def test_json_export_content_disposition_header(self, app_client):
        """JSON export sets Content-Disposition attachment header."""
        p = app_client.post("/products", json={"name": "Disposition Test Pump"})
        pid = p.json()["id"]
        r = app_client.get(f"/exports/products/{pid}/json")
        assert r.status_code == 200
        disposition = r.headers.get("content-disposition", "")
        assert "attachment" in disposition


class TestCsvExport:
    def test_csv_export_empty_product(self, app_client):
        """Empty product exports valid CSV with header only."""
        p = app_client.post("/products", json={"name": "Empty CSV Pump"})
        pid = p.json()["id"]
        r = app_client.get(f"/exports/products/{pid}/csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        # Should have at least the header row
        lines = r.text.strip().splitlines()
        assert len(lines) >= 1  # header row present
        assert "attribute" in lines[0].lower() or "display_name" in lines[0].lower()

    def test_csv_export_with_claims_has_data_rows(self, app_client):
        """CSV export has data rows when claims exist."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            product, claim = _make_product_with_data(db, "CSV Claims Pump")
            pid = str(product.id)
        finally:
            db.close()

        r = app_client.get(f"/exports/products/{pid}/csv")
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) >= 2  # header + at least one data row

    def test_csv_export_unknown_product_returns_404(self, app_client):
        """CSV export for unknown product returns 404."""
        r = app_client.get("/exports/products/" + str(uuid.uuid4()) + "/csv")
        assert r.status_code == 404

    def test_csv_export_content_disposition_header(self, app_client):
        """CSV export sets Content-Disposition attachment header."""
        p = app_client.post("/products", json={"name": "CSV Disposition Pump"})
        pid = p.json()["id"]
        r = app_client.get(f"/exports/products/{pid}/csv")
        assert r.status_code == 200
        disposition = r.headers.get("content-disposition", "")
        assert "attachment" in disposition

    def test_csv_has_required_columns(self, app_client):
        """CSV header contains required columns."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            product, _ = _make_product_with_data(db, "Column Check Pump")
            pid = str(product.id)
        finally:
            db.close()

        r = app_client.get(f"/exports/products/{pid}/csv")
        assert r.status_code == 200
        header = r.text.strip().splitlines()[0]
        required_cols = ["attribute", "display_name", "canonical_value", "trust_status", "confidence"]
        for col in required_cols:
            assert col in header, f"Missing required column: {col}"
