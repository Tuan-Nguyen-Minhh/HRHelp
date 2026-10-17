"""Kiểm thử bộ chấm retrieval độc lập với API và database."""

import asyncio
import copy
import hashlib
import json

import pytest

from eval.retrieval.benchmark import PacedReranker, digest, measure, summarize, validate, write_report
from eval.retrieval.build_dataset import build, eligible
from eval.retrieval.snapshot import HERE, fingerprint


@pytest.fixture
def sample():
    rows = []
    for key in "ABCD":
        content = f"Original source text {key}, including its exception."
        rows.append(
            {
                "chunk_id": key,
                "content": content,
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                "policy_code": "POLICY",
                "article": str(ord(key) - 64),
                "clause": None,
                "point": None,
                "is_active": True,
                "policy_deleted": False,
                "document_deleted": False,
                "ingest_status": "EMBEDDED",
                "version_status": "ACTIVE",
                "effective_from": "2026-01-01",
                "effective_to": None,
            }
        )
    snapshot = {"chunks": rows, "references": []}
    snapshot["corpus_sha256"] = fingerprint(snapshot)
    units = {
        f"U{n}": {"member_ids": [key], "member_hashes": {key: rows[n - 1]["content_sha256"]}}
        for n, key in enumerate("ABC", 1)
    }
    case = {
        "case_id": "TEST",
        "reference_status": "draft_pending_expert_review",
        "reviewer": None,
        "origin": "synthetic_source_task",
        "source": None,
        "input": {"query": "Find rules and exceptions", "incident_date": "2026-08-15"},
        "evidence_bundles": [["U1", "U2"]],
        "critical_units": ["U2"],
        "judgments": {"A": 3, "B": 3, "C": 0},
        "expected_empty": False,
    }
    dataset = {
        "schema_version": 1,
        "corpus_sha256": snapshot["corpus_sha256"],
        "units": units,
        "cases": [case],
        "scope_vi": "Kiểm thử",
    }
    run = {
        "status": "complete",
        "input_sha256": digest(case["input"]),
        "stages": {"fused": ["A", "B", "D"], "expanded": ["A", "B", "D"], "hits": ["A", "B", "D"]},
        "selected_passages": [{"chunk_id": r["chunk_id"], "content": r["content"]} for r in rows],
        "healthy": True,
        "health_gaps": [],
        "evidence_gaps": [],
        "latency_ms": 100,
        "graph_ids": [],
    }
    return dataset, snapshot, case, run


def test_complete_reference_and_partial_judgments(sample):
    dataset, snapshot, case, run = sample
    result = measure(case, run, dataset, snapshot)
    assert result["passed_checks"] is True
    assert result["metrics"]["candidate_recall"] == result["metrics"]["final_recall"] == 1
    assert result["metrics"]["labeled_precision_lower_bound"] == pytest.approx(2 / 3)
    assert result["metrics"]["judged_precision"] == 1
    assert result["metrics"]["judgment_coverage"] == pytest.approx(2 / 3)
    assert result["unjudged_selected_ids"] == ["D"]


def test_alternative_bundle_does_not_require_union(sample):
    dataset, snapshot, case, run = sample
    case.update(evidence_bundles=[["U1", "U2"], ["U1", "U3"]], critical_units=[])
    run["stages"].update(fused=["A", "C"], expanded=["A", "C"], hits=["A", "C"])
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["complete_labeled_bundle"] is True
    assert result["metrics"]["candidate_recall"] == result["metrics"]["final_recall"] == 1


def test_critical_exception_lost_between_candidates_and_final(sample):
    dataset, snapshot, case, run = sample
    run["stages"]["hits"] = ["A", "D"]
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["candidate_recall"] == 1
    assert result["metrics"]["final_recall"] == 0.5
    assert result["metrics"]["critical_chunk_recall"] == 0
    assert result["missing_critical_units"] == ["U2"]
    assert result["passed_checks"] is False


def test_multichunk_unit_requires_every_member(sample):
    dataset, snapshot, case, run = sample
    dataset["units"]["U2"]["member_ids"] = ["B", "C"]
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["critical_chunk_recall"] == 0.5
    assert result["metrics"]["complete_labeled_bundle"] is False


