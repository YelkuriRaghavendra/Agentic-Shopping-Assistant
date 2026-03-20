from app.db.models.enums.source_enums import SourceStatus, SourceType
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.models.base import Base
from datetime import datetime
import uuid

class Source(Base):

    __tablename__ = "sources"

    source_id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name:        Mapped[str]       = mapped_column(String(255), nullable=False)
    source_type:        Mapped[SourceType]   = mapped_column(SAEnum(SourceType, name="source_type_enum"), nullable=False)
    source_config:      Mapped[dict]         = mapped_column(JSONB, nullable=False, default=dict)
    status:             Mapped[SourceStatus] = mapped_column(SAEnum(SourceStatus, name="source_status_enum"), nullable=False, default=SourceStatus.ACTIVE)
    last_synced_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
