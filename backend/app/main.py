import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import engine, Base, SessionLocal
from app.core.qdrant_client import qdrant_wrapper
from app.core.neo4j_client import neo4j_client

from app.api import health, products, processing, evidence, conflicts, reviews, graph, exports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipte.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing IPTE Backend...")
    # Initialize PostgreSQL tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("PostgreSQL tables created or verified.")
    except Exception as e:
        logger.warning(f"Could not initialize PostgreSQL tables: {e}")

    # Seed core attributes and demonstration products
    try:
        from app.services.seed_service import seed_demo_data
        db = SessionLocal()
        try:
            seed_demo_data(db)
            logger.info("Core attributes and demonstration products seeded.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not seed demo data: {e}")

    # Ensure Qdrant collection exists
    try:
        qdrant_wrapper.ensure_collection()
    except Exception as e:
        logger.warning(f"Could not connect to Qdrant at startup: {e}")

    # Connect Neo4j
    try:
        neo4j_client.connect()
    except Exception as e:
        logger.warning(f"Could not connect to Neo4j at startup: {e}")

    yield

    logger.info("Shutting down IPTE Backend...")
    neo4j_client.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health.router)
app.include_router(products.router)
app.include_router(processing.router)
app.include_router(evidence.router)
app.include_router(conflicts.router)
app.include_router(reviews.router)
app.include_router(graph.router)
app.include_router(exports.router)

@app.get("/")
def root():
    return {
        "message": "Welcome to Industrial Product Truth Engine (IPTE) API",
        "docs": "/docs",
        "health": "/health"
    }