def test_correct_uuid_with_truncated_content_fails(sample):
    dataset, snapshot, case, run = sample
    run["selected_passages"][1]["content"] = "Original source text B"
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["final_recall"] == 1
    assert result["altered_selected_ids"] == ["B"]
    assert result["metrics"]["passage_fidelity_pass"] is False
    assert result["passed_checks"] is False


def test_expiry_is_inclusive_and_ineligible_output_is_flagged(sample):
    dataset, snapshot, case, run = sample
    snapshot["chunks"][1]["effective_to"] = "2026-09-09"
    assert eligible(snapshot["chunks"][1], "2026-09-09")
    assert not eligible(snapshot["chunks"][1], "2026-09-10")
    case["input"]["incident_date"] = "2026-09-10"
    result = measure(case, run, dataset, snapshot)
    assert result["ineligible_selected_ids"] == ["B"]
    assert result["passed_checks"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("is_active", False),
        ("policy_deleted", True),
        ("document_deleted", True),
        ("version_status", "ARCHIVED"),
        ("ingest_status", "FAILED"),
    ],
)
def test_eligibility_is_not_only_a_date_check(sample, field, value):
    _, snapshot, _, _ = sample
    row = dict(snapshot["chunks"][0], **{field: value})
    assert not eligible(row, "2026-08-15")


def test_negative_empty_case_has_no_fabricated_recall(sample):
    dataset, snapshot, case, run = sample
    case.update(expected_empty=True, evidence_bundles=[], critical_units=[])
    case["input"]["incident_date"] = "2000-01-01"
    run["stages"].update(fused=[], expanded=[], hits=[])
    result = measure(case, run, dataset, snapshot)
    assert result["passed_checks"] is True
    assert result["metrics"]["expected_empty_pass"] is True
    assert result["metrics"]["final_recall"] is None
    assert result["metrics"]["ndcg_lower_bound"] is None
    run["stages"]["hits"] = ["A"]
    assert measure(case, run, dataset, snapshot)["passed_checks"] is False


def test_no_edges_does_not_claim_graph_effectiveness(sample):
    dataset, snapshot, case, run = sample
    assert measure(case, run, dataset, snapshot)["metrics"]["graph_recall_gain"] is None


def test_supplemented_candidates_are_not_counted_as_graph_gain(sample):
    dataset, snapshot, case, run = sample
    snapshot["references"] = [{"example": "edge"}]
    run["stages"].update(fused=["A"], expanded=["A", "B"])
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["candidate_recall"] == 1
    assert result["metrics"]["graph_recall_gain"] == 0
    run["graph_ids"] = ["B"]
    assert measure(case, run, dataset, snapshot)["metrics"]["graph_recall_gain"] == 0.5


def test_api_error_is_null_not_zero(sample):
    dataset, snapshot, case, _ = sample
    result = measure(case, {"status": "error", "error": "TimeoutError"}, dataset, snapshot)
    assert result["metrics"] is None
    assert result["passed_checks"] is None


def test_degraded_output_is_measured_but_not_passed(sample):
    dataset, snapshot, case, run = sample
    run.update(healthy=False, health_gaps=["rerank_status:FAILED"])
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["final_recall"] == 1
    assert result["passed_checks"] is False


def test_duplicate_hits_do_not_inflate_scores(sample):
    dataset, snapshot, case, run = sample
    run["stages"]["hits"] = ["A", "A", "B"]
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["selected_count"] == 2
    assert result["metrics"]["ndcg_lower_bound"] == 1


def test_ndcg_rewards_relevant_passages_earlier(sample):
    dataset, snapshot, case, run = sample
    run["stages"]["hits"] = ["A", "B", "C"]
    good = measure(case, run, dataset, snapshot)["metrics"]["ndcg_lower_bound"]
    run["stages"]["hits"] = ["C", "B", "A"]
    assert measure(case, run, dataset, snapshot)["metrics"]["ndcg_lower_bound"] < good


