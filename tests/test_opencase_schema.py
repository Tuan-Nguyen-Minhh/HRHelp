from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.features.assessment.schemas import EmployeeInformation
from src.features.opencase.model.store import find_by_code
from src.features.opencase.schema import CasePatchRequest, CaseView, OpenCaseRequest
from src.features.recidivism.model import _priors
from src.models.cases import Case
from src.models.disciplinary_decisions import DisciplinaryDecision


def test_open_case_requires_the_incident_date():
    with pytest.raises(ValidationError):
        OpenCaseRequest(
            case_code="HR-01",
            employee_code="NV-01",
            employee_name="Nguyễn An",
            description="Nghỉ không phép",
        )


def test_open_case_strips_the_code():
    payload = OpenCaseRequest(
        case_code="  HR-01  ",
        employee_code="NV-01",
        employee_name="Nguyễn An",
        description="Nghỉ không phép",
        incident_date=date(2026, 3, 1),
    )
    assert payload.case_code == "HR-01"


def test_open_case_normalizes_identity_before_saving():
    payload = OpenCaseRequest(
        case_code="  case-010  ",
        employee_code=" nv-1152 ",
        employee_name=" nGUYỄN văn đức ",
        description="Nghỉ không phép",
        incident_date=date(2026, 3, 1),
    )
    assert payload.model_dump(include={"case_code", "employee_code", "employee_name"}) == {
        "case_code": "CASE-010",
        "employee_code": "NV-1152",
        "employee_name": "NGUYỄN VĂN ĐỨC",
    }
    assert payload.description == "Nghỉ không phép"


@pytest.mark.parametrize("model", [CasePatchRequest, EmployeeInformation])
def test_employee_edits_are_normalized(model):
    payload = model(employee_name=" nguyễn Văn c ", employee_code=" emp-009 ")
    assert payload.employee_name == "NGUYỄN VĂN C"
    assert payload.employee_code == "EMP-009"
    assert model(employee_name=None, employee_code=None).employee_name is None


def test_legacy_case_view_normalizes_identity_for_display():
    payload = CaseView(
        case_id=uuid4(),
        conversation_id=None,
        case_code="hs-005",
        employee_code="nv-1152",
        employee_name="nguyen van c",
        description=None,
        incident_date=None,
        status="ANALYZED",
    )
    assert payload.case_code == "HS-005"
    assert payload.employee_name == "NGUYEN VAN C"
    assert payload.employee_code == "NV-1152"


@pytest.mark.parametrize("name", ["   ", 123, "a" * 256, "ß" * 128])
def test_normalized_identity_still_respects_validation(name):
    with pytest.raises(ValidationError):
        OpenCaseRequest(
            case_code="CASE-001",
            employee_code="NV-01",
            employee_name=name,
            description="Nghỉ không phép",
            incident_date=date(2026, 3, 1),
        )


@pytest.mark.asyncio
async def test_duplicate_check_finds_legacy_codes_with_different_casing():
    engine = create_engine("sqlite://")
    try:
        Case.__table__.create(engine)
        with Session(engine) as stored:
            legacy = Case(id=uuid4(), created_by=uuid4(), case_code="case-010", status="OPEN")
            stored.add(legacy)
            stored.commit()
            session = SimpleNamespace(execute=AsyncMock(side_effect=stored.execute))
            assert await find_by_code(session, "CASE-010") is legacy
            assert await find_by_code(session, "case-010") is legacy
            assert await find_by_code(session, "CASE-011") is None
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_uppercase_employee_code_still_matches_legacy_history():
    engine = create_engine("sqlite://")
    try:
        Case.__table__.create(engine)
        DisciplinaryDecision.__table__.create(engine)
        with Session(engine) as stored:
            legacy = Case(
                id=uuid4(), created_by=uuid4(), case_code="case-010", employee_code="emp-009", status="DECIDED"
            )
            stored.add(legacy)
            stored.flush()
            decision = DisciplinaryDecision(
                id=uuid4(), case_id=legacy.id, decision_code="QD-001", sanction_type="REPRIMAND",
                summary="Đi muộn", issued_by=uuid4(),
            )
            stored.add(decision)
            stored.commit()
            session = SimpleNamespace(execute=AsyncMock(side_effect=stored.execute))
            current = Case(id=uuid4(), employee_code="EMP-009")
            assert await _priors(session, current, set()) == [(legacy, decision)]
            current.employee_code = "EMP-010"
            assert await _priors(session, current, set()) == []
    finally:
        engine.dispose()
