"""Short-term memory for one case conversation."""

from sqlalchemy import Column, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin


class ConversationMemory(TimestampMixin, Base):
    __tablename__ = "conversation_memories"

    __table_args__ = (
        Index("uq_conversation_memories_conversation_id", "conversation_id", unique=True),
        Index("idx_conversation_memories_pending_action", "pending_action"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=False, default="", server_default=text("''"))
    open_questions = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    pending_fact_keys = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    last_user_intent = Column(String(80), nullable=True)
    pending_action = Column(String(80), nullable=True)
    recent_messages = Column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
