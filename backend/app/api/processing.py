import os
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.entities import Product, Source, ProcessingJob
from app.services.processing_service import (
    process_pdf_for_product, process_url_for_product,
    process_excel_for_product, process_image_for_product
)
from app.ingestion.url_ingest import validate_url, fetch_url_content
from app.ingestion.excel_ingest import validate_excel_file
from app.ingestion.image_ingest import validate_image_file

router = APIRouter(prefix="/processing", tags=["Processing"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class ProcessURLRequest(BaseModel):
    source_id: str
    url: str


@router.get("/status")
def processing_status():
    return {"status": "ready"}


@router.post("/products/{product_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def process_product(
    product_id: uuid.UUID,
    source_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF and immediately process it through the full pipeline.
    Returns processing result synchronously (suitable for demo).
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for this endpoint")

    # Save file
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Create processing job
    job = ProcessingJob(
        product_id=product_id,
        status="PROCESSING",
        current_step="pdf_parse",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Run pipeline
    try:
        result = await process_pdf_for_product(
            product_id=str(product_id),
            source_id=source_id,
            pdf_path=str(save_path),
            db=db,
        )
        job.status = result.get("status", "COMPLETED")
        job.current_step = "done"
        db.commit()
        return {"job_id": str(job.id), "result": result}
    except Exception as e:
        job.status = "FAILED"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    finally:
        # Clean up temp file
        try:
            os.remove(save_path)
        except Exception:
            pass


@router.post("/products/{product_id}/process-url", status_code=status.HTTP_202_ACCEPTED)
async def process_product_url(
    product_id: uuid.UUID,
    req: ProcessURLRequest,
    db: Session = Depends(get_db),
):
    """
    Ingest a website URL using Crawl4AI and process it through the full truth pipeline.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    is_valid, err_msg = validate_url(req.url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid URL: {err_msg}")

    # Ensure source exists or create default URL source
    source = db.query(Source).filter(Source.id == uuid.UUID(req.source_id)).first()
    if not source:
        source = Source(
            id=uuid.UUID(req.source_id),
            product_id=product_id,
            type="url",
            name="Website Specification Page",
            authority_rank=3,
        )
        db.add(source)
        db.commit()

    job = ProcessingJob(
        product_id=product_id,
        status="PROCESSING",
        current_step="url_fetch",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        result = await process_url_for_product(
            product_id=str(product_id),
            source_id=req.source_id,
            url=req.url,
            db=db,
        )
        job.status = result.get("status", "COMPLETED")
        job.current_step = "done"
        db.commit()
        return {"job_id": str(job.id), "result": result}
    except Exception as e:
        job.status = "FAILED"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"URL Ingestion failed: {e}")


@router.post("/products/{product_id}/process-excel", status_code=status.HTTP_202_ACCEPTED)
async def process_product_excel(
    product_id: uuid.UUID,
    source_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV, XLSX, or XLSM catalog file and process it through the full truth pipeline.
    Each row/cell with recognized attributes becomes a Claim with sheet/row/column provenance.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Read file content to check size
    content = await file.read()
    size_bytes = len(content)

    is_valid, err_msg = validate_excel_file(file.filename or "", file.content_type or "", size_bytes)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid file: {err_msg}")

    ext = Path(file.filename).suffix.lower().lstrip(".")

    # Save to disk
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(content)

    job = ProcessingJob(product_id=product_id, status="PROCESSING", current_step="excel_parse")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        result = await process_excel_for_product(
            product_id=str(product_id),
            source_id=source_id,
            file_path=str(save_path),
            file_type=ext,
            db=db,
        )
        job.status = result.get("status", "COMPLETED")
        job.current_step = "done"
        db.commit()
        return {"job_id": str(job.id), "result": result}
    except Exception as e:
        job.status = "FAILED"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Excel processing failed: {e}")
    finally:
        try:
            import os
            os.remove(save_path)
        except Exception:
            pass


@router.post("/products/{product_id}/process-image", status_code=status.HTTP_202_ACCEPTED)
async def process_product_image(
    product_id: uuid.UUID,
    source_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a PNG, JPG, JPEG, or WEBP nameplate image.
    Runs PaddleOCR, extracts attribute claims with OCR confidence and bounding box provenance.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    source = db.query(Source).filter(Source.id == uuid.UUID(source_id)).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    content = await file.read()
    size_bytes = len(content)

    is_valid, err_msg = validate_image_file(file.filename or "", file.content_type or "", size_bytes)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {err_msg}")

    save_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(content)

    job = ProcessingJob(product_id=product_id, status="PROCESSING", current_step="ocr")
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        result = await process_image_for_product(
            product_id=str(product_id),
            source_id=source_id,
            file_path=str(save_path),
            db=db,
        )
        job.status = result.get("status", "COMPLETED")
        job.current_step = "done"
        db.commit()
        return {"job_id": str(job.id), "result": result}
    except Exception as e:
        job.status = "FAILED"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Image OCR processing failed: {e}")
    finally:
        try:
            import os
            os.remove(save_path)
        except Exception:
            pass
