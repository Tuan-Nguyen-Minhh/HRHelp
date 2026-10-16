"""Exercise the real PostgreSQL rejection transaction, rolling back all test rows.

Run against a migrated local database with P029_RUN_DB_TESTS=1.
"""

import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.common.deps import get_session
from src.core.config import settings
from src.core.security.auth_handler import AuthHandler
from src.core.security.tokens import claims_for_role
from src.main import app
from src.models.audit_logs import AuditLog
from src.models.case_drafts import CaseDraft
from src.models.cases import Case
from src.models.notifications import Notification
from src.models.recommendations import Recommendation
from src.models.users import User


@pytest.mark.skipif(os.getenv("P029_RUN_DB_TESTS") != "1", reason="Requires migrated local PostgreSQL")
@pytest.mark.asyncio
async def test_manager_rejection_commits_packet_notice_and_idempotent_response():
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI)
    suffix = uuid4().hex
    case_id, hr_id, manager_id, recommendation_id = (uuid4() for _ in range(4))
    previous_overrides = app.dependency_overrides.copy()
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                    autoflush=False,
                ) as session:
                    session.add_all(
                        [
                            User(id=hr_id, email=f"hr-{suffix}@example.invalid", password_hash="test-only", role="HR"),
                            User(
                                id=manager_id,
                                email=f"manager-{suffix}@example.invalid",
                                password_hash="test-only",
                                role="MANAGER",
                            ),
                        ]
                    )
                    await session.flush()
                    session.add(
                        Case(id=case_id, case_code=f"TEST-REJECT-{suffix}", created_by=hr_id, status="APPROVED")
                    )
                    await session.flush()
                    session.add(
                        Recommendation(
                            id=recommendation_id,
                            case_id=case_id,
                            recommendation="Synthetic test report",
                            status="APPROVED",
                            sanction_type=None,
                        )
                    )
                    await session.flush()
                    session.add_all(
                        [
                            CaseDraft(
                                case_id=case_id,
                                recommendation_id=recommendation_id,
                                created_by=hr_id,
                                draft_type=kind,
                                title=kind,
                                content="Synthetic test document",
                                status="APPROVED",
                            )
                            for kind in ("MINUTES", "EXPLANATION_REQUEST", "DECISION", "TICKET")
                        ]
                    )
                    await session.commit()

                    async def test_session():
                        yield session

                    app.dependency_overrides[get_session] = test_session
                    token = AuthHandler.create_access_token(
                        {"user_id": str(manager_id), "is_active": True},
                        **claims_for_role("MANAGER"),
                    )
                    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"test-reject-{suffix}"}
                    url = f"/api/v1/manager/cases/{case_id}/reject"
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                        first = await client.post(url, json={"comment": "Chưa xác định mức xử lý"}, headers=headers)
                        assert first.status_code == 200, first.text
                        assert first.json() == {"case_id": str(case_id), "status": "REJECTED"}
                        replay = await client.post(url, json={"comment": "Chưa xác định mức xử lý"}, headers=headers)
                        assert replay.status_code == 200
                        assert replay.json() == first.json()

                    assert (await session.get(Case, case_id)).status == "REJECTED"
                    assert (await session.get(Recommendation, recommendation_id)).status == "REJECTED"
                    drafts = (await session.scalars(select(CaseDraft).where(CaseDraft.case_id == case_id))).all()
                    assert len(drafts) == 4 and all(row.status == "REJECTED" for row in drafts)
                    notices = (await session.scalars(select(Notification).where(Notification.case_id == case_id))).all()
                    assert len(notices) == 1
                    assert notices[0].event == "MANAGER_REJECTED"
                    assert notices[0].user_id == hr_id
                    assert "Chưa xác định mức xử lý" in notices[0].body
                    assert (
                        await session.scalar(
                            select(func.count())
                            .select_from(AuditLog)
                            .where(
                                AuditLog.case_id == case_id,
                                AuditLog.action == "MANAGER_REJECTED",
                            )
                        )
                        == 1
                    )
            finally:
                await transaction.rollback()

        async with AsyncSession(engine) as verification:
            assert await verification.get(Case, case_id) is None
            assert await verification.get(User, hr_id) is None
            assert await verification.get(User, manager_id) is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        await engine.dispose()
