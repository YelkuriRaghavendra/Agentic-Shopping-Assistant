"""Retrieve routes — URL registration only."""
from fastapi import APIRouter
from app.api.controllers.retrieve_controller import retrieve_controller
from app.api.dto.retrieve import RetrievalResponse

router = APIRouter(prefix="/retrieve", tags=["Retrieval"])

router.post("", response_model=RetrievalResponse)(retrieve_controller.retrieve)
