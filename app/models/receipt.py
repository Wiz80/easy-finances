"""Receipt model for storing parsed receipt data and metadata."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.expense import Expense


class Receipt(Base):
    """
    Receipt stores parsed receipt data from images/PDFs.
    Links to an expense and contains OCR output and metadata.
    """

    __tablename__ = "receipt"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Storage
    blob_uri: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # MinIO or S3 URI for original image/PDF
    content_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )  # SHA256 hash for deduplication
    
    # Parsed Data
    parsed_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # Structured receipt data
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # OCR raw text
    raw_markdown: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # LlamaParse markdown output
    
    # OCR Metadata
    ocr_provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # llamaparse, tesseract, etc.
    ocr_confidence: Mapped[float | None] = mapped_column(nullable=True)
    parse_status: Mapped[str] = mapped_column(
        String(50), default="success"
    )  # success, partial, failed
    
    # File Metadata
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # image/jpeg, pdf, etc.
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    expense: Mapped["Expense"] = relationship("Expense", back_populates="receipt")

    def __repr__(self) -> str:
        return (
            f"<Receipt(id={self.id}, expense_id={self.expense_id}, "
            f"provider={self.ocr_provider}, status={self.parse_status})>"
        )

