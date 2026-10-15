"""Display formatting that preserves Vietnamese sentence endings and line breaks."""

import re


def clean_minutes_text(value: str) -> str:
    text = re.sub(r"[ \t]*-?[ \t]*Chunk[_\s-]*id\s*:\s*[\w-]+", "", value or "", flags=re.IGNORECASE)
    text = re.sub(r"[*_`]+", "", text)
    # Roman prefixes only occur at the start of a line. A Unicode word boundary
    # can occur inside 'ngoài.' or 'mức.' and must never be used to remove them.
    text = re.sub(r"^[ \t]*[IVXLCDM]{1,6}\.[ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", r"\3/\2/\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
