from sqlalchemy import String, Integer, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.models.base import Base
from pgvector.sqlalchemy import Vector
import uuid


class LLMModel(Base):

    __tablename__ = "llm_models"

    llm_model_id:  Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    llm_name:      Mapped[str]       = mapped_column(String(100), nullable=False, unique=True)
    provider:      Mapped[str]       = mapped_column(String(50),  nullable=False)
    dimensions:    Mapped[int]       = mapped_column(Integer,     nullable=False)
    is_active:     Mapped[bool]      = mapped_column(Boolean,     nullable=False, default=True)

    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="model")


class Embedding(Base):

    __tablename__ = "embeddings"

    embedding_id:   Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id:       Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("chunks.chunk_id", ondelete="CASCADE"), nullable=False)
    llm_model_id:   Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("llm_models.llm_model_id"), nullable=False)
    embedding:      Mapped[list[float]]     = mapped_column(Vector(1536), nullable=False)

    chunk: Mapped["Chunk"]      = relationship(back_populates="embeddings")
    model: Mapped["LLMModel"]  = relationship(back_populates="embeddings")

    __table_args__ = (
        UniqueConstraint("chunk_id", "llm_model_id", name="uq_embedding_chunk_model"),
        Index("idx_embeddings_llm_model_id", "llm_model_id"),
    )
