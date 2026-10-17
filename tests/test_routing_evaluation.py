"""Kiểm tra bộ chấm bằng lỗi có chủ đích; không gọi mô hình hoặc cơ sở dữ liệu."""

import copy
import json

import pytest

from eval.routing.build_dataset import build
from eval.routing.evaluate import HERE, digest, matches, score_case, summarize, validate, write_report


@pytest.fixture
def routing_case():
    return {
        "case_id": "R",
        "suite": "routing",
        "origin": "synthetic_contract",
        "review_status": "draft",
        "reviewer": None,
        "input": {"message": "Đã lập biên bản.", "state": {}},
        "expected": {"routes": ["fact_planner"], "actions": ["complete_facts"], "task_change": "keep"},
    }


@pytest.fixture
def routing_record():
    return {
        "status": "complete",
        "latency_ms": 10,
        "actual": {
            "selected_route": "fact_planner",
            "requested_action": "complete_facts",
            "task_change": "keep",
            "contract_issues": [],
            "edge": "extract",
            "decision": {"requires_fact_planner": True},
        },
    }


@pytest.fixture
def fact_case():
    return {
        "case_id": "F",
        "suite": "facts",
        "origin": "synthetic_contract",
        "review_status": "draft",
        "reviewer": None,
        "input": {
            "message": "Nghỉ không phép 5 ngày.",
            "state": {"active_fact_keys": ["absence_days", "contract_type"]},
        },
        "expected": {
            "final_facts": {"absence_days": {"values": ["5 ngày"], "confirmed": True}},
            "raw_facts": {"absence_days": {"values": ["5 ngày"]}},
            "missing_keys": ["contract_type"],
            "facts_locked": False,
            "forbidden_keys": ["contract_type"],
            "pending_action": "draft_minutes",
        },
    }


@pytest.fixture
def fact_record():
    return {
        "status": "complete",
        "latency_ms": 10,
        "actual": {
            "merged": {"absence_days": {"value": "5 ngày", "confirmed": True}},
            "raw_facts": [{"key": "absence_days", "value": "5 ngày", "ambiguous": False, "evidence": "5 ngày"}],
            "missing_keys": ["contract_type"],
            "facts_locked": False,
            "next_edge": "ask",
            "pending_action": "draft_minutes",
        },
    }


def test_correct_routing_passes(routing_case, routing_record):
    assert score_case(routing_case, routing_record)["passed"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("selected_route", "policy_qa"),
        ("requested_action", "draft_minutes"),
        ("task_change", "cancel"),
        ("contract_issues", ["invalid"]),
    ],
)
def test_wrong_route_action_task_or_contract_fails(routing_case, routing_record, field, value):
    routing_record["actual"][field] = value
    assert score_case(routing_case, routing_record)["passed"] is False


def test_fallback_clarification_is_not_a_correct_prediction(routing_case, routing_record):
    routing_case["expected"] = {"routes": ["clarify"]}
    routing_record.update(status="error", error="Phương án dự phòng")
    routing_record["actual"]["selected_route"] = "clarify"
    scored = score_case(routing_case, routing_record)
    assert scored["passed"] is None
    assert scored["status"] == "error"


def test_correct_facts_pass(fact_case, fact_record):
    scored = score_case(fact_case, fact_record)
    assert scored["passed"] is True
    assert scored["validated_counts"] == {"tp": 1, "fp": 0, "fn": 0, "missing_or_wrong": [], "extra_or_wrong": []}


def test_changed_value_counts_false_positive_and_false_negative(fact_case, fact_record):
    fact_record["actual"]["merged"]["absence_days"]["value"] = "50 ngày"
    scored = score_case(fact_case, fact_record)
    assert scored["validated_counts"]["tp"] == 0
    assert scored["validated_counts"]["fp"] == scored["validated_counts"]["fn"] == 1
    assert scored["passed"] is False


def test_hallucinated_contract_fails(fact_case, fact_record):
    fact_record["actual"]["merged"]["contract_type"] = {"value": "thử việc", "confirmed": True}
    assert score_case(fact_case, fact_record)["passed"] is False


def test_python_filter_does_not_hide_raw_hallucination(fact_case, fact_record):
    fact_record["actual"]["raw_facts"].append({"key": "contract_type", "value": "thử việc", "evidence": "5 ngày"})
    scored = score_case(fact_case, fact_record)
    assert scored["validated_counts"]["fp"] == 0
    assert scored["raw_counts"]["fp"] == 1
    assert scored["passed"] is False


def test_correct_model_fact_lost_by_python_is_identified(fact_case, fact_record):
    fact_record["actual"]["merged"] = {}
    scored = score_case(fact_case, fact_record)
    assert scored["raw_counts"]["fn"] == 0
    assert scored["dropped_by_validation"] == ["absence_days"]
    assert scored["passed"] is False


def test_evidence_must_come_from_current_message(fact_case, fact_record):
    fact_record["actual"]["raw_facts"][0]["evidence"] = "Theo dữ liệu cũ nghỉ 5 ngày"
    scored = score_case(fact_case, fact_record)
    assert scored["evidence_grounded"] == 0
    assert scored["passed"] is False


