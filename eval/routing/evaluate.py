"""Chấm định tuyến và trích xuất tình tiết; chỉ gọi mô hình khi có --live."""

import argparse
import asyncio
import hashlib
import json
import math
import time
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ROUTES = {
    "general_chat",
    "system_help",
    "case_qa",
    "fact_planner",
    "policy_qa",
    "workflow_action",
    "external_research",
    "clarify",
    "unsupported",
    "capability_gap",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def normal(value):
    return " ".join(unicodedata.normalize("NFC", str(value)).casefold().split())


def matches(key, value, label):
    text = normal(value)
    if key in {"absence_days", "late_days"} and text.isdigit():
        text += " ngày" if key == "absence_days" else " lần"
    if key in {"minutes_made", "explanation_requested"}:
        text = {"yes": "true", "có": "true", "đã": "true", "no": "false", "chưa": "false", "không": "false"}.get(
            text, text
        )
    if "values" in label:
        return text in {normal(v) for v in label["values"]}
    return all(normal(part) in text for part in label["contains_all"])


def validate(dataset, root=ROOT):
    if dataset.get("schema_version") != 1 or not dataset.get("cases"):
        raise ValueError("Bộ dữ liệu phải có schema_version=1 và danh sách ca không rỗng")
    ids = [c["case_id"] for c in dataset["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Trùng case_id")
    for case in dataset["cases"]:
        if not case["input"]["message"].strip():
            raise ValueError("Tin nhắn không được rỗng")
        if case["suite"] == "routing":
            if not case["expected"]["routes"] or set(case["expected"]["routes"]) - ROUTES:
                raise ValueError("Nhãn định tuyến không hợp lệ")
        elif case["suite"] == "facts":
            keys = case["input"]["state"]["active_fact_keys"]
            if not keys or len(keys) != len(set(keys)):
                raise ValueError("Lược đồ tình tiết phải có khóa duy nhất")
            for section in ("final_facts", "raw_facts"):
                for label in case["expected"][section].values():
                    if not label.get("values") and not label.get("contains_all"):
                        raise ValueError("Nhãn tình tiết phải có giá trị hoặc các cụm bắt buộc")
        else:
            raise ValueError("Nhóm đánh giá không hợp lệ")
        source = case.get("source")
        if source:
            path = root / source["path"]
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError(f"{case['case_id']}: nguồn gốc thiếu hoặc SHA-256 thay đổi")
            if case["input"]["message"] != "\n".join(p["text"] for p in source["paragraphs"]):
                raise ValueError("Trích đoạn đầu vào khác nhãn nguồn đã lưu")


def fact_counts(actual, expected):
    correct = {k for k, label in expected.items() if k in actual and matches(k, actual[k], label)}
    return {
        "tp": len(correct),
        "fp": len(set(actual) - correct),
        "fn": len(set(expected) - correct),
        "missing_or_wrong": sorted(set(expected) - correct),
        "extra_or_wrong": sorted(set(actual) - correct),
    }


def score_case(case, record):
    base = {
        "case_id": case["case_id"],
        "suite": case["suite"],
        "origin": case["origin"],
        "message": case["input"]["message"],
        "expected": case["expected"],
        "latency_ms": record.get("latency_ms"),
        "passed": None,
        "errors": [],
    }
    if record.get("status") != "complete":
        return {
            **base,
            "status": "error",
            "technical_error": record.get("error", "Thiếu đầu ra hoàn chỉnh"),
            "failure_details": {
                k: record.get("actual", {}).get(k) for k in ("fallback_kind", "recheck_status", "initial_route")
            },
        }
    actual, label = record["actual"], case["expected"]
    base.update(status="complete", actual=actual)
    if case["suite"] == "routing":
        base["route_correct"] = actual["selected_route"] in label["routes"]
        if not base["route_correct"]:
            base["errors"].append("Nhánh cuối không thuộc các nhánh mong đợi")
        if "actions" in label and actual["requested_action"] not in label["actions"]:
            base["errors"].append("Hành động không đúng nhãn")
        if "task_change" in label and actual["task_change"] != label["task_change"]:
            base["errors"].append("Thao tác giữ/hủy mục tiêu không đúng")
        if actual.get("contract_issues"):
            base["errors"].append("Quyết định vi phạm hợp đồng định tuyến")
        edges = {
            "general_chat": "general_chat",
            "system_help": "system_help",
            "case_qa": "case_qa",
            "fact_planner": "extract",
            "workflow_action": "extract",
            "clarify": "disambiguate",
        }
        expected_edges = {edges.get(route, "action") for route in label["routes"]}
        if actual.get("edge") not in expected_edges:
            base["errors"].append("Cạnh đồ thị sau cổng Python không đúng")
        decision = actual.get("decision", {})
        if actual["selected_route"] == "fact_planner" or actual["requested_action"] == "draft_minutes":
            if decision.get("requires_fact_planner") is not True:
                base["errors"].append("Thiếu yêu cầu kiểm tra tình tiết trước khi xử lý")
    else:
        final = {k: v["value"] for k, v in actual["merged"].items() if str(v["value"]).strip()}
        base["validated_counts"] = fact_counts(final, label["final_facts"])
        if base["validated_counts"]["fp"] or base["validated_counts"]["fn"]:
            base["errors"].append("Thiếu, sai giá trị hoặc thêm tình tiết ngoài nhãn")
        for key, expected in label["final_facts"].items():
            if key in actual["merged"] and actual["merged"][key]["confirmed"] != expected["confirmed"]:
                base["errors"].append(f"Trạng thái xác nhận không đúng: {key}")
        if set(actual["missing_keys"]) != set(label["missing_keys"]):
            base["errors"].append("Danh sách tình tiết còn thiếu không đúng")
        if actual["facts_locked"] != label["facts_locked"]:
            base["errors"].append("Trạng thái khóa tình tiết không đúng")
        if set(final) & set(label["forbidden_keys"]):
            base["errors"].append("Có tình tiết bị yêu cầu không suy diễn")
        if label["pending_action"] and actual["pending_action"] != label["pending_action"]:
            base["errors"].append("Không giữ tác vụ đang chờ")
        if not label["facts_locked"] and actual["next_edge"] == "retrieve":
            base["errors"].append("Cho phép truy xuất khi tình tiết chưa đủ điều kiện")
        asserted = [item for item in actual["raw_facts"] if not item.get("ambiguous") and str(item["value"]).strip()]
        raw = {item["key"]: item["value"] for item in asserted}
        for key in label.get("raw_optional_keys", []):
            if key in raw and matches(key, raw[key], label["final_facts"][key]):
                raw.pop(key)
        base["raw_counts"] = fact_counts(raw, label["raw_facts"])
        base["dropped_by_validation"] = [
            key
            for key, expected in label["final_facts"].items()
            if key in raw
            and matches(key, raw[key], expected)
            and (key not in final or not matches(key, final[key], expected))
        ]
        base["evidence_total"] = len(asserted)
        base["evidence_grounded"] = sum(
            bool(normal(item.get("evidence", ""))) and normal(item["evidence"]) in normal(case["input"]["message"])
            for item in asserted
        )
        if base["raw_counts"]["fp"] or base["raw_counts"]["fn"]:
            base["errors"].append("Đầu ra mô hình trước kiểm tra Python thiếu, sai hoặc thừa tình tiết")
        if base["evidence_grounded"] != base["evidence_total"]:
            base["errors"].append("Trích dẫn bằng chứng không khớp nguyên văn tin nhắn hiện tại")
    base["passed"] = not base["errors"]
    return base


def ratio(n, d):
    return n / d if d else None


def count_metrics(cases, key):
    totals = {k: sum(c[key][k] for c in cases) for k in ("tp", "fp", "fn")}
    p, r = ratio(totals["tp"], totals["tp"] + totals["fp"]), ratio(totals["tp"], totals["tp"] + totals["fn"])
    return {
        **totals,
        "precision": p,
        "recall": r,
        "f1": ratio(2 * totals["tp"], 2 * totals["tp"] + totals["fp"] + totals["fn"]),
    }


def summarize(dataset, capture):
    if capture.get("dataset_sha256") != digest(dataset):
        raise ValueError("Bộ dữ liệu khác bản đã dùng thu thập; không trộn nhãn hoặc lần chạy")
    records = capture.get("runs", {})
    unknown = set(records) - {c["case_id"] for c in dataset["cases"]}
    if unknown:
        raise ValueError("Kết quả chứa case_id không thuộc bộ dữ liệu")
    scored = []
    for case in dataset["cases"]:
        record = records.get(case["case_id"], {"status": "error", "error": "Chưa thu thập ca này"})
        if record.get("input_sha256") and record["input_sha256"] != digest(case["input"]):
            raise ValueError("Đầu vào ca không khớp lần thu thập")
        scored.append(score_case(case, record))
    routes = [c for c in scored if c["suite"] == "routing" and c["status"] == "complete"]
    facts = [c for c in scored if c["suite"] == "facts" and c["status"] == "complete"]
    per_route = {}
    for route in sorted(ROUTES):
        tp = sum(c["actual"]["selected_route"] == route and route in c["expected"]["routes"] for c in routes)
        fp = sum(c["actual"]["selected_route"] == route and route not in c["expected"]["routes"] for c in routes)
        fn = sum(c["actual"]["selected_route"] != route and route in c["expected"]["routes"] for c in routes)
        per_route[route] = {
            "support": tp + fn,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn),
        }
    supported = [m["f1"] or 0 for m in per_route.values() if m["support"]]
    confusion = Counter((c["expected"]["routes"][0], c["actual"]["selected_route"]) for c in routes)
    latencies = sorted(c["latency_ms"] for c in scored if c["status"] == "complete" and c["latency_ms"] is not None)
    reviewed = all(
        c["review_status"] == "reviewed"
        and c.get("reviewer")
        and (not c.get("source") or c["source"].get("reviewed_source_sha256") == c["source"]["sha256"])
        for c in dataset["cases"]
    )
    return {
        "status": "pass" if all(c["passed"] is True for c in scored) else "fail",
        "label_status": "reviewed" if reviewed else "draft_pending_review",
        "scope_vi": dataset["scope_vi"],
        "dataset_sha256": digest(dataset),
        "configuration": capture.get("configuration", {}),
        "sample_count": len(scored),
        "completed_count": len(routes) + len(facts),
        "error_count": sum(c["status"] == "error" for c in scored),
        "passed_count": sum(c["passed"] is True for c in scored),
        "routing": {
            "attempted": sum(c["suite"] == "routing" for c in scored),
            "completed": len(routes),
            "accuracy": ratio(sum(c["route_correct"] for c in routes), len(routes)),
            "contract_pass_rate": ratio(sum(c["passed"] for c in routes), len(routes)),
            "macro_f1": sum(supported) / len(supported) if supported else None,
            "per_route": per_route,
            "confusion": [{"expected": k[0], "actual": k[1], "count": v} for k, v in sorted(confusion.items())],
        },
        "facts": {
            "attempted": sum(c["suite"] == "facts" for c in scored),
            "completed": len(facts),
            "exact_case_accuracy": ratio(sum(c["passed"] for c in facts), len(facts)),
            "validated": count_metrics(facts, "validated_counts"),
            "raw": count_metrics(facts, "raw_counts"),
            "evidence_grounding_rate": ratio(
                sum(c["evidence_grounded"] for c in facts), sum(c["evidence_total"] for c in facts)
            ),
        },
        "latency_ms": {
            "p50": latencies[math.ceil(len(latencies) * 0.5) - 1] if latencies else None,
            "p95": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
        },
        "cases": scored,
    }


async def collect_case(case, timeout):
    # Only input, never expected labels, enters the production functions.
    from src.agents.case_graph import _decide_intent_route, route_after_intent
    from src.agents.conversation import memory_patch, reconcile_plan
    from src.features.clarify.model.assess import StoredFact
    from src.features.clarify.model.catalog import FactSpec
    from src.features.clarify.model.graph import route_after_extract
    from src.features.clarify.model.intent import route_turn
    from src.features.clarify.model.planner import plan_turn
    from src.features.clarify.model.policy import apply_decision

    payload = case["input"]
    state = dict(payload["state"])
    state["stored"] = {k: StoredFact(**v) for k, v in state.get("stored", {}).items()}
    state.update(
        text=payload["message"],
        latest_user_message=payload["message"],
        semantic=True,
        turn_context=state.get("turn_context")
        or "Hồ sơ kiểm thử; chỉ phân tích lượt hội thoại, không thực thi nghiệp vụ.",
    )
    started = time.perf_counter()

    async def operation():
        if case["suite"] == "routing":
            result = await route_turn(state)
            decision = result.decision
            selected, action, trace = _decide_intent_route(state, decision, result.fallback_kind)
            actual = {
                "initial_route": result.initial_decision.get("route"),
                "selected_route": selected.value,
                "requested_action": action,
                "task_change": decision.task_change.value,
                "contract_issues": trace["contract_issues"],
                "decision": decision.model_dump(mode="json"),
                "edge": route_after_intent(
                    {
                        **state,
                        "selected_route": selected,
                        "intent_decision": decision,
                        "task_change": decision.task_change.value,
                    }
                ),
                "recheck_status": result.recheck_status,
                "fallback_kind": result.fallback_kind.value,
                "model": result.model,
                "prompt_version": result.prompt_version,
            }
            return actual, result.fallback, "Bộ định tuyến dùng phương án dự phòng" if result.fallback else None
        required = set(state["required_fact_keys"])
        state["active_specs"] = tuple(
            FactSpec(key=k, label=k, question=f"Hãy cung cấp {k}?", required=k in required)
            for k in state["active_fact_keys"]
        )
        state["locked_fact_keys"] = state["active_fact_keys"]
        result = await plan_turn(state)
        plan = apply_decision(
            state["text"],
            state["stored"],
            result.decision,
            fallback=result.fallback,
            locked_keys=set(state["locked_fact_keys"]),
            active_specs=state["active_specs"],
            active_family=state["family"],
        )
        plan = reconcile_plan(plan, state)
        patch = memory_patch(plan, pending_action=state.get("pending_action"))
        actual = {
            "raw_facts": [
                f.model_dump(mode="json") for f in [*result.decision.corrections, *result.decision.extracted_facts]
            ],
            "decision": result.decision.model_dump(mode="json"),
            "family": plan.family,
            "merged": {k: {"value": v.value, "confirmed": v.confirmed} for k, v in plan.merged.items()},
            "missing_keys": plan.missing_keys,
            "facts_locked": plan.locked,
            "pending_action": patch.get("pending_action", state.get("pending_action")),
            "next_edge": route_after_extract(
                {
                    "facts_locked": plan.locked,
                    "conflicts": list(plan.conflicts),
                    "requested_action": plan.requested_action,
                }
            ),
            "model": result.model,
            "prompt_version": result.prompt_version,
        }
        return actual, result.fallback, "Bộ trích xuất dùng phương án dự phòng" if result.fallback else None

    try:
        actual, fallback, error = await asyncio.wait_for(operation(), timeout)
        return {
            "status": "error" if fallback else "complete",
            "actual": actual,
            "error": error,
            "input_sha256": digest(payload),
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        # Do not persist provider response bodies, credentials, or exception strings.
        return {
            "status": "error",
            "error": f"Lỗi xử lý: {type(exc).__name__}",
            "input_sha256": digest(payload),
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }


async def collect(dataset, output, *, concurrency=2, timeout=75, resume=False):
    from src.core.config import settings
    from src.features.clarify.model.intent import PROMPT_VERSION as INTENT_VERSION
    from src.features.clarify.model.prompt import PROMPT_VERSION as FACT_VERSION

    if not settings.chat_api_key:
        raise ValueError("Chưa cấu hình khóa API cho mô hình hội thoại")
    path = output / "runs.json"
    configuration = {
        "provider": settings.LLM_PROVIDER,
        "models": list(settings.chat_models()),
        "intent_prompt_version": INTENT_VERSION,
        "fact_prompt_version": FACT_VERSION,
        "concurrency": concurrency,
        "case_timeout_seconds": timeout,
        "scope": "live_production_components_no_db_no_retrieval",
    }
    capture = {"dataset_sha256": digest(dataset), "configuration": configuration, "runs": {}}
    if resume and path.exists():
        previous = json.loads(path.read_text())
        if previous["dataset_sha256"] != capture["dataset_sha256"] or previous["configuration"] != configuration:
            raise ValueError("Không thể tiếp tục: bộ dữ liệu hoặc cấu hình đã đổi")
        capture = previous
    output.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    async def run(case):
        if capture["runs"].get(case["case_id"], {}).get("status") == "complete":
            return
        async with semaphore:
            record = await collect_case(case, timeout)
            capture["runs"][case["case_id"]] = record
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n")
            temporary.replace(path)
            print(f"{case['case_id']}: {record['status']} ({record['latency_ms']} ms)", flush=True)

    await asyncio.gather(*(run(c) for c in dataset["cases"]))
    return capture


def display(value):
    return "Chưa có điểm" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def write_report(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    rows = [
        "# Đánh giá định tuyến và trích xuất tình tiết",
        "",
        f"Kết quả: **{'Đạt' if result['status'] == 'pass' else 'Chưa đạt'}**. Nhãn: **{'Đã rà soát' if result['label_status'] == 'reviewed' else 'Bản nháp chờ rà soát'}**.",
        "",
        result["scope_vi"],
        "",
        "Nhãn nháp chưa được chuyên gia xác nhận. Lỗi API, hết thời gian và phương án dự phòng không được coi là dự đoán đúng hoặc lỗi ngữ nghĩa; các ca này có điểm null.",
        "",
        f"Tổng số ca: {result['sample_count']}; hoàn thành: {result['completed_count']}; lỗi xử lý: {result['error_count']}; đạt toàn bộ yêu cầu: {result['passed_count']}.",
        "",
        f"Định tuyến: chấm được {result['routing']['completed']}/{result['routing']['attempted']} ca. "
        f"Tình tiết: chấm được {result['facts']['completed']}/{result['facts']['attempted']} ca. Các tỷ lệ bên dưới dùng mẫu số là các ca chấm được.",
        "",
        "| Chỉ số | Giá trị |",
        "| --- | --- |",
    ]
    metrics = {
        "Định tuyến — độ chính xác nhánh cuối": result["routing"]["accuracy"],
        "Định tuyến — tỷ lệ đạt cả nhánh/hành động/hợp đồng": result["routing"]["contract_pass_rate"],
        "Định tuyến — F1 trung bình giữa các lớp có mẫu": result["routing"]["macro_f1"],
        "Tình tiết — tỷ lệ ca đạt toàn bộ yêu cầu": result["facts"]["exact_case_accuracy"],
        "Tình tiết sau kiểm tra Python — precision": result["facts"]["validated"]["precision"],
        "Tình tiết sau kiểm tra Python — recall": result["facts"]["validated"]["recall"],
        "Tình tiết sau kiểm tra Python — F1": result["facts"]["validated"]["f1"],
        "Tình tiết mô hình trước kiểm tra — F1": result["facts"]["raw"]["f1"],
        "Bằng chứng khớp nguyên văn tin nhắn": result["facts"]["evidence_grounding_rate"],
        "Thời gian p50 (ms)": result["latency_ms"]["p50"],
        "Thời gian p95 (ms)": result["latency_ms"]["p95"],
    }
    rows += [f"| {k} | {display(v)} |" for k, v in metrics.items()]
    if result.get("review_gate_error"):
        rows += ["", "Điều kiện rà soát chưa đạt: " + result["review_gate_error"] + "."]
    rows += [
        "",
        "## Kết quả theo nhánh",
        "",
        "| Nhánh | Số mẫu hoàn thành | Precision | Recall | F1 |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows += [
        f"| `{k}` | {v['support']} | {display(v['precision'])} | {display(v['recall'])} | {display(v['f1'])} |"
        for k, v in result["routing"]["per_route"].items()
    ]
    rows += ["", "## Kết quả từng ca", "", "| Ca | Nhóm | Kết quả | Thời gian (ms) |", "| --- | --- | --- | --- |"]
    rows += [
        f"| {c['case_id']} | {'Định tuyến' if c['suite'] == 'routing' else 'Tình tiết'} | {'Lỗi xử lý' if c['status'] == 'error' else 'Đạt' if c['passed'] else 'Chưa đạt'} | {c['latency_ms']} |"
        for c in result["cases"]
    ]
    rows += ["", "## Chi tiết chưa đạt", ""]
    for case in result["cases"]:
        if case["passed"] is True:
            continue
        rows += [f"### {case['case_id']}", "", case["message"], ""]
        if case["status"] == "error":
            rows += [f"- {case['technical_error']}", ""]
            detail = case.get("failure_details", {})
            if detail.get("fallback_kind"):
                rows += [
                    f"- Loại dự phòng: `{detail['fallback_kind']}`; trạng thái kiểm tra lại: `{detail['recheck_status']}`; nhánh ban đầu: `{detail['initial_route']}`.",
                    "",
                ]
            continue
        rows += [f"- {e}." for e in case["errors"]]
        if case["suite"] == "routing":
            rows += [f"- Nhánh mong đợi: {case['expected']['routes']}; thực tế: `{case['actual']['selected_route']}`."]
        else:
            for key in ("validated_counts", "raw_counts"):
                counts = case[key]
                rows += [
                    f"- {'Sau kiểm tra Python' if key == 'validated_counts' else 'Đầu ra mô hình'}: thiếu/sai {counts['missing_or_wrong']}; thừa/sai {counts['extra_or_wrong']}."
                ]
            rows += ["- Tình tiết thực tế: `" + json.dumps(case["actual"]["merged"], ensure_ascii=False) + "`."]
            if case["dropped_by_validation"]:
                rows += [
                    f"- Tình tiết đúng ở đầu ra mô hình nhưng bị mất sau kiểm tra Python: {case['dropped_by_validation']}."
                ]
        rows += [""]
    rows += [
        "## Phạm vi và giới hạn",
        "",
        "- Ca định tuyến dùng mô hình thật, bước kiểm tra lại ngữ nghĩa và cổng Python của ứng dụng; quy tắc từ khóa không được dùng làm đáp án thay thế.",
        "- Ca tình tiết gọi trực tiếp thành phần trích xuất với lược đồ đang hoạt động; chưa đo xác suất định tuyến đúng rồi mới trích xuất đúng trong một hội thoại hoàn chỉnh.",
        "- Các phép so giá trị dùng nhãn độc lập và các biến thể được chấp nhận; không dùng hàm chuẩn hóa của ứng dụng để tự chấm ứng dụng.",
        "- Trích dẫn nguyên văn là kiểm tra cơ học, không tự xác nhận quan hệ suy luận. Nhãn contains_all cho mô tả chỉ kiểm tra các cụm đã khai báo.",
        "- Bộ nhỏ, hiển thị công khai, pha trộn ca tổng hợp và trích đoạn nguồn; không phải ước lượng không thiên lệch về dữ liệu vận hành.",
        "- Không đo truy xuất, nội dung trả lời, thao tác cơ sở dữ liệu, phê duyệt hoặc độ đúng pháp lý.",
    ]
    (output / "report.md").write_text("\n".join(rows) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "golden.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "results/golden_live")
    parser.add_argument("--runs", type=Path, help="Chấm đầu ra đã thu thập, không gọi API")
    parser.add_argument("--live", action="store_true", help="Gọi mô hình đang cấu hình; có thể phát sinh phí API")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--timeout", type=int, default=75)
    parser.add_argument("--require-reviewed", action="store_true")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    validate(dataset)
    if args.validate_only:
        print(f"Đã kiểm tra {len(dataset['cases'])} ca và mã băm nguồn; chưa chạy mô hình.")
        return 0
    if args.live == bool(args.runs):
        parser.error("Chọn đúng một trong --live hoặc --runs")
    if args.timeout < 1:
        parser.error("--timeout phải lớn hơn 0")
    if args.live and (args.output_dir / "runs.json").exists() and not args.resume:
        parser.error("Đã có lần chạy; dùng thư mục mới hoặc --resume")
    capture = (
        asyncio.run(
            collect(dataset, args.output_dir, concurrency=args.concurrency, timeout=args.timeout, resume=args.resume)
        )
        if args.live
        else json.loads(args.runs.read_text())
    )
    result = summarize(dataset, capture)
    if args.require_reviewed and result["label_status"] != "reviewed":
        result["status"] = "fail"
        result["review_gate_error"] = "Nhãn chưa được rà soát đầy đủ"
    write_report(result, args.output_dir)
    print(
        json.dumps(
            {k: result[k] for k in ("status", "label_status", "completed_count", "error_count", "passed_count")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
