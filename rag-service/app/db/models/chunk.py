from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Text, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.models.base import Base
import uuid


class Chunk(Base):

    __tablename__ = "chunks"

    chunk_id:    Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int]             = mapped_column(Integer, nullable=False)
    content:     Mapped[str]             = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None]      = mapped_column(Integer, nullable=True)
    character_start:  Mapped[int | None] = mapped_column(Integer, nullable=True)
    character_end:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_metadata:   Mapped[dict]       = mapped_column("metadata", JSONB, nullable=False, default=dict)

    document:   Mapped["Document"]         = relationship(back_populates="chunks")
    embeddings: Mapped[list["Embedding"]]  = relationship(back_populates="chunk", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_metadata",    "metadata", postgresql_using="gin"),
    )
