"""Retrieve routes — URL registration only."""
from fastapi import APIRouter, Depends

from app.api.controllers.retrieve_controller import retrieve_controller
from app.api.dto.retrieve import RetrievalResponse
from app.core.security import verify_api_key

router = APIRouter(prefix="/retrieve", tags=["Retrieval"], dependencies=[Depends(verify_api_key)])

router.post("", response_model=RetrievalResponse)(retrieve_controller.retrieve)
