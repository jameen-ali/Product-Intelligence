"""
API integration tests for Segment 2 vertical slice.
These tests use `app_client` from conftest.py which runs the full lifespan
so tables are created and core attributes are seeded.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))


def test_root(app_client):
    r = app_client.get("/")
    assert r.status_code == 200

def test_health(app_client):
    r = app_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "services" in data
    assert "postgresql" in data["services"]
    assert "neo4j" in data["services"]
    assert "qdrant" in data["services"]

def test_create_product(app_client):
    r = app_client.post("/products", json={
        "name": "Test Hydraulic Pump",
        "manufacturer": "TestCo",
        "model_number": "TP-001",
        "category": "Hydraulic",
    })
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "Test Hydraulic Pump"

def test_list_products(app_client):
    r = app_client.get("/products")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_get_product(app_client):
    create_r = app_client.post("/products", json={
        "name": "Pump for Get Test",
        "manufacturer": "Co",
        "model_number": "PGT-1",
    })
    assert create_r.status_code == 201
    pid = create_r.json()["id"]

    r = app_client.get(f"/products/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid

def test_add_source_to_product(app_client):
    p = app_client.post("/products", json={"name": "Source Test Pump", "model_number": "STP-1"})
    assert p.status_code == 201
    pid = p.json()["id"]

    r = app_client.post(f"/products/{pid}/sources", json={
        "type": "datasheet",
        "name": "Manufacturer Datasheet",
        "authority_rank": 1,
    })
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["type"] == "datasheet"

def test_get_product_evidence_empty(app_client):
    p = app_client.post("/products", json={"name": "Evidence Test Pump"})
    assert p.status_code == 201
    pid = p.json()["id"]
    r = app_client.get(f"/products/{pid}/evidence")
    assert r.status_code == 200
    assert isinstance(r.json()["evidence"], list)

def test_get_product_attributes_empty(app_client):
    p = app_client.post("/products", json={"name": "Attr Test Pump"})
    assert p.status_code == 201
    pid = p.json()["id"]
    r = app_client.get(f"/products/{pid}/attributes")
    assert r.status_code == 200
    assert isinstance(r.json()["attributes"], list)
