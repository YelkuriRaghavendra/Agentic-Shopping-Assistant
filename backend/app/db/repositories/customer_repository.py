"""
Customer repository.
All customer-related DB operations live here.
"""

import uuid
from datetime import datetime, UTC
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.models import Customer
from app.db.repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository[Customer]):

    def __init__(self, db: AsyncSession):
        super().__init__(Customer, db)

    async def find_by_external_id(self, external_id: str) -> Customer | None:
        result = await self._db.execute(
            select(Customer).where(Customer.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> Customer | None:
        result = await self._db.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        external_id: str | None = None,
        email: str | None = None,
        name: str | None = None,
        phone: str | None = None,
        profile: dict | None = None,
    ) -> Customer:
        customer = Customer(
            external_id=external_id,
            email=email,
            name=name,
            phone=phone,
            profile=profile or {},
            status="active",
        )
        return await self.save(customer)

    async def update_profile(
        self,
        customer_id: uuid.UUID,
        profile: dict,
    ) -> None:
        """
        Merge new profile data into existing profile.
        Uses DB-level update to avoid race conditions.
        """
        customer = await self.get_by_id(customer_id)
        if not customer:
            return
        merged = {**customer.profile, **profile}
        customer.profile = merged
        customer.updated_at = datetime.now(UTC)
        self.mark_modified(customer, "profile")

    async def set_status(self, customer_id: uuid.UUID, status: str) -> None:
        await self._db.execute(
            update(Customer)
            .where(Customer.id == customer_id)
            .values(status=status, updated_at=datetime.now(UTC))
        )
