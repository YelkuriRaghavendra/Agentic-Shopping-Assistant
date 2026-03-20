from sqlalchemy import String, Text, Integer, ForeignKey, Index, Enum as SAEnum
from app.db.models.enums.document_enums import DocumentStatus, DocumentType
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.models.base import Base
import uuid


class Document(Base):

    __tablename__ = "documents"

    document_id:  Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id:    Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("sources.source_id", ondelete="CASCADE"), nullable=False)
    product_id:   Mapped[str]             = mapped_column(Text, nullable=True)
    document_type:Mapped[DocumentType]    = mapped_column(SAEnum(DocumentType, name="document_type_enum"), nullable=False, default=DocumentType.PRODUCT)
    content:      Mapped[str]             = mapped_column(Text, nullable=True)
    content_hash: Mapped[str]             = mapped_column(String(64), nullable=False)
    status:       Mapped[DocumentStatus]  = mapped_column(SAEnum(DocumentStatus, name="document_status_enum"), nullable=False, default=DocumentStatus.PENDING)
    token_count:  Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chunk_counts:  Mapped[int]      = mapped_column(Integer, nullable=False, default=0)
    document_metadata:    Mapped[dict]    = mapped_column("metadata", JSONB, nullable=False, default=dict)


    source:        Mapped["Source"]   = relationship(back_populates="documents")
    chunks:        Mapped[list["Chunk"]]       = relationship(back_populates="document", cascade="all, delete-orphan")
    jobs: Mapped["Jobs | None"] = relationship(back_populates="document", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_source_id", "source_id"),
        Index("idx_documents_status",    "status"),
        Index("idx_documents_document_type",  "document_type"),
        Index("idx_documents_hash",      "content_hash"),
        Index("idx_documents_metadata",  "metadata", postgresql_using="gin"),
    )
