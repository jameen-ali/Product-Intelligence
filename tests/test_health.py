import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    json_data = response.json()
    assert "Industrial Product Truth Engine" in json_data["message"]

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.json()
    assert "status" in json_data
    assert "services" in json_data
    assert "postgresql" in json_data["services"]
    assert "neo4j" in json_data["services"]
    assert "qdrant" in json_data["services"]
    assert "ollama" in json_data["services"]
