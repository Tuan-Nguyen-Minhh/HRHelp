"""Minutes formatting must not remove Vietnamese letters or join separate facts."""

import pytest

from src.common.minutes_text import clean_minutes_text
from src.features.answer.model.case_tools import _minutes_bullets
from src.features.assessment.agent import _clean_minutes_text


@pytest.mark.parametrize("cleaner", [clean_minutes_text, _clean_minutes_text])
@pytest.mark.parametrize("value", ["Thông tin dự án ra ngoài.", "Chưa đủ căn cứ để đề xuất một mức.", "Đã xác minh."])
def test_sentence_endings_are_preserved(cleaner, value):
    assert cleaner(value) == value


def test_bullets_preserve_separation_deduplicate_and_format_dates():
    text = "- Thông tin dự án ra ngoài.\n- Thông tin dự án ra ngoài.\n- Ngày xảy ra: 2026-11-04."
    assert _minutes_bullets(text) == ["  - Thông tin dự án ra ngoài.", "  - Ngày xảy ra: 04/11/2026."]


def test_only_heading_prefixes_are_removed():
    assert clean_minutes_text("II. NỘI DUNG\nThông tin dự án ra ngoài.\nChưa đủ căn cứ để đề xuất một mức.") == (
        "NỘI DUNG\nThông tin dự án ra ngoài.\nChưa đủ căn cứ để đề xuất một mức."
    )
