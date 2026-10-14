"""Unit tests for the admin document-ingestion feature.

No database and no network: conversion, metadata derivation, the in-memory
step3 chunking, and the guard are all pure enough to exercise directly.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from data_pipeline_steps.step3.hierarchy_parser import parse_document
from src.common.errors import AppError
from src.core.security.guards import _check_permissions, require_permissions
from src.core.security.rbac import PermissionEnum
from src.features.ingestion import converter, metadata, pipeline
from src.features.ingestion.writer import _build_chunks, content_hash, embedding_input

CLEANED = """# NGHỊ ĐỊNH QUY ĐỊNH VỀ THỬ VIỆC

- **Số hiệu:** 999/2026/NĐ-CP
- **Hình thức:** VĂN BẢN GỐC
- **Loại văn bản:** NGHỊ ĐỊNH

---

## Chương I. QUY ĐỊNH CHUNG

#### Điều 1. Phạm vi điều chỉnh

1. Nghị định này quy định về thời gian thử việc.
2. Thời gian thử việc do hai bên thỏa thuận.

#### Điều 2. Đối tượng áp dụng

Người sử dụng lao động và người lao động.
"""

STEP2_META = {
    "document_number": "999/2026/NĐ-CP",
    "document_type": "NGHỊ ĐỊNH",
    "document_form": "VĂN BẢN GỐC",
    "document_title": "Nghị định quy định về thử việc",
}


def _doc_info() -> dict:
    return {
        "document_id": "999/2026/NĐ-CP",
        "document_type": "NGHI_DINH",
        "document_form": "VAN_BAN_GOC",
        "doc_code": "ND999_2026",
        "max_article": 0,
    }


def test_converter_passes_through_text_formats():
    assert converter.to_markdown("a.md", "# Tiêu đề".encode()) == "# Tiêu đề"
    assert converter.to_markdown("a.txt", "xin chào".encode()) == "xin chào"


def test_converter_rejects_unsupported_and_empty():
    with pytest.raises(AppError):
        converter.to_markdown("a.exe", b"binary")
    with pytest.raises(AppError):
        converter.to_markdown("a.md", b"")


def test_build_doc_info_maps_labels_and_is_unique():
    info = metadata.build_doc_info(STEP2_META, "stem", set())
    assert info["document_type"] == "NGHI_DINH"
    assert info["document_form"] == "VAN_BAN_GOC"
    assert info["document_id"] == "999/2026/NĐ-CP"
    assert info["doc_code"].startswith("ND999")

    other = metadata.build_doc_info(STEP2_META, "stem", {info["doc_code"]})
    assert other["doc_code"] != info["doc_code"]


def test_parse_document_accepts_dynamic_doc_info():
    tree = parse_document(CLEANED, "not_in_the_map", _doc_info())
    assert tree.document_id == "999/2026/NĐ-CP"
    assert tree.doc_code == "ND999_2026"

    with pytest.raises(ValueError):
        parse_document(CLEANED, "not_in_the_map")


def test_chunk_produces_article_chunks_with_breadcrumb():
    ingested = pipeline.chunk(CLEANED, "stem", _doc_info())
    assert ingested.chunks, "expected at least one chunk"
    assert all(chunk.chunk_id.startswith("ND999_2026") for chunk in ingested.chunks)
    assert {chunk.metadata.article_number for chunk in ingested.chunks} >= {1, 2}
    assert ingested.chunks[0].header_context.startswith("[VĂN BẢN: 999/2026/NĐ-CP]")


def test_build_chunks_maps_into_official_columns():
    ingested = pipeline.chunk(CLEANED, "stem", _doc_info())
    rows = _build_chunks(uuid4(), ingested)
    assert len(rows) == len(ingested.chunks)

    first = rows[0]
    assert first.article == "1"
    assert first.section in {"ARTICLE", "CLAUSE", "POINT"}
    assert first.section_title == ingested.chunks[0].header_context
    assert first.embedding is None
    assert first.chunk_metadata["legal_chunk_id"] == ingested.chunks[0].chunk_id
    assert first.chunk_metadata["legal_document_id"] == "999/2026/NĐ-CP"
    # Promoted-to-column keys must not be duplicated inside the JSONB.
    assert "article_number" not in first.chunk_metadata
    assert embedding_input(first) == f"{first.section_title}\n{first.content}"


def test_content_hash_is_stable_sha256():
    assert content_hash("abc") == content_hash("abc")
    assert len(content_hash("abc")) == 64


def test_document_manage_guard_requires_the_permission():
    assert PermissionEnum.DOCUMENT_MANAGE.value == "document:manage"
    _check_permissions({"permissions": ["document:manage"]}, (PermissionEnum.DOCUMENT_MANAGE,))
    with pytest.raises(HTTPException) as exc:
        _check_permissions({"permissions": []}, (PermissionEnum.DOCUMENT_MANAGE,))
    assert exc.value.status_code == 403
    # The controller wires this exact guard onto every route.
    assert callable(require_permissions(PermissionEnum.DOCUMENT_MANAGE))
