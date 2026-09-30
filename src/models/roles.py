from sqlalchemy import CheckConstraint, Column, String, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    __table_args__ = (
        CheckConstraint(
            "name IN ('HR', 'MANAGER', 'LEGAL')",
            name="ck_roles_name",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200), nullable=True)
