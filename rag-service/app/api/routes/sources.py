"""Source routes — URL registration only."""
from fastapi import APIRouter, Depends

from app.api.controllers.source_controller import source_controller
from app.api.dto.sources import KnowledgeSourceResponse
from app.core.security import verify_api_key

router = APIRouter(
    prefix="/sources",
    tags=["Knowledge Sources"],
    dependencies=[Depends(verify_api_key)],
)

router.post("",            response_model=KnowledgeSourceResponse)(source_controller.create)
router.get("",             response_model=list[KnowledgeSourceResponse])(source_controller.list_all)
router.get("/{source_id}", response_model=KnowledgeSourceResponse)(source_controller.get)
