"""Base repository — shared CRUD helpers for all concrete repos."""
from typing import TypeVar, Generic, Type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession, pk_attr: str = "id"):
        self._model   = model
        self._db      = db
        self._pk_attr = pk_attr

    async def get_by_id(self, record_id) -> T | None:
        pk = getattr(self._model, self._pk_attr)
        result = await self._db.execute(
            select(self._model).where(pk == record_id)
        )
        return result.scalar_one_or_none()

    async def save(self, instance: T) -> T:
        self._db.add(instance)
        await self._db.flush()
        return instance

    async def bulk_create(self, instances: list[T]) -> None:
        for instance in instances:
            self._db.add(instance)
        await self._db.flush()

