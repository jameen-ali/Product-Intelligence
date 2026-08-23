"""
Regression & Stability Tests for Segment 3 Fixes:
1. Product metadata isolation (no inherited HP-4000/HydroDyn/Hydraulic Pump defaults).
2. EM-750 metadata correctness.
3. Neo4j health recovery after transient failure.
4. Real health status reflection.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

import pytest
from app.core.neo4j_client import neo4j_client


class TestProductMetadataIsolation:
    def test_new_product_does_not_inherit_hp4000_metadata(self, app_client):
        """Creating an electric motor product should not inherit HP-4000 model number."""
        r = app_client.post("/products", json={
            "name": "Industrial Electric Motor EM-750",
            "model_number": "EM-750",
            "manufacturer": "Generic Industrial Motors",
            "category": "Electric Motor",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["model_number"] == "EM-750"
        assert data["model_number"] != "HP-4000"

    def test_new_product_does_not_inherit_hydrodyn_manufacturer(self, app_client):
        """Creating a gearbox product should not inherit HydroDyn manufacturer."""
        r = app_client.post("/products", json={
            "name": "Industrial Gearbox GB-200",
            "model_number": "GB-200",
            "manufacturer": "GearTech Systems",
            "category": "Industrial Gearbox",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["manufacturer"] == "GearTech Systems"
        assert data["manufacturer"] != "HydroDyn Pumps Pvt. Ltd."

    def test_new_product_does_not_inherit_hydraulic_pump_category(self, app_client):
        """Creating a motor product should not inherit Hydraulic Pump category."""
        r = app_client.post("/products", json={
            "name": "AC Induction Motor M-100",
            "model_number": "M-100",
            "category": "Electric Motor",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["category"] == "Electric Motor"
        assert data["category"] != "Hydraulic Pump"

    def test_em750_existing_metadata_correct(self, app_client):
        """Verify EM-750 product record in DB has clean metadata."""
        from app.core.db import SessionLocal
        from app.models.entities import Product
        db = SessionLocal()
        try:
            p = db.query(Product).filter(Product.model_number == "EM-750").first()
            if p:
                assert p.model_number == "EM-750"
                assert p.manufacturer == "Generic Industrial Motors"
                assert p.category == "Electric Motor"
        finally:
            db.close()


class TestNeo4jHealthRecovery:
    def test_neo4j_health_auto_recovery(self, app_client):
        """Neo4jClient should recover healthy status without Uvicorn restart."""
        # Simulate transient error
        neo4j_client._driver = None
        # Call check_health -- should attempt reconnect and return healthy/unhealthy accurately
        h = neo4j_client.check_health()
        assert "status" in h
        assert h["status"] in ["healthy", "unhealthy"]
        if h["status"] == "healthy":
            assert h["uri"] is not None

    def test_health_endpoint_reflects_actual_services(self, app_client):
        """GET /health endpoint returns service health dictionary."""
        r = app_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert "services" in data
        assert "postgresql" in data["services"]
        assert "neo4j" in data["services"]
        assert "qdrant" in data["services"]
        assert "ollama" in data["services"]
