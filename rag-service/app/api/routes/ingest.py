"""Ingest routes — URL registration only."""
from fastapi import APIRouter, Depends

from app.api.controllers.ingest_controller import ingest_controller
from app.api.dto.ingest import IngestResponse, BulkIngestResponse, JobsResponse
from app.core.security import verify_api_key

router = APIRouter(prefix="/ingest", tags=["Ingestion"], dependencies=[Depends(verify_api_key)])

router.post("/product", response_model=IngestResponse)(ingest_controller.ingest_product)
router.post("/products/bulk", response_model=BulkIngestResponse)(ingest_controller.ingest_products_bulk)
router.get("/jobs/{job_id}", response_model=JobsResponse)(ingest_controller.get_job)
