"""Convert an uploaded source file to Markdown, entirely in memory.

The bytes never touch the filesystem. ``.md``/``.txt`` are decoded directly;
``.docx``/``.pdf`` go through MarkItDown, the same converter the offline pipeline
uses by hand (``data_pipeline_steps/pipeline_design.md``, step 1).
"""

from io import BytesIO
from pathlib import Path

from src.common.errors import AppError

_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
_OFFICE_SUFFIXES = {".docx", ".pdf"}
_SUPPORTED = _TEXT_SUFFIXES | _OFFICE_SUFFIXES


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _office_to_markdown(filename: str, data: bytes, suffix: str) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError as exc:  # pragma: no cover - depends on deploy extras
        raise AppError(500, "Máy chủ thiếu thư viện chuyển đổi tệp (markitdown).", code="CONVERTER_UNAVAILABLE") from exc

    stream = BytesIO(data)
    # MarkItDown guesses the converter from the stream name, so keep the original.
    stream.name = filename
    try:
        result = MarkItDown().convert_stream(stream)
    except Exception as exc:
        raise AppError(422, f"Không đọc được tệp {suffix}.", code="CONVERT_FAILED") from exc

    text = (result.text_content or "").strip()
    if not text:
        raise AppError(422, "Tệp rỗng hoặc không trích được nội dung.", code="EMPTY_DOCUMENT")
    return text


def to_markdown(filename: str, data: bytes) -> str:
    """Return the Markdown text of an uploaded file, or raise ``AppError``."""
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED:
        shown = suffix or "(không có phần mở rộng)"
        raise AppError(
            422,
            f"Định dạng không hỗ trợ: {shown}. Chỉ nhận .docx, .pdf, .md, .txt.",
            code="UNSUPPORTED_FILE_TYPE",
        )
    if not data:
        raise AppError(422, "Tệp rỗng.", code="EMPTY_DOCUMENT")
    if suffix in _TEXT_SUFFIXES:
        return _decode(data)
    return _office_to_markdown(filename, data, suffix)
