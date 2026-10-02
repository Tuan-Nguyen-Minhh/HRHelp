"""Admin routes for policy versions and document retry."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.knowledge.model import create_version, get_document, list_versions, retry_document
from src.features.knowledge.schema import DocumentView, VersionCreate, VersionListResponse, VersionView
from src.models.users import User

router = APIRouter(tags=["Kho văn bản"])


@router.post("/policies/{policy_id}/versions", response_model=VersionView, status_code=status.HTTP_201_CREATED)
async def post_version(
    policy_id: UUID,
    payload: VersionCreate,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> VersionView:
    return await create_version(session, actor, policy_id, payload)


@router.get("/policies/{policy_id}/versions", response_model=VersionListResponse)
async def get_versions(
    policy_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> VersionListResponse:
    del actor
    return await list_versions(session, policy_id)


@router.get("/documents/{document_id}", response_model=DocumentView)
async def read_document(
    document_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> DocumentView:
    del actor
    return await get_document(session, document_id)


@router.post("/documents/{document_id}/retry", response_model=DocumentView)
async def post_retry(
    document_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> DocumentView:
    return await retry_document(session, actor, document_id)