def test_abstention_does_not_require_evidence_for_an_unasserted_value(fact_case, fact_record):
    fact_case["expected"].update(final_facts={}, raw_facts={}, missing_keys=["absence_days", "contract_type"])
    fact_record["actual"].update(
        merged={},
        missing_keys=["absence_days", "contract_type"],
        raw_facts=[{"key": "absence_days", "value": "", "ambiguous": True, "evidence": ""}],
    )
    scored = score_case(fact_case, fact_record)
    assert scored["evidence_total"] == 0
    assert scored["passed"] is True


@pytest.mark.parametrize(
    "field,value", [("missing_keys", []), ("facts_locked", True), ("next_edge", "retrieve"), ("pending_action", None)]
)
def test_missing_fact_lock_and_pending_task_guards(fact_case, fact_record, field, value):
    fact_record["actual"][field] = value
    assert score_case(fact_case, fact_record)["passed"] is False


def test_wrong_confirmation_fails(fact_case, fact_record):
    fact_record["actual"]["merged"]["absence_days"]["confirmed"] = False
    assert score_case(fact_case, fact_record)["passed"] is False


def test_confirmation_can_repeat_stored_value_without_new_raw_fact(fact_case, fact_record):
    fact_case["expected"].update(raw_facts={}, raw_optional_keys=["absence_days"])
    assert score_case(fact_case, fact_record)["raw_counts"]["fp"] == 0
    fact_record["actual"]["raw_facts"][0]["value"] = "7 ngày"
    assert score_case(fact_case, fact_record)["passed"] is False


def test_value_comparison_does_not_collapse_distinct_numbers():
    assert matches("absence_days", "5", {"values": ["5 ngày"]})
    assert not matches("absence_days", "50 ngày", {"values": ["5 ngày"]})
    assert matches("minutes_made", "chưa", {"values": ["false"]})
    assert not matches("minutes_made", "true", {"values": ["false"]})


def test_transport_errors_have_null_accuracy(routing_case, fact_case):
    dataset = {"schema_version": 1, "scope_vi": "Kiểm thử", "cases": [routing_case, fact_case]}
    result = summarize(dataset, {"dataset_sha256": digest(dataset), "runs": {}})
    assert result["error_count"] == 2
    assert result["routing"]["accuracy"] is None
    assert result["facts"]["exact_case_accuracy"] is None
    assert all(c["passed"] is None for c in result["cases"])


def test_confusion_and_fact_metrics_use_real_predictions(routing_case, routing_record, fact_case, fact_record):
    dataset = {"schema_version": 1, "scope_vi": "Kiểm thử", "cases": [routing_case, fact_case]}
    routing_record["actual"]["selected_route"] = "policy_qa"
    result = summarize(dataset, {"dataset_sha256": digest(dataset), "runs": {"R": routing_record, "F": fact_record}})
    assert result["routing"]["accuracy"] == 0
    assert result["routing"]["per_route"]["fact_planner"]["fn"] == 1
    assert result["routing"]["per_route"]["policy_qa"]["fp"] == 1
    assert result["facts"]["validated"]["f1"] == 1
    assert result["label_status"] == "draft_pending_review"


def test_mismatched_capture_is_rejected(routing_case):
    dataset = {"schema_version": 1, "scope_vi": "Kiểm thử", "cases": [routing_case]}
    with pytest.raises(ValueError, match="Bộ dữ liệu khác"):
        summarize(dataset, {"dataset_sha256": "wrong", "runs": {}})


def test_mismatched_case_input_is_rejected(routing_case, routing_record):
    dataset = {"schema_version": 1, "scope_vi": "Kiểm thử", "cases": [routing_case]}
    routing_record["input_sha256"] = "wrong"
    with pytest.raises(ValueError, match="Đầu vào ca"):
        summarize(dataset, {"dataset_sha256": digest(dataset), "runs": {"R": routing_record}})


def test_original_source_drift_is_rejected(tmp_path, fact_case):
    source = tmp_path / "case.docx"
    source.write_bytes(b"changed")
    fact_case["source"] = {"path": "case.docx", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="SHA-256"):
        validate({"schema_version": 1, "cases": [fact_case]}, root=tmp_path)


def test_real_dataset_is_reproducible_and_not_approved():
    dataset = json.loads((HERE / "golden.json").read_text())
    assert build() == dataset
    validate(dataset)
    assert len(dataset["cases"]) == 48
    assert sum(c["origin"] == "source_excerpt" for c in dataset["cases"]) == 5
    assert all(c["review_status"] == "draft" and not c["reviewer"] for c in dataset["cases"])


def test_report_is_written_in_vietnamese(tmp_path, routing_case, routing_record):
    dataset = {"schema_version": 1, "scope_vi": "Kiểm thử", "cases": [routing_case]}
    result = summarize(dataset, {"dataset_sha256": digest(dataset), "runs": {"R": routing_record}})
    before = copy.deepcopy(result)
    write_report(result, tmp_path)
    assert result == before
    assert "Đánh giá định tuyến" in (tmp_path / "report.md").read_text()
    assert json.loads((tmp_path / "scores.json").read_text())["sample_count"] == 1
