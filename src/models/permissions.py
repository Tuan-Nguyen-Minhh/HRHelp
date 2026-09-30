from sqlalchemy import CheckConstraint, Column, String, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    __table_args__ = (
        CheckConstraint(
            "name IN ('case:open', 'case:read', 'case:chat', 'case:confirm', 'answer:read')",
            name="ck_permissions_name",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(100), unique=True, nullable=False)
    resource = Column(String(50), nullable=True)
    action = Column(String(50), nullable=True)