def test_empty_positive_result_is_zero_recall_and_ndcg(sample):
    dataset, snapshot, case, run = sample
    run["stages"]["hits"] = []
    result = measure(case, run, dataset, snapshot)
    assert result["metrics"]["final_recall"] == 0
    assert result["metrics"]["ndcg_lower_bound"] == 0
    assert result["passed_checks"] is False


@pytest.mark.asyncio
async def test_pacing_preserves_original_queries_passages_and_scores():
    import time

    calls, started = [], []
    marker = object()

    async def real(query, passages):
        started.append(time.monotonic())
        calls.append((query, passages))
        return marker

    paced = PacedReranker(real, 0.005)
    passages = [object()]
    results = await asyncio.gather(*(paced(f"Q{i}", passages) for i in range(3)))
    assert all(r is marker for r in results)
    assert calls == [(f"Q{i}", passages) for i in range(3)]
    assert all(b - a >= 0.0049 for a, b in zip(started, started[1:]))
    assert paced.requests == 3
    assert await paced("empty", []) is marker
    assert paced.requests == 3


def test_source_hash_drift_blocks_evaluation(sample):
    dataset, snapshot, _, _ = sample
    snapshot["chunks"][0]["content"] = "Changed text"
    with pytest.raises(ValueError, match="Ảnh chụp"):
        validate(dataset, snapshot)


def test_different_dataset_cannot_be_scored(sample):
    dataset, snapshot, _, _ = sample
    with pytest.raises(ValueError, match="Không được trộn"):
        summarize(dataset, snapshot, {"dataset_sha256": "wrong", "corpus_sha256": dataset["corpus_sha256"]})


def test_real_golden_is_reproducible_and_not_expert_approved():
    dataset = json.loads((HERE / "golden.json").read_text())
    snapshot = json.loads((HERE / "corpus_snapshot.json").read_text())
    validate(dataset, snapshot)
    assert build(snapshot) == dataset
    assert len(dataset["cases"]) == 20
    assert sum(c["origin"] == "source_excerpt" for c in dataset["cases"]) == 5
    assert all(c["reference_status"] != "expert_reviewed" for c in dataset["cases"])


def test_summary_and_vietnamese_report(sample, tmp_path):
    dataset, snapshot, case, run = sample
    capture = {
        "dataset_sha256": digest(dataset),
        "corpus_sha256": dataset["corpus_sha256"],
        "corpus_stable_after_run": True,
        "configuration": {},
        "runs": {case["case_id"]: run},
    }
    result = summarize(dataset, snapshot, capture)
    before = copy.deepcopy(result)
    write_report(result, tmp_path)
    assert result == before
    assert result["averages"]["final_recall"]["mean"] == 1
    assert result["reference_status"] == "draft_pending_expert_review"
    assert "Đánh giá chất lượng truy xuất" in (tmp_path / "report.md").read_text()


def test_corpus_change_after_capture_blocks_scoring(sample):
    dataset, snapshot, case, run = sample
    capture = {
        "dataset_sha256": digest(dataset),
        "corpus_sha256": dataset["corpus_sha256"],
        "corpus_stable_after_run": False,
        "configuration": {},
        "runs": {case["case_id"]: run},
    }
    with pytest.raises(ValueError, match="giữ nguyên"):
        summarize(dataset, snapshot, capture)


def test_legacy_expert_gate_is_preserved(tmp_path):
    from eval.retrieval.evaluate import load_references

    path = tmp_path / "draft.json"
    path.write_text(
        json.dumps(
            [
                {
                    "case_id": "draft",
                    "reference_status": "draft_pending_expert_review",
                    "incident_date": "2026-08-15",
                    "description": "Draft",
                    "evidence_bundles": [["00000000-0000-0000-0000-000000000001"]],
                }
            ]
        )
    )
    with pytest.raises(ValueError, match="drafts"):
        load_references(path)


def test_new_cli_requires_explicit_draft_preview(monkeypatch, tmp_path):
    import sys

    from eval.retrieval.benchmark import main

    monkeypatch.setattr(sys, "argv", ["benchmark", "--runs", str(tmp_path / "missing.json")])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
