"""Admin routes for uploading source documents into the runtime corpus.

Guarded by ``document:manage``, which only ADMIN holds — the same permission the
existing ``knowledge`` feature uses. The whole surface is admin-only by role.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.deps import get_actor, get_session
from src.common.errors import AppError
from src.core.config import settings
from src.core.security.guards import require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.ingestion import service
from src.features.ingestion.schema import IngestionDocumentList, IngestionDocumentView
from src.models.users import User

router = APIRouter(prefix="/admin/ingestion", tags=["Nạp văn bản"])


@router.post("/documents", response_model=IngestionDocumentView, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
    file: Annotated[UploadFile, File(...)],
    effective_from: Annotated[date | None, Form()] = None,
) -> IngestionDocumentView:
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError(413, f"Tệp vượt quá {settings.MAX_UPLOAD_MB}MB.", code="FILE_TOO_LARGE")
    return await service.create_from_upload(
        session, actor, filename=file.filename or "", data=data, effective_from=effective_from
    )


@router.get("/documents", response_model=IngestionDocumentList)
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> IngestionDocumentList:
    return await service.list_documents(session)


@router.get("/documents/{document_id}", response_model=IngestionDocumentView)
async def get_document(
    document_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> IngestionDocumentView:
    return await service.get_document(session, document_id)


@router.post("/documents/{document_id}/retry", response_model=IngestionDocumentView)
async def retry_document(
    document_id: UUID,
    actor: Annotated[User, Depends(get_actor)],
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[dict, Depends(require_permissions(PermissionEnum.DOCUMENT_MANAGE))],
) -> IngestionDocumentView:
    return await service.retry_document(session, actor, document_id)
