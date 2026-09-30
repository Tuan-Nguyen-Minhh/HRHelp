from sqlalchemy import Column, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base


class PermissionRole(Base):
    __tablename__ = "permission_roles"

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_permission_roles_role_permission"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
