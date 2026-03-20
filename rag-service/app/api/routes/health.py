from fastapi import APIRouter

router   = APIRouter(tags=["Health"])

@router.get("/health", include_in_schema=False)
async def health():
    return {
        "status":  "ok"
    }
