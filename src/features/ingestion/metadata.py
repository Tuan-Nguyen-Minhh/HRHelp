"""Derive the step3 document identity from the metadata step2 extracted.

The offline pipeline keeps this identity in ``DOC_ID_MAP`` (a hand-edited dict).
An upload supplies it at call time instead, so ``parse_document`` never needs to
learn about the new document.
"""

import re

from data_pipeline_steps.step3.hierarchy_parser import DOC_ID_MAP

_TYPE_ENUM = {
    "BỘ LUẬT": "BO_LUAT",
    "LUẬT": "LUAT",
    "NGHỊ ĐỊNH": "NGHI_DINH",
    "NGHỊ QUYẾT": "NGHI_QUYET",
    "QUYẾT ĐỊNH": "QUYET_DINH",
    "THÔNG TƯ": "THONG_TU",
    "CHỈ THỊ": "CHI_THI",
    "NỘI QUY": "NOI_QUY",
}

_FORM_ENUM = {
    "VĂN BẢN HỢP NHẤT": "VAN_BAN_HOP_NHAT",
    "VĂN BẢN NỘI BỘ": "VAN_BAN_NOI_BO",
}

_CODE_PREFIX = {
    "BO_LUAT": "BL",
    "LUAT": "L",
    "NGHI_DINH": "ND",
    "NGHI_QUYET": "NQ",
    "QUYET_DINH": "QD",
    "THONG_TU": "TT",
    "CHI_THI": "CT",
    "NOI_QUY": "NQLD",
    "VAN_BAN_KHAC": "VB",
}

# policies.policy_type CHECK allows LAW/DECREE/CIRCULAR/INTERNAL_RULE/PRECEDENT
# or NULL. Types without a natural mapping fall through to NULL.
_POLICY_TYPE = {
    "BO_LUAT": "LAW",
    "LUAT": "LAW",
    "NGHI_DINH": "DECREE",
    "THONG_TU": "CIRCULAR",
    "NOI_QUY": "INTERNAL_RULE",
}


def _slug(value: str) -> str:
    ascii_only = re.sub(r"[^0-9A-Za-z]+", "_", value)
    return re.sub(r"_+", "_", ascii_only).strip("_").upper()


def document_type_enum(label: str | None) -> str:
    return _TYPE_ENUM.get((label or "").strip().upper(), "VAN_BAN_KHAC")


def document_form_enum(label: str | None) -> str:
    return _FORM_ENUM.get((label or "").strip().upper(), "VAN_BAN_GOC")


def policy_type_for(document_type: str) -> str | None:
    return _POLICY_TYPE.get(document_type)


def _base_code(document_type: str, number: str | None, stem: str) -> str:
    prefix = _CODE_PREFIX.get(document_type, "VB")
    if number:
        core = _slug(number)
        if core:
            return f"{prefix}{core}"[:60]
    return (f"{prefix}_{_slug(stem)}"[:60]) or prefix


def build_doc_info(metadata: dict, stem: str, taken: set[str]) -> dict:
    """Return a DOC_ID_MAP-shaped entry with a ``doc_code`` unique among ``taken``."""
    document_type = document_type_enum(metadata.get("document_type"))
    document_form = document_form_enum(metadata.get("document_form"))
    number = (metadata.get("document_number") or "").strip() or None
    document_id = number or f"{_CODE_PREFIX.get(document_type, 'VB')}/{stem}"

    base = _base_code(document_type, number, stem)
    reserved = {k.upper() for k in DOC_ID_MAP}
    reserved |= {str(v.get("doc_code", "")).upper() for v in DOC_ID_MAP.values()}
    reserved |= {code.upper() for code in taken}
    doc_code = base
    counter = 2
    while doc_code.upper() in reserved:
        doc_code = f"{base}_{counter}"
        counter += 1

    return {
        "document_id": document_id,
        "document_type": document_type,
        "document_form": document_form,
        "doc_code": doc_code,
        "max_article": 0,
    }
