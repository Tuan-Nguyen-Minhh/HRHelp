from datetime import date

import pytest
from pydantic import ValidationError

from src.features.opencase.schema import OpenCaseRequest


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
