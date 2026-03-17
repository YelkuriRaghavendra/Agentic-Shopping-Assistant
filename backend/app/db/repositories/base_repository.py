"""
Base repository.
Provides shared CRUD helpers used by all concrete repositories.
Repositories are the ONLY layer that touches SQLAlchemy directly.
"""

from typing import TypeVar, Generic
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic base — concrete repos inherit and specialise."""

    def __init__(self, model: type[T], db: AsyncSession):
        self._model = model
        self._db = db

    async def get_by_id(self, record_id) -> T | None:
        result = await self._db.execute(
            select(self._model).where(self._model.id == record_id)
        )
        return result.scalar_one_or_none()

    async def save(self, instance: T) -> T:
        self._db.add(instance)
        await self._db.flush()
        return instance

    async def delete(self, instance: T) -> None:
        await self._db.delete(instance)
        await self._db.flush()

    async def count(self) -> int:
        result = await self._db.execute(select(func.count()).select_from(self._model))
        return result.scalar_one()

    def mark_modified(self, instance: T, column: str) -> None:
        """
        Must be called after mutating a JSONB column in-place.
        SQLAlchemy won't detect the change otherwise.
        """
        flag_modified(instance, column)
