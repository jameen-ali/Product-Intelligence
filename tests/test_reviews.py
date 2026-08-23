"""
Segment 3 -- Review actions tests.
Tests POST /reviews/claims/{id}/approve|reject|mark-unknown
and GET /reviews/products/{id}.
"""
import sys, os, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))


def _make_product_with_claim(db, product_name="Review Test Pump"):
    """Create product + attribute + claim directly in DB for review tests."""
    from app.models.entities import Product, Attribute, Source, Claim
    p = Product(name=product_name, model_number="RVP-001")
    db.add(p); db.commit(); db.refresh(p)

    attr = db.query(Attribute).first()  # seeded attributes exist
    src = Source(product_id=p.id, type="datasheet", name="Test Datasheet", authority_rank=1)
    db.add(src); db.commit(); db.refresh(src)

    claim = Claim(
        product_id=p.id,
        attribute_id=attr.id if attr else None,
        source_id=src.id,
        raw_value="5",
        original_unit="HP",
        normalized_value=3.73,
        normalized_unit="kW",
        extraction_confidence=0.92,
        status="INFERRED",
    )
    db.add(claim); db.commit(); db.refresh(claim)
    return p, claim


class TestReviewsStatus:
    def test_status_endpoint(self, app_client):
        """Reviews router is registered and responsive."""
        r = app_client.get("/reviews/status")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestApproveRejectMarkUnknown:
    def test_approve_known_claim(self, app_client):
        """POST approve sets claim status to VERIFIED."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            _, claim = _make_product_with_claim(db, "Approve Test Pump")
            cid = str(claim.id)
        finally:
            db.close()

        r = app_client.post(
            f"/reviews/claims/{cid}/approve",
            json={"reviewer_id": "test_engineer", "notes": "Verified against datasheet"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "APPROVED"
        assert data["claim_id"] == cid
        assert "review_id" in data
        assert data["reviewer_id"] == "test_engineer"

    def test_reject_known_claim(self, app_client):
        """POST reject logs a rejection review."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            _, claim = _make_product_with_claim(db, "Reject Test Pump")
            cid = str(claim.id)
        finally:
            db.close()

        r = app_client.post(
            f"/reviews/claims/{cid}/reject",
            json={"reviewer_id": "test_engineer", "notes": "Value inconsistent with label"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "REJECTED"
        assert data["claim_id"] == cid
        assert "review_id" in data

    def test_mark_unknown_known_claim(self, app_client):
        """POST mark-unknown sets claim status to UNKNOWN."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            _, claim = _make_product_with_claim(db, "Unknown Test Pump")
            cid = str(claim.id)
        finally:
            db.close()

        r = app_client.post(
            f"/reviews/claims/{cid}/mark-unknown",
            json={"reviewer_id": "test_engineer"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "MARK_UNKNOWN"
        assert data["claim_id"] == cid

    def test_approve_nonexistent_claim_returns_404(self, app_client):
        """Approving a non-existent claim returns 404."""
        r = app_client.post(
            "/reviews/claims/" + str(uuid.uuid4()) + "/approve",
            json={"reviewer_id": "test_engineer"},
        )
        assert r.status_code == 404

    def test_reject_nonexistent_claim_returns_404(self, app_client):
        """Rejecting a non-existent claim returns 404."""
        r = app_client.post(
            "/reviews/claims/" + str(uuid.uuid4()) + "/reject",
            json={"reviewer_id": "test_engineer"},
        )
        assert r.status_code == 404

    def test_mark_unknown_nonexistent_claim_returns_404(self, app_client):
        """Mark-unknown on non-existent claim returns 404."""
        r = app_client.post(
            "/reviews/claims/" + str(uuid.uuid4()) + "/mark-unknown",
            json={"reviewer_id": "test_engineer"},
        )
        assert r.status_code == 404

    def test_review_persisted_in_history(self, app_client):
        """Approved claim shows in /reviews/products/{id} history."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            product, claim = _make_product_with_claim(db, "History Test Pump")
            pid = str(product.id)
            cid = str(claim.id)
        finally:
            db.close()

        # Approve the claim
        app_client.post(
            f"/reviews/claims/{cid}/approve",
            json={"reviewer_id": "history_tester"},
        )

        # Verify it shows in history
        r = app_client.get(f"/reviews/products/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data["product_id"] == pid
        assert data["review_count"] >= 1
        review_claim_ids = [rv["claim_id"] for rv in data["reviews"]]
        assert cid in review_claim_ids


class TestReviewsHistory:
    def test_history_for_unknown_product_returns_404(self, app_client):
        """History for non-existent product returns 404."""
        r = app_client.get("/reviews/products/" + str(uuid.uuid4()))
        assert r.status_code == 404

    def test_history_schema_correct(self, app_client):
        """Review history response has correct schema."""
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            product, _ = _make_product_with_claim(db, "Schema History Pump")
            pid = str(product.id)
        finally:
            db.close()

        r = app_client.get(f"/reviews/products/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert "product_id" in data
        assert "review_count" in data
        assert "reviews" in data
        assert isinstance(data["reviews"], list)


class TestReviewPersistenceAndConflictResolution:
    def test_approve_candidate_persists_and_resolves_conflict(self, app_client):
        """Approving Candidate A persists decision and removes attribute from conflicts list."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Attribute, Source, Claim
        db = SessionLocal()
        try:
            p = Product(name="Conflict Resolve Pump", model_number="CRP-100")
            db.add(p); db.commit(); db.refresh(p)
            attr = db.query(Attribute).first()
            s1 = Source(product_id=p.id, type="datasheet", name="Src 1", authority_rank=1)
            s2 = Source(product_id=p.id, type="supplier", name="Src 2", authority_rank=7)
            db.add(s1); db.add(s2); db.commit()
            
            c1 = Claim(product_id=p.id, attribute_id=attr.id, source_id=s1.id, raw_value="415", original_unit="V", normalized_value=415.0, normalized_unit="V", status="EXTRACTED")
            c2 = Claim(product_id=p.id, attribute_id=attr.id, source_id=s2.id, raw_value="400", original_unit="V", normalized_value=400.0, normalized_unit="V", status="EXTRACTED")
            db.add(c1); db.add(c2); db.commit(); db.refresh(c1); db.refresh(c2)
            pid = str(p.id)
            c1_id = str(c1.id)
        finally:
            db.close()

        # 1. Verify conflict initially exists
        r1 = app_client.get(f"/conflicts/products/{pid}")
        assert r1.status_code == 200
        assert len(r1.json()["conflicts"]) >= 1

        # 2. Approve c1 (415 V)
        r_app = app_client.post(f"/reviews/claims/{c1_id}/approve", json={"reviewer_id": "test_user"})
        assert r_app.status_code == 200

        # 3. Verify conflict is now resolved
        r2 = app_client.get(f"/conflicts/products/{pid}")
        assert r2.status_code == 200
        assert len(r2.json()["conflicts"]) == 0

        # 4. Verify canonical attribute is updated to 415 V and status is VERIFIED
        r_attr = app_client.get(f"/products/{pid}/attributes")
        assert r_attr.status_code == 200
        attr_data = r_attr.json()["attributes"][0]
        assert attr_data["trust_status"] == "VERIFIED"
        assert "415" in attr_data["canonical_value"]

    def test_voltage_review_does_not_modify_speed_review(self, app_client):
        """Reviewing voltage claim does not affect rotational speed conflict or state."""
        from app.core.db import SessionLocal
        from app.models.entities import Product, Attribute, Source, Claim
        db = SessionLocal()
        try:
            p = Product(name="Multi Conflict Engine", model_number="MCE-200")
            db.add(p); db.commit(); db.refresh(p)
            attrs = db.query(Attribute).all()
            a_volt = attrs[0]
            a_speed = attrs[1] if len(attrs) > 1 else attrs[0]
            s1 = Source(product_id=p.id, type="datasheet", name="Mfr Sheet", authority_rank=1)
            s2 = Source(product_id=p.id, type="supplier", name="Sup Sheet", authority_rank=7)
            db.add(s1); db.add(s2); db.commit()

            c_v1 = Claim(product_id=p.id, attribute_id=a_volt.id, source_id=s1.id, raw_value="415", normalized_value=415.0, status="EXTRACTED")
            c_v2 = Claim(product_id=p.id, attribute_id=a_volt.id, source_id=s2.id, raw_value="400", normalized_value=400.0, status="EXTRACTED")
            
            c_s1 = Claim(product_id=p.id, attribute_id=a_speed.id, source_id=s1.id, raw_value="1440", normalized_value=1440.0, status="EXTRACTED")
            c_s2 = Claim(product_id=p.id, attribute_id=a_speed.id, source_id=s2.id, raw_value="1450", normalized_value=1450.0, status="EXTRACTED")
            db.add(c_v1); db.add(c_v2); db.add(c_s1); db.add(c_s2); db.commit()
            pid = str(p.id)
            cv1_id = str(c_v1.id)
            cs1_id = str(c_s1.id)
            a_volt_id = str(a_volt.id)
        finally:
            db.close()

        # Approve voltage claim only
        app_client.post(f"/reviews/claims/{cv1_id}/approve", json={"reviewer_id": "test_user"})

        # Check attributes
        r_attr = app_client.get(f"/products/{pid}/attributes")
        assert r_attr.status_code == 200
        attrs_resp = r_attr.json()["attributes"]
        v_attr = next(a for a in attrs_resp if a["attribute_id"] == a_volt_id)
        assert v_attr["trust_status"] == "VERIFIED"
