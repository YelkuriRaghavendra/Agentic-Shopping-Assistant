"""Order event routes — URL registration only."""
from fastapi import APIRouter
from app.api.controllers.order_events_controller import order_events_controller
from app.api.dto.order_events import OrderIndexResponse

router = APIRouter(prefix="/orders", tags=["Order Embeddings"])

router.post("/index", response_model=OrderIndexResponse)(order_events_controller.index_order)
