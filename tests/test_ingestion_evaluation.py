"""Adversarial evaluator checks: boundary changes pass, actual losses fail."""

import copy
import hashlib
import json

import pytest

from eval.ingestion.build_dataset import build
from eval.ingestion.evaluate import ROOT, canonical, evaluate, validate_dataset


@pytest.fixture
def benchmark(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original source fixture")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    text = "The employer must create the register within 30 days, except when condition Y applies."
    dataset = {
        "schema_version": 1,
        "documents": [
            {
                "code": "DOC",
                "document_id": "POLICY-1",
                "document_type": "NOI_QUY",
                "source_path": "source.txt",
                "source_sha256": digest,
                "review_status": "draft",
                "expected_articles": [{"article": 3}],
            }
        ],
        "cases": [
            {
                "case_id": "C1",
                "document_code": "DOC",
                "article": 3,
                "review_status": "draft",
                "spans": [{"source_index": 1, "text": text, "clause": None, "point": None}],
                "references": [{"target_doc": "OTHER", "article": 12, "clause": 1, "point": None}],
                "reference_scope": "positive_only",
                "context_requirements": [],
            }
        ],
    }
    row = {
        "chunk_id": "A",
        "text": text,
        "header_context": "POLICY-1 > Điều 3: Registers",
        "metadata": {
            "document_id": "POLICY-1",
            "document_type": "NOI_QUY",
            "article_number": 3,
            "clause_number": None,
            "point_letter": None,
            "chunk_level": "ARTICLE",
        },
        "references": copy.deepcopy(dataset["cases"][0]["references"]),
    }
    return dataset, row, tmp_path


def score(benchmark, rows):
    dataset, _, root = benchmark
    return evaluate(dataset, {"DOC": rows}, root=root)


def test_original_and_arbitrary_midword_split_pass(benchmark):
    _, row, _ = benchmark
    assert score(benchmark, [row])["status"] == "pass"
    left, right = copy.deepcopy(row), copy.deepcopy(row)
    cut = row["text"].index("register") + 3
    left["text"], right["text"] = row["text"][:cut], row["text"][cut:]
    right["chunk_id"] = "B"
    result = score(benchmark, [left, right])
    assert result["status"] == "pass"
    assert result["cases"][0]["spans"][0]["chunk_ids"] == ["A", "B"]


def test_overlapping_chunks_pass(benchmark):
    _, row, _ = benchmark
    left, right = copy.deepcopy(row), copy.deepcopy(row)
    left["text"] = row["text"][:65]
    right.update(chunk_id="B", text=row["text"][20:])
    assert score(benchmark, [left, right])["status"] == "pass"


@pytest.mark.parametrize("old,new", [("30", "60"), (", except when condition Y applies", ""), ("must", "must not")])
def test_changed_values_exceptions_and_negations_fail(benchmark, old, new):
    _, row, _ = benchmark
    row["text"] = row["text"].replace(old, new)
    result = score(benchmark, [row])
    assert result["status"] == "fail"
    assert result["metrics"]["source_spans_preserved"] == 0


def test_wrong_article_found_by_content_then_flagged(benchmark):
    _, row, _ = benchmark
    row["metadata"]["article_number"] = 4
    result = score(benchmark, [row])
    assert result["metrics"]["source_spans_preserved"] == 1
    assert result["cases"][0]["spans"][0]["metadata_errors"]
    assert result["status"] == "fail"


def test_wrong_document_metadata_detected(benchmark):
    _, row, _ = benchmark
    row["metadata"]["document_id"] = "WRONG"
    assert score(benchmark, [row])["metrics"]["metadata_pass_rate_on_preserved_spans"] == 0


def test_invented_extra_body_text_fails_even_when_source_is_preserved(benchmark):
    _, row, _ = benchmark
    row["text"] += " The employer may invent a new punishment."
    result = score(benchmark, [row])
    assert result["metrics"]["span_preservation_rate"] == 1
    assert result["cases"][0]["unexpected_body_fragments"]
    assert result["status"] == "fail"


def test_missing_reference_detected(benchmark):
    _, row, _ = benchmark
    row["references"] = []
    assert score(benchmark, [row])["metrics"]["positive_reference_recall"] == 0


def test_reference_negative_case_catches_extra_edge(benchmark):
    dataset, row, _ = benchmark
    dataset["cases"][0].update(references=[], reference_scope="complete_empty")
    assert score(benchmark, [row])["cases"][0]["unexpected_references"]


def test_missing_header_context_detected(benchmark):
    _, row, _ = benchmark
    row["header_context"] = ""
    assert score(benchmark, [row])["metrics"]["context_pass_rate_on_preserved_spans"] == 0


def test_parent_condition_checked_on_each_split_chunk(benchmark):
    dataset, row, _ = benchmark
    dataset["cases"][0]["spans"][0].update(clause=1, point="a")
    dataset["cases"][0]["context_requirements"] = [{"clause": 1, "points_only": True, "text": "Except in emergencies"}]
    row["metadata"].update(chunk_level="POINT", clause_number=1, point_letter="a")
    row["header_context"] += " Except in emergencies"
    assert score(benchmark, [row])["status"] == "pass"
    left, right = copy.deepcopy(row), copy.deepcopy(row)
    left["text"], right["text"] = row["text"][:40], row["text"][40:]
    right.update(chunk_id="B", header_context="POLICY-1 > Điều 3: Registers")
    result = score(benchmark, [left, right])
    assert result["metrics"]["source_spans_preserved"] == 1
    assert result["status"] == "fail"


def test_clause_number_can_move_from_text_to_metadata(benchmark):
    dataset, row, _ = benchmark
    span = dataset["cases"][0]["spans"][0]
    span.update(text="1. " + span["text"], clause=1)
    row["metadata"].update(chunk_level="CLAUSE", clause_number=1)
    assert score(benchmark, [row])["status"] == "pass"
    row["metadata"]["clause_number"] = 2
    assert score(benchmark, [row])["status"] == "fail"


def test_article_chunk_cannot_drop_source_numbering(benchmark):
    dataset, row, _ = benchmark
    span = dataset["cases"][0]["spans"][0]
    span.update(text="1. " + span["text"], clause=1)
    assert score(benchmark, [row])["status"] == "fail"


def test_same_phrase_elsewhere_does_not_override_correct_header_match(benchmark):
    dataset, row, _ = benchmark
    correct = copy.deepcopy(row)
    correct["header_context"] += " " + correct["text"]
    correct["text"] = "Other body content"
    wrong = copy.deepcopy(row)
    wrong["metadata"]["article_number"] = 4
    wrong["chunk_id"] = "WRONG"
    result = score(benchmark, [wrong, correct])
    assert result["cases"][0]["spans"][0]["chunk_ids"] == ["A"]


def test_metadata_only_text_is_distinguished_from_retrievable_text(benchmark):
    _, row, _ = benchmark
    row["metadata"]["chapeau_text"] = row["text"]
    row["text"] = "Other body content"
    result = score(benchmark, [row])
    assert result["metrics"]["span_preservation_rate"] == 1
    assert result["metrics"]["retrieval_visible_span_rate"] == 0
    assert result["status"] == "fail"


def test_source_hash_mismatch_blocks_success(benchmark):
    _, row, root = benchmark
    (root / "source.txt").write_text("changed original")
    result = score(benchmark, [row])
    assert result["provenance_errors"]
    assert result["status"] == "fail"


def test_duplicate_and_empty_chunks_fail(benchmark):
    _, row, _ = benchmark
    extra = copy.deepcopy(row)
    extra["text"] = ""
    result = score(benchmark, [row, extra])
    assert result["documents"][0]["duplicate_chunk_ids"] == ["A"]
    assert result["documents"][0]["empty_chunks"] == ["A"]


def test_missing_capture_never_passes(benchmark):
    result = score(benchmark, [])
    assert result["status"] == "fail"
    assert result["metrics"]["source_spans_preserved"] == 0


def test_reversed_source_paragraph_order_fails(benchmark):
    dataset, row, _ = benchmark
    first = dataset["cases"][0]["spans"][0]
    second = {**first, "source_index": 2, "text": "A separate duty must also be fulfilled."}
    dataset["cases"][0]["spans"].append(second)
    row["text"] = second["text"] + "\n" + first["text"]
    result = score(benchmark, [row])
    assert result["metrics"]["source_spans_preserved"] == 2
    assert result["status"] == "fail"


def test_empty_golden_span_is_rejected(benchmark):
    dataset, _, _ = benchmark
    dataset["cases"][0]["spans"][0]["text"] = " "
    with pytest.raises(ValueError, match="Empty source span"):
        validate_dataset(dataset)


def test_normalization_keeps_meaningful_values_and_accents():
    assert canonical("**30 ngày**") == canonical("30\nngày")
    assert canonical("30 ngày") != canonical("60 ngày")
    assert canonical("không") != canonical("khong")


def test_dataset_is_reproducible_and_drafts_are_not_approved():
    expected = json.loads((ROOT / "eval/ingestion/golden.json").read_text())
    assert build() == expected
    assert len(expected["cases"]) == 16
    assert all(c["review_status"] == "draft" and not c["reviewer"] for c in expected["cases"])
