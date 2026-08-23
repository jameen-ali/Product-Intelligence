"""
Segment 3 -- Conflict Detection tests.
Tests /conflicts/* endpoints and the conflict engine directly.
"""
import sys, os, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))


def _make_product(client, name="Conflict Test Pump"):
    r = client.post("/products", json={
        "name": name, "manufacturer": "TestCo",
        "model_number": "CTP-001", "category": "Hydraulic",
    })
    assert r.status_code == 201
    return r.json()["id"]


class TestConflictsStatus:
    def test_status_endpoint(self, app_client):
        """Conflicts router is registered and responsive."""
        r = app_client.get("/conflicts/status")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestConflictsForProduct:
    def test_empty_product_returns_no_conflicts(self, app_client):
        """Product with no claims has zero conflicts."""
        pid = _make_product(app_client, "No Claims Pump A")
        r = app_client.get(f"/conflicts/products/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data["product_id"] == pid
        assert data["conflict_count"] == 0
        assert data["conflicts"] == []

    def test_unknown_product_returns_404(self, app_client):
        """Unknown product UUID returns 404."""
        r = app_client.get("/conflicts/products/" + str(uuid.uuid4()))
        assert r.status_code == 404

    def test_response_schema_is_correct(self, app_client):
        """Response always contains product_id, conflict_count, conflicts list."""
        pid = _make_product(app_client, "Schema Check Pump A")
        r = app_client.get(f"/conflicts/products/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert "product_id" in data
        assert "conflict_count" in data
        assert "conflicts" in data
        assert isinstance(data["conflicts"], list)
        assert isinstance(data["conflict_count"], int)

    def test_conflict_count_non_negative(self, app_client):
        """conflict_count must always be >= 0."""
        pid = _make_product(app_client, "Non-Neg Pump A")
        r = app_client.get(f"/conflicts/products/{pid}")
        assert r.json()["conflict_count"] >= 0


class TestConflictEngine:
    def test_detect_conflicts_returns_list(self, app_client):
        """detect_conflicts_for_product always returns a list."""
        from app.core.db import SessionLocal
        from app.conflict.engine import detect_conflicts_for_product
        from app.models.entities import Product
        db = SessionLocal()
        try:
            p = Product(name="Engine Test Pump A", model_number="ETP-A1")
            db.add(p); db.commit(); db.refresh(p)
            result = detect_conflicts_for_product(p.id, db)
            assert isinstance(result, list)
        finally:
            db.close()

    def test_compute_confidence_single_claim_in_range(self):
        """Confidence for a single claim is in [0, 1]."""
        from app.conflict.engine import compute_confidence_for_attribute
        claims = [{"authority_rank": 1, "extraction_confidence": 0.95, "normalized_value": 3.73}]
        conf, breakdown = compute_confidence_for_attribute(claims, "INFERRED")
        assert 0.0 <= conf <= 1.0
        assert isinstance(breakdown, dict)
        assert len(breakdown) > 0

    def test_verified_confidence_geq_conflict(self):
        """VERIFIED status confidence >= CONFLICT with same claims."""
        from app.conflict.engine import compute_confidence_for_attribute
        claims = [
            {"authority_rank": 1, "extraction_confidence": 0.95, "normalized_value": 3.73},
            {"authority_rank": 2, "extraction_confidence": 0.90, "normalized_value": 3.73},
        ]
        conf_v, _ = compute_confidence_for_attribute(claims, "VERIFIED")
        conf_c, _ = compute_confidence_for_attribute(claims, "CONFLICT")
        assert conf_v >= conf_c

    def test_decision_reason_verified_not_empty(self):
        """Decision reason for VERIFIED is a non-empty string."""
        from app.conflict.engine import generate_decision_reason
        reason = generate_decision_reason("VERIFIED", 0.91, {}, 2, 1)
        assert isinstance(reason, str) and len(reason) > 10

    def test_decision_reason_conflict_not_empty(self):
        """Decision reason for CONFLICT is a non-empty string."""
        from app.conflict.engine import generate_decision_reason
        reason = generate_decision_reason("CONFLICT", 0.45, {}, 2, 2)
        assert isinstance(reason, str) and len(reason) > 10

    def test_breakdown_all_values_in_range(self):
        """All breakdown factor values are in [0, 1]."""
        from app.conflict.engine import compute_confidence_for_attribute
        claims = [{"authority_rank": 1, "extraction_confidence": 0.9, "normalized_value": 5.0}]
        _, breakdown = compute_confidence_for_attribute(claims, "INFERRED")
        for k, v in breakdown.items():
            assert 0.0 <= v <= 1.0, f"Factor {k} out of range: {v}"

    def test_confidence_stable_across_statuses(self):
        """Confidence is always [0, 1] for all trust statuses."""
        from app.conflict.engine import compute_confidence_for_attribute
        for status in ["VERIFIED", "INFERRED", "CONFLICT", "UNKNOWN"]:
            claims = [{"authority_rank": 3, "extraction_confidence": 0.7, "normalized_value": 1.5}]
            conf, _ = compute_confidence_for_attribute(claims, status)
            assert 0.0 <= conf <= 1.0
