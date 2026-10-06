"""Directed cross-reference graph over ``document_chunks`` — the live corpus.

One row is one edge: a chunk whose text cites another provision.

    source_chunk_id ────► target_chunk_id
    the chunk holding      the provision that was
    the citation           cited

Port of ``legal_chunk_references`` (599 edges, produced by
``data_pipeline_steps/step3/cross_reference_resolver.py``) onto the HR-side
corpus the runtime actually reads. ``legal_*`` stays untouched as the
build-time copy; this table is what application code may join against.

Column decisions that are easy to get wrong:

* **Surrogate ``ref_id`` PK, not the source id.** ``target_chunk_id`` is
  nullable for provisions outside the corpus (a BLLD article that cites the
  Social Insurance Law), so no natural column set is unique on its own.
* **``target_chunk_id`` FK is ``ON DELETE SET NULL``, mirroring
  ``recommendation_citations``.** Losing a target chunk must not delete the
  fact that a citation existed; the edge degrades into an external reference
  and stays readable via ``target_doc`` / ``article`` / ``clause`` / ``point``.
* **``source_chunk_id`` is ``ON DELETE CASCADE``.** A citation with no source
  has no meaning.
* **``NULLS NOT DISTINCT`` on the unique key.** Two refs can otherwise differ
  only in whether ``clause``/``point`` is NULL, which would let a duplicate in.
  Requires PostgreSQL 15+; the project already relies on it in
  ``policy_versions``.
* **Forward and reverse traversal are both indexed.** The unique key leads with
  ``source_chunk_id`` and serves outgoing lookups; the extra composite index
  on ``(target_chunk_id, source_chunk_id)`` serves "who cites this article".
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.db.base import Base
from src.models.timestamp import TimestampMixin

# Set together: needs_review is exactly "needs_reason is not None". Keeping two
# independently writable flags is how they drift apart.
NEEDS_REASON_BOUNDARY = "BOUNDARY"
NEEDS_REASON_UNRESOLVED = "UNRESOLVED"
ALL_NEEDS_REASONS = (NEEDS_REASON_BOUNDARY, NEEDS_REASON_UNRESOLVED)


class ChunkReference(TimestampMixin, Base):
    __tablename__ = "chunk_references"

    __table_args__ = (
        CheckConstraint("confidence IN ('HIGH', 'LOW')", name="ck_chunk_references_confidence"),
        CheckConstraint(
            "needs_reason IN ('BOUNDARY', 'UNRESOLVED')",
            name="ck_chunk_references_needs_reason",
        ),
        UniqueConstraint(
            "source_chunk_id",
            "target_chunk_id",
            "target_doc",
            "article",
            "clause",
            "point",
            "rule",
            name="uq_chunk_references",
            postgresql_nulls_not_distinct=True,
        ),
        # Reverse traversal: "which chunks cite article N of document D".
        Index("ix_chunk_references_target_source", "target_chunk_id", "source_chunk_id"),
    )

    ref_id = Column(Integer, primary_key=True, autoincrement=True)
    source_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Where the citation points, independent of whether that chunk exists here.
    target_doc = Column(String(128), nullable=False)
    article = Column(Integer, nullable=False)
    clause = Column(Integer, nullable=True)
    point = Column(String(16), nullable=True)

    # How the edge was found. Bo Luat cites come as EXPLICIT / EXPLICIT_SELF /
    # DEFAULT_SELF / LIST_EXPANSION / SCOPED_CHAPEAU / QUOTED_EXTERNAL /
    # AMBIGUOUS_LUAT_NAY / BOUNDARY_CHECK — see the resolver for the definitions.
    rule = Column(String(64), nullable=False)
    # HIGH for every rule the resolver trusts; LOW for AMBIGUOUS_LUAT_NAY and
    # BOUNDARY_CHECK. A traversal should skip LOW.
    confidence = Column(String(16), nullable=False)
    needs_review = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    needs_reason = Column(String(16), nullable=True)
