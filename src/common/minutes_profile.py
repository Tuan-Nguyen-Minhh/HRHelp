"""Shared minutes letterhead for the preview and Word export.

Company/city: https://www.vingroup.net/vi/lien-he
The two representatives are fictional demo people, as requested by the user.
The document number is this application's convention, not Vingroup's official one.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.common.clock import vietnam_date


class MinutesProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    company_name: str = "TẬP ĐOÀN VINGROUP – CÔNG TY CP"
    city: str = "Hà Nội"
    document_number: str = ""
    meeting_location: str = "Phòng họp Tập đoàn Vingroup, Hà Nội"
    leadership_name: str = "NGUYỄN MINH KHANG"
    leadership_position: str = "Phó Tổng giám đốc"
    hr_name: str = "TRẦN THU HÀ"
    hr_position: str = "Giám đốc Nhân sự"
    hr_department: str = "Ban Nhân sự"


def minutes_profile(case_code: str | None, created_at: datetime | None) -> MinutesProfile:
    created_date = vietnam_date(created_at)
    year = str(created_date.year) if created_date else "...."
    code = (case_code or "....").strip().upper()
    return MinutesProfile(document_number=f"{code}/{year}/BB-XLKL")
