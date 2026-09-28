from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "ingest_status IN ('UPLOADED', 'CHUNKED', 'EMBEDDED', 'FAILED')",
            name="ck_documents_ingest_status",
        ),
        Index("idx_documents_policy_version_id", "policy_version_id"),
        Index("idx_documents_ingest_status", "ingest_status"),
        Index("idx_documents_content_hash", "content_hash"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    policy_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)
    storage_path = Column(String(1000), nullable=True)
    source = Column(String(255), nullable=True)
    content_hash = Column(String(64), nullable=True)
    page_count = Column(Integer, nullable=True)
    ingest_status = Column(String(50), nullable=False, default="UPLOADED", server_default=text("'UPLOADED'"))
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
