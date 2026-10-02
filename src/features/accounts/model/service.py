"""Create, correct, and retire HR and legal accounts. Other roles stay untouched."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.clock import utc_now
from src.common.errors import AppError
from src.core.security.auth_handler import AuthHandler
from src.features.accounts.schema import StaffAccount, StaffCreate, StaffList, StaffUpdate
from src.models.roles import Role
from src.models.user_roles import UserRole
from src.models.users import User

_STAFF = frozenset({"HR", "LEGAL"})


async def list_staff(session: AsyncSession, actor: User) -> StaffList:
    """Active and locked HR and legal accounts. Retired rows stay out of the list."""
    _require_manager(actor)
    rows = list(
        (
            await session.scalars(
                select(User)
                .where(User.role.in_(tuple(_STAFF)), User.deleted_at.is_(None))
                .order_by(User.role.asc(), User.email.asc())
            )
        ).all()
    )
    return StaffList(users=[_view(row) for row in rows])


async def create_staff(session: AsyncSession, actor: User, payload: StaffCreate) -> StaffAccount:
    """Open an HR or legal account. The new user signs in with the password given here."""
    _require_manager(actor)
    existing = await session.scalar(select(User).where(func.lower(User.email) == payload.email))
    if existing is not None and existing.deleted_at is None:
        raise AppError(409, "Email đã được đăng ký.", code="CONFLICT")
    if existing is not None:
        raise AppError(409, "Email này thuộc tài khoản đã xóa. Hãy dùng email khác.", code="CONFLICT")
    user = User(
        email=payload.email,
        password_hash=AuthHandler.get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
        await _assign_staff_role(session, user, payload.role, actor.id)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "Email đã được đăng ký.", code="CONFLICT") from exc
    return _view(user)


async def update_staff(session: AsyncSession, actor: User, user_id: UUID, payload: StaffUpdate) -> StaffAccount:
    """Change name, email, role, password, or the lock on one HR or legal account."""
    _require_manager(actor)
    user = await _staff(session, user_id)
    if payload.email is not None and payload.email != user.email:
        taken = await session.scalar(select(User.id).where(func.lower(User.email) == payload.email, User.id != user.id))
        if taken is not None:
            raise AppError(409, "Email đã được đăng ký.", code="CONFLICT")
        user.email = payload.email
    if payload.password is not None:
        user.password_hash = AuthHandler.get_password_hash(payload.password)
    if "full_name" in payload.model_fields_set:
        user.full_name = payload.full_name or None
    if payload.role is not None and payload.role != user.role:
        user.role = payload.role
        await _assign_staff_role(session, user, payload.role, actor.id)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "Email đã được đăng ký.", code="CONFLICT") from exc
    await session.refresh(user)
    return _view(user)


async def delete_staff(session: AsyncSession, actor: User, user_id: UUID) -> StaffAccount:
    """Retire the account. Cases that person opened stay on the record."""
    _require_manager(actor)
    user = await _staff(session, user_id)
    user.is_active = False
    user.deleted_at = utc_now()
    await session.commit()
    await session.refresh(user)
    return _view(user)


def _require_manager(actor: User) -> None:
    if actor.role != "MANAGER":
        raise AppError(403, "Chỉ quản lý được tạo tài khoản HR và pháp chế.", code="FORBIDDEN")


async def _staff(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None or user.role not in _STAFF:
        raise AppError(404, "Không tìm thấy tài khoản HR hoặc pháp chế.", code="NOT_FOUND")
    return user


async def _assign_staff_role(session: AsyncSession, user: User, role_name: str, assigned_by: UUID) -> None:
    """Keep a single HR or LEGAL link. Other role rows are left in place."""
    role = await session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        return
    staff_ids = set((await session.scalars(select(Role.id).where(Role.name.in_(tuple(_STAFF))))).all())
    links = list((await session.scalars(select(UserRole).where(UserRole.user_id == user.id))).all())
    has_target = False
    for link in links:
        if link.role_id == role.id:
            has_target = True
            continue
        if link.role_id in staff_ids:
            await session.delete(link)
    if not has_target:
        session.add(UserRole(user_id=user.id, role_id=role.id, assigned_by=assigned_by))
    await session.flush()


def _view(user: User) -> StaffAccount:
    return StaffAccount(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=bool(user.is_active),
    )
