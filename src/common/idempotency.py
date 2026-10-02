"""Replay a critical POST when the client sends the same Idempotency-Key."""

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.models.idempotency_keys import IdempotencyKey


@dataclass(frozen=True)
class Replay:
    """A response that was already committed for this key."""

    status_code: int
    body: dict


def request_hash(payload: dict) -> str:
    """Hash the canonical JSON of a request body."""
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def claim(
    session: AsyncSession,
    *,
    actor_id: UUID,
    route: str,
    key: str | None,
    body_hash: str,
) -> Replay | None:
    """Reserve a key, or return the previous result.

    A missing key means the caller does not want replay protection.
    A completed key with the same body is returned. A different body conflicts.
    """
    if not key:
        return None
    existing = await _find(session, actor_id, route, key)
    if existing is not None:
        return _decide(existing, body_hash)
    row = IdempotencyKey(
        actor_id=actor_id,
        route=route,
        idempotency_key=key,
        request_hash=body_hash,
        status="IN_PROGRESS",
    )
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError:
        existing = await _find(session, actor_id, route, key)
        if existing is None:
            raise AppError(409, "Khóa idempotency đang được xử lý.", code="IDEMPOTENCY_CONFLICT") from None
        return _decide(existing, body_hash)
    return None


async def abandon(
    session: AsyncSession,
    *,
    actor_id: UUID,
    route: str,
    key: str | None,
) -> None:
    """Drop an in-progress key so a failed attempt can be retried."""
    if not key:
        return
    row = await _find(session, actor_id, route, key)
    if row is not None and row.status != "COMPLETED":
        await session.delete(row)
        await session.flush()


async def complete(
    session: AsyncSession,
    *,
    actor_id: UUID,
    route: str,
    key: str | None,
    status_code: int,
    body: dict,
) -> None:
    """Store the response that a later retry must receive."""
    if not key:
        return
    row = await _find(session, actor_id, route, key)
    if row is None:
        return
    row.status = "COMPLETED"
    row.status_code = status_code
    row.response_body = body
    await session.flush()


async def _find(session: AsyncSession, actor_id: UUID, route: str, key: str) -> IdempotencyKey | None:
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.actor_id == actor_id,
        IdempotencyKey.route == route,
        IdempotencyKey.idempotency_key == key,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _decide(row: IdempotencyKey, body_hash: str) -> Replay:
    if row.request_hash != body_hash:
        raise AppError(
            409,
            "Idempotency-Key đã dùng cho một nội dung khác.",
            code="IDEMPOTENCY_CONFLICT",
        )
    if row.status != "COMPLETED" or row.response_body is None or row.status_code is None:
        raise AppError(409, "Yêu cầu cùng khóa đang được xử lý.", code="IDEMPOTENCY_CONFLICT")
    return Replay(status_code=row.status_code, body=dict(row.response_body))
