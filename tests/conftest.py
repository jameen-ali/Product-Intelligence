"""
Test configuration: ensure SQLite test DB tables are created before tests run.
Overrides the DB engine with a fresh in-memory SQLite instance for isolation.
"""
import sys
import os

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Override PostgreSQL URL before any app imports to force SQLite test DB
os.environ["POSTGRES_URL"] = "sqlite:///./ipte_test.db"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all DB tables in a fresh test SQLite database."""
    from app.core.db import engine, Base
    from app.models import entities  # ensure all models are registered
    engine.dispose()
    try:
        if os.path.exists("./ipte_test.db"):
            os.remove("./ipte_test.db")
    except Exception:
        pass
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        if os.path.exists("./ipte_test.db"):
            os.remove("./ipte_test.db")
    except Exception:
        pass



@pytest.fixture(scope="session")
def app_client(setup_test_db):
    """Test client with lifespan context so attributes are seeded."""
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
