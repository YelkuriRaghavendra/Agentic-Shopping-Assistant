from sqlalchemy import Text, Integer, DateTime, ForeignKey, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.enums.job_enums import JobStatus
from sqlalchemy.dialects.postgresql import UUID
from app.db.models.base import Base
from datetime import datetime
import uuid


class Jobs(Base):

    __tablename__ = "jobs"

    job_id:        Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id:   Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, unique=True)
    status:        Mapped[JobStatus]  = mapped_column(SAEnum(JobStatus, name="job_status_enum"), nullable=False, default=JobStatus.QUEUED)
    chunks_total:  Mapped[int]        = mapped_column(Integer, nullable=False, default=0)
    chunks_done:   Mapped[int]        = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="jobs")

    __table_args__ = (Index("idx_jobs_status", "status"),)
