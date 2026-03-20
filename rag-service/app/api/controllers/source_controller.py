"""
Knowledge Source controller — HTTP boundary only.
Validates input, calls repository, returns response.
"""
import uuid
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dto.sources import KnowledgeSourceCreate, KnowledgeSourceResponse
from app.db.session import get_db
from app.db.repositories import KnowledgeSourceRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class SourceController:

    async def create(
        self,
        request: KnowledgeSourceCreate,
        db: AsyncSession = Depends(get_db),
    ) -> KnowledgeSourceResponse:
        repository = KnowledgeSourceRepository(db)
        source = await repository.create(
            name=request.name,
            source_type=request.source_type,
            config=request.config,
        )
        await db.commit()
        await db.refresh(source)
        logger.info("source.created", source_id=str(source.source_id), name=source.source_name)
        return KnowledgeSourceResponse.model_validate(source)

    async def get(
        self,
        source_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
    ) -> KnowledgeSourceResponse:
        repository = KnowledgeSourceRepository(db)
        source = await repository.get_by_id(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Knowledge source not found.")
        return KnowledgeSourceResponse.model_validate(source)

    async def list_all(
        self,
        db: AsyncSession = Depends(get_db),
    ) -> list[KnowledgeSourceResponse]:
        repository = KnowledgeSourceRepository(db)
        sources = await repository.list_all()
        return [KnowledgeSourceResponse.model_validate(source) for source in sources]


source_controller = SourceController()
