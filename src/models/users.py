from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('HR', 'MANAGER', 'LEGAL', 'SIGNER', 'ADMIN')",
            name="ck_users_role",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="HR", server_default=text("'HR'"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("TRUE"))
    deleted_at = Column(DateTime, nullable=True)
