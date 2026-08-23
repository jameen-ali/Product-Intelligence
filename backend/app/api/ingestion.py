from fastapi import APIRouter

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

@router.get("/status")
def ingestion_status():
    return {"status": "ready"}
