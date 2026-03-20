"""
Document repository.
All document + knowledge-source DB operations live here.
"""
import uuid
from sqlalchemy import select, update, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.document import Document
from app.db.models.sources import Source
from app.db.models.enums.document_enums import DocumentStatus, DocumentType
from app.db.repositories.base_repository import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(Document, db, "document_id")

    async def find_by_hash(self, content_hash: str) -> Document | None:
        result = await self._db.execute(
            select(Document).where(
                Document.content_hash == content_hash,
                Document.status == DocumentStatus.READY,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_product_id(self, product_id: str) -> list[Document]:
        result = await self._db.execute(
            select(Document).where(
                Document.product_id    == product_id,
                Document.document_type == DocumentType.PRODUCT,
            )
        )
        return result.scalars().all()

    async def delete_by_product_id(self, product_id: str) -> None:
        """Remove all existing docs for a product before re-ingesting."""
        await self._db.execute(
            delete(Document).where(
                Document.product_id    == product_id,
                Document.document_type == DocumentType.PRODUCT,
            )
        )

    async def set_status(self, doc_id: uuid.UUID, status: str) -> None:
        await self._db.execute(
            update(Document).where(Document.document_id == doc_id).values(status=status)
        )

    async def list_by_source(
        self,
        source_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        offset = (page - 1) * page_size
        total_result = await self._db.execute(
            select(func.count()).select_from(Document).where(Document.source_id == source_id)
        )
        total = total_result.scalar_one()
        docs_result = await self._db.execute(
            select(Document)
            .where(Document.source_id == source_id)
            .order_by(Document.created_at.desc())
            .offset(offset).limit(page_size)
        )
        return docs_result.scalars().all(), total


class KnowledgeSourceRepository(BaseRepository[Source]):
    def __init__(self, db: AsyncSession):
        super().__init__(Source, db, "source_id")

    async def list_all(self) -> list[Source]:
        result = await self._db.execute(
            select(Source).order_by(Source.created_at.desc())
        )
        return result.scalars().all()

    async def create(self, name: str, source_type: str, config: dict) -> Source:
        source = Source(
            source_name=name,
            source_type=source_type,
            source_config=config,
            created_by="system",
        )
        return await self.save(source)
