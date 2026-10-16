"""Notification writes must accept every event produced by manager rejection."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.notifications import Notification


@pytest.mark.parametrize("event,valid", [("MANAGER_REJECTED", True), ("UNKNOWN_EVENT", False)])
def test_notification_event_constraint(event, valid):
    engine = create_engine("sqlite://")
    try:
        Notification.__table__.create(engine)
        with Session(engine) as session:
            notice = Notification(
                id=uuid4(),
                user_id=uuid4(),
                case_id=uuid4(),
                event=event,
                title="Quản lý không duyệt hồ sơ",
                body="Cần HR bổ sung mức xử lý.",
            )
            session.add(notice)
            if valid:
                session.commit()
                assert session.get(Notification, notice.id).event == event
            else:
                with pytest.raises(IntegrityError, match="ck_notifications_event"):
                    session.commit()
    finally:
        engine.dispose()
