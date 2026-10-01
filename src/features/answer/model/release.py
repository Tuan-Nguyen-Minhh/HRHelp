"""Store a dispatch submit. A hold does not call this module."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import src.common.orm  # noqa: F401
from src.features.answer.model.dispatch import DRAFT_TYPES, DispatchResult
from src.features.answer.model.proposal import ProposalHandoff
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.recommendations import Recommendation


class DispatchError(Exception):
    """The submit cannot be stored. The caller leaves the proposal as a draft."""


async def save_submission(
    session: AsyncSession,
    case: Case,
    proposal: ProposalHandoff,
    result: DispatchResult,
) -> None:
    """Insert four pending drafts and move the case to legal review.

    The caller commits. A ``DispatchError`` is raised before any draft row is added.
    """
    kinds = tuple(item.draft_type for item in result.drafts)
    if kinds != DRAFT_TYPES or any(not item.title.strip() or not item.content.strip() for item in result.drafts):
        raise DispatchError("Bốn nháp không đúng loại hoặc bị trùng.")
    recommendation = await session.get(Recommendation, proposal.recommendation_id)
    if recommendation is None or recommendation.status != "DRAFT":
        raise DispatchError("Đề xuất không còn DRAFT nên không đẩy ticket.")
    if case.status != "ANALYZED":
        raise DispatchError("Hồ sơ không còn ANALYZED nên không đẩy ticket.")
    if case.created_by is None:
        raise DispatchError("Hồ sơ không có người tạo để ghi nháp.")
    for item in result.drafts:
        session.add(
            CaseDraft(
                id=uuid4(),
                case_id=case.id,
                recommendation_id=proposal.recommendation_id,
                draft_type=item.draft_type,
                title=item.title,
                content=item.content,
                status="PENDING_REVIEW",
                created_by=case.created_by,
            )
        )
    recommendation.status = "PENDING_REVIEW"
    case.status = "PENDING_LEGAL"
    await session.flush()
