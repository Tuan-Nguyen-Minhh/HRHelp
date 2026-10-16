"""Đánh giá retrieval thật trên corpus cố định, có chế độ xem trước nhãn nháp.

Không thay đổi cổng nhãn chuyên gia của evaluate.py. Không chạy synthesis hoặc
ghi vào database. --live gọi embeddings/Cohere; --runs chỉ chấm ngoại tuyến.
"""

import argparse
import asyncio
import hashlib
import json
import math
import time
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from .build_dataset import ROOT, eligible
from .snapshot import HERE, fingerprint, read_corpus


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class PacedReranker:
    """Schedule original requests without changing queries, passages or scores."""

    def __init__(self, ranker, interval):
        self.ranker = ranker
        self.interval = interval
        self.last_started = None
        self.lock = asyncio.Lock()
        self.requests = 0

    async def __call__(self, query, passages):
        if passages:
            async with self.lock:
                if self.last_started is not None:
                    delay = self.interval - (time.monotonic() - self.last_started)
                    if delay > 0:
                        await asyncio.sleep(delay)
                self.last_started = time.monotonic()
                self.requests += 1
        return await self.ranker(query, passages)


def validate(dataset, snapshot, root=ROOT):
    if dataset.get("schema_version") != 1 or not dataset.get("cases"):
        raise ValueError("Bộ dữ liệu không hợp lệ")
    if fingerprint(snapshot) != dataset["corpus_sha256"] or snapshot["corpus_sha256"] != dataset["corpus_sha256"]:
        raise ValueError("Ảnh chụp không khớp corpus đã gán nhãn")
    chunks = {c["chunk_id"]: c for c in snapshot["chunks"]}
    if len(chunks) != len(snapshot["chunks"]):
        raise ValueError("Trùng UUID trong ảnh chụp")
    for unit in dataset["units"].values():
        if not unit["member_ids"]:
            raise ValueError("Đơn vị chứng cứ không được rỗng")
        for key in unit["member_ids"]:
            if (
                key not in chunks
                or unit["member_hashes"][key] != hashlib.sha256(chunks[key]["content"].encode()).hexdigest()
            ):
                raise ValueError("UUID hoặc nội dung chứng cứ không khớp")
    ids = [c["case_id"] for c in dataset["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Trùng case_id")
    for case in dataset["cases"]:
        day = case["input"]["incident_date"]
        date.fromisoformat(day)
        if not case["input"]["query"].strip():
            raise ValueError("Query không được rỗng")
        bundles = case["evidence_bundles"]
        if case["expected_empty"]:
            if bundles or case["critical_units"] or any(eligible(c, day) for c in chunks.values()):
                raise ValueError("Ca rỗng phải thực sự không có corpus đủ điều kiện tại ngày đã chọn")
        elif not bundles or any(not b for b in bundles):
            raise ValueError("Ca dương tính phải có ít nhất một bộ chứng cứ không rỗng")
        units = set(case["critical_units"]) | {u for b in bundles for u in b}
        for unit in units:
            if unit not in dataset["units"]:
                raise ValueError("Nhãn trỏ đến đơn vị chứng cứ không tồn tại")
            if not all(eligible(chunks[key], day) for key in dataset["units"][unit]["member_ids"]):
                raise ValueError("Chứng cứ tham chiếu không đủ điều kiện theo metadata DB")
        if set(case["judgments"]) - set(chunks) or any(v not in (0, 1, 2, 3) for v in case["judgments"].values()):
            raise ValueError("Nhãn liên quan không hợp lệ")
        if any(grade > 0 and not eligible(chunks[key], day) for key, grade in case["judgments"].items()):
            raise ValueError("Không gán nhãn liên quan dương tính cho chunk ngoài phiên bản/ngày đủ điều kiện")
        if any(case["judgments"].get(key, 0) <= 0 for unit in units for key in dataset["units"][unit]["member_ids"]):
            raise ValueError("Chứng cứ mong đợi phải có nhãn liên quan dương tính")
        source = case.get("source")
        if source:
            path = root / source["path"]
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError("Nguồn tình huống thiếu hoặc đổi mã băm")
            if not all(p["text"] in case["input"]["query"] for p in source["paragraphs"]):
                raise ValueError("Query không còn chứa trích đoạn nguồn được gán nhãn")


def unit_ids(dataset, units):
    return {key for unit in units for key in dataset["units"][unit]["member_ids"]}


def best_recall(ids, bundles):
    return max(len(ids & b) / len(b) for b in bundles) if bundles else None


def measure(case, run, dataset, snapshot):
    base = {
        "case_id": case["case_id"],
        "status": run.get("status", "error"),
        "origin": case["origin"],
        "input": case["input"],
        "metrics": None,
    }
    if run.get("status") != "complete":
        return {**base, "error": run.get("error", "Chưa có đầu ra"), "passed_checks": None}
    selected = list(dict.fromkeys(run["stages"]["hits"]))
    chosen = set(selected)
    bundles = [unit_ids(dataset, b) for b in case["evidence_bundles"]]
    candidates = set(run["stages"].get("fused", [])) | set(run["stages"].get("expanded", []))
    critical = unit_ids(dataset, case["critical_units"])
    chunks = {c["chunk_id"]: c for c in snapshot["chunks"]}
    invalid = [
        key for key in selected if key not in chunks or not eligible(chunks[key], case["input"]["incident_date"])
    ]
    passages = {p["chunk_id"]: p["content"] for p in run.get("selected_passages", [])}
    altered = [
        key
        for key in selected
        if key not in chunks or key not in passages or chunks[key]["content"] not in passages[key]
    ]
    judged = [key for key in selected if key in case["judgments"]]
    relevant = [key for key in selected if case["judgments"].get(key, 0) > 0]

    def dcg(values):
        return sum((2**value - 1) / math.log2(i + 2) for i, value in enumerate(values))

    eligible_grades = [
        grade for key, grade in case["judgments"].items() if eligible(chunks[key], case["input"]["incident_date"])
    ]
    ideal = dcg(sorted(eligible_grades, reverse=True)[: len(selected)])
    missing = [u for u in case["critical_units"] if not unit_ids(dataset, [u]) <= chosen]
    full_bundle = any(b <= chosen for b in bundles) if bundles else None
    stages = {name: best_recall(set(ids), bundles) for name, ids in run["stages"].items() if name != "hits"}
    graph_gain = None
    if snapshot["references"] and bundles:
        fused = set(run["stages"].get("fused", []))
        graph_gain = best_recall(fused | set(run.get("graph_ids", [])), bundles) - best_recall(fused, bundles)
    metrics = {
        "candidate_recall": best_recall(candidates, bundles),
        "final_recall": best_recall(chosen, bundles),
        "complete_labeled_bundle": full_bundle,
        "critical_chunk_recall": len(critical & chosen) / len(critical) if critical else None,
        "labeled_precision_lower_bound": len(relevant) / len(selected)
        if selected
        else (None if case["expected_empty"] else 0),
        "judged_precision": len(relevant) / len(judged) if judged else None,
        "judgment_coverage": len(judged) / len(selected) if selected else None,
        "ndcg_lower_bound": (dcg([case["judgments"].get(key, 0) for key in selected]) / ideal if ideal else 0)
        if not case["expected_empty"]
        else None,
        "date_eligibility_pass": not invalid,
        "passage_fidelity_pass": not altered,
        "expected_empty_pass": not selected if case["expected_empty"] else None,
        "graph_recall_gain": graph_gain,
        "latency_ms": run["latency_ms"],
        "selected_count": len(selected),
    }
    checks = (
        (not selected if case["expected_empty"] else full_bundle and not missing)
        and not invalid
        and not altered
        and run["healthy"]
    )
    return {
        **base,
        "metrics": metrics,
        "stage_recall": stages,
        "passed_checks": bool(checks),
        "healthy": run["healthy"],
        "health_gaps": run["health_gaps"],
        "evidence_gaps": run["evidence_gaps"],
        "missing_critical_units": missing,
        "ineligible_selected_ids": invalid,
        "altered_selected_ids": altered,
        "unjudged_selected_ids": [key for key in selected if key not in case["judgments"]],
        "selected": [
            {
                "chunk_id": key,
                "policy_code": chunks[key]["policy_code"],
                "article": chunks[key]["article"],
                "clause": chunks[key]["clause"],
                "point": chunks[key]["point"],
                "grade": case["judgments"].get(key),
            }
            for key in selected
            if key in chunks
        ],
    }


def summarize(dataset, snapshot, capture):
    if capture["dataset_sha256"] != digest(dataset) or capture["corpus_sha256"] != dataset["corpus_sha256"]:
        raise ValueError("Không được trộn bộ nhãn hoặc corpus giữa các lần chạy")
    if capture.get("corpus_stable_after_run") is not True:
        raise ValueError("Corpus chưa được xác nhận giữ nguyên sau thu thập; dừng chấm để tránh dùng nhãn cũ.")
    rows = []
    for case in dataset["cases"]:
        run = capture.get("runs", {}).get(case["case_id"], {"status": "error", "error": "Chưa thu thập ca này"})
        if run.get("input_sha256") and run["input_sha256"] != digest(case["input"]):
            raise ValueError("Đầu vào khác lần thu thập")
        rows.append(measure(case, run, dataset, snapshot))
    complete = [r for r in rows if r["metrics"] is not None]
    averages = {}
    for key in complete[0]["metrics"] if complete else []:
        values = [r["metrics"][key] for r in complete if r["metrics"][key] is not None]
        averages[key] = {"mean": sum(values) / len(values) if values else None, "scored_count": len(values)}
    stage_averages = {}
    for stage in ("similarity", "bm25", "lexical", "fused", "seeds", "expanded"):
        values = [r["stage_recall"][stage] for r in complete if r["stage_recall"].get(stage) is not None]
        stage_averages[stage] = {"mean": sum(values) / len(values) if values else None, "scored_count": len(values)}
    reviewed = all(c["reference_status"] == "expert_reviewed" and c.get("reviewer") for c in dataset["cases"])
    return {
        "status": "provisional" if len(complete) == len(rows) else "partial_failure",
        "reference_status": "expert_reviewed" if reviewed else "draft_pending_expert_review",
        "dataset_sha256": digest(dataset),
        "corpus_sha256": dataset["corpus_sha256"],
        "scope_vi": dataset["scope_vi"],
        "configuration": capture["configuration"],
        "sample_count": len(rows),
        "completed_count": len(complete),
        "error_count": len(rows) - len(complete),
        "degraded_count": sum(not r["healthy"] for r in complete),
        "passed_labeled_checks": sum(r["passed_checks"] is True for r in rows),
        "corpus_stable_after_run": capture.get("corpus_stable_after_run"),
        "graph_edges_in_snapshot": len(snapshot["references"]),
        "averages": averages,
        "stage_averages": stage_averages,
        "cases": rows,
    }


async def live_case(case, sessions, snapshot, timeout):
    from sqlalchemy import text

    from src.features.cite.model.pipeline import build_retrieval_graph
    from src.features.cite.model.query import SearchQuery
    from src.features.cite.model.terms import search_terms

    data = case["input"]
    query = SearchQuery(
        text=data["query"],
        description=data["description"],
        family=data["family"],
        fact_lines=[f"{k}: {v}" for k, v in data["facts"].items()],
        incident_date=date.fromisoformat(data["incident_date"]),
        agent_run_id=uuid4(),
    )
    started = time.perf_counter()
    try:
        async with sessions() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            state = await asyncio.wait_for(
                build_retrieval_graph(session).ainvoke(
                    {"query": query, "terms": search_terms(query.family, query.fact_lines, query.description)}
                ),
                timeout,
            )
        stages = {
            name: [str(p.chunk_id) for p in state.get(name, [])]
            for name in ("similarity", "bm25", "lexical", "fused", "seeds", "expanded", "hits")
        }
        gaps = [f"{name}:{status}" for name, status in state.get("arm_status", {}).items() if status != "OK"]
        for name in ("seed_status", "rerank_status"):
            if state.get(name) != "OK":
                gaps.append(f"{name}:{state.get(name)}")
        if state.get("graph_status") == "FAILED":
            gaps.append("graph:FAILED")
        if not stages["similarity"] and any(
            eligible(c, data["incident_date"]) and c["has_embedding"] for c in snapshot["chunks"]
        ):
            gaps.append("VECTOR_EMPTY_WITH_ELIGIBLE_EMBEDDINGS")
        return {
            "status": "complete",
            "input_sha256": digest(data),
            "stages": stages,
            "healthy": not gaps,
            "health_gaps": gaps,
            "arm_status": state.get("arm_status"),
            "rerank_status": state.get("rerank_status"),
            "graph_status": state.get("graph_status"),
            "evidence_gaps": state.get("evidence_gaps", []),
            "supplemented": state.get("supplemented", False),
            "trace": state.get("trace", {}),
            "evidence_size": state.get("evidence_size"),
            "evidence_size_unit": state.get("evidence_size_unit"),
            "graph_ids": [str(p.chunk_id) for p in state.get("expanded", []) if p.origin == "graph"],
            "selected_passages": [
                {
                    "chunk_id": str(p.chunk_id),
                    "content": p.content,
                    "policy_version_id": str(p.policy_version_id),
                    "rerank_score": p.rerank_score,
                    "origin": p.origin,
                    "facet_scores": dict(p.facet_scores),
                }
                for p in state.get("hits", [])
            ],
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "status": "error",
            "input_sha256": digest(data),
            "error": type(exc).__name__,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }


async def collect(dataset, snapshot, output, *, resume=False, timeout=150, rerank_interval=0):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from src.core.config import settings
    from src.features.cite.model import pipeline

    if not settings.MISTRAL_API_KEY.strip() or not settings.COHERE_API_KEY.strip():
        raise ValueError("Cần khóa Mistral và Cohere để đo đúng cấu hình truy xuất hiện tại")
    before = await asyncio.to_thread(read_corpus)
    if before["corpus_sha256"] != dataset["corpus_sha256"]:
        raise ValueError("Corpus DB đã đổi; dừng trước khi gọi API. Hãy chụp lại và rà soát nhãn.")
    names = (
        "EMBEDDING_MODEL",
        "EMBEDDING_DIMENSIONS",
        "COHERE_RERANK_MODEL",
        "COHERE_RERANK_TIMEOUT_SECONDS",
        "RETRIEVAL_CANDIDATE_K",
        "RETRIEVAL_FUSION_K",
        "RETRIEVAL_FINAL_K",
        "RETRIEVAL_BM25_MAX_CORPUS",
        "RETRIEVAL_GRAPH_INCOMING",
        "RETRIEVAL_EVIDENCE_MAX_BYTES",
        "RETRIEVAL_EVIDENCE_TOKEN_BUDGET",
    )
    config = {name: getattr(settings, name) for name in names}
    config.update(
        scope="live_production_retrieval_graph_readonly_no_synthesis",
        case_timeout=timeout,
        exact_tokenizer_configured=bool(settings.SYNTHESIS_TOKENIZER_PATH),
        rerank_request_interval_seconds=rerank_interval,
    )
    result = {
        "dataset_sha256": digest(dataset),
        "corpus_sha256": dataset["corpus_sha256"],
        "configuration": config,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "runs": {},
    }
    path = output / "runs.json"
    if resume and path.exists():
        previous = json.loads(path.read_text())
        if any(previous[k] != result[k] for k in ("dataset_sha256", "corpus_sha256", "configuration")):
            raise ValueError("Không thể tiếp tục khi corpus, nhãn hoặc cấu hình đã thay đổi")
        result = previous
    output.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        temp.replace(path)

    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, connect_args={"timeout": 10})
    sessions = async_sessionmaker(engine)
    original_ranker = pipeline.rerank
    pacer = PacedReranker(original_ranker, rerank_interval)
    if rerank_interval:
        pipeline.rerank = pacer
    try:
        for case in dataset["cases"]:
            if result["runs"].get(case["case_id"], {}).get("status") == "complete":
                continue
            record = await live_case(case, sessions, snapshot, timeout)
            result["runs"][case["case_id"]] = record
            checkpoint()
            print(
                f"{case['case_id']}: {record['status']}, khỏe={record.get('healthy')}, "
                f"{len(record.get('stages', {}).get('hits', []))} đoạn, {record['latency_ms']} ms",
                flush=True,
            )
        after = await asyncio.to_thread(read_corpus)
        result["corpus_stable_after_run"] = after["corpus_sha256"] == dataset["corpus_sha256"]
        result["completed_at_utc"] = datetime.now(UTC).isoformat()
        result["rerank_requests_in_this_process"] = pacer.requests if rerank_interval else None
        checkpoint()
        return result
    finally:
        pipeline.rerank = original_ranker
        await engine.dispose()


def fmt(value):
    if isinstance(value, bool):
        return "Có" if value else "Không"
    return "Chưa có điểm" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)


def write_report(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    labels = {
        "candidate_recall": "Recall tập ứng viên",
        "final_recall": "Recall gói chứng cứ cuối",
        "complete_labeled_bundle": "Tỷ lệ giữ đủ một bộ chứng cứ tối thiểu đã gán nhãn",
        "critical_chunk_recall": "Recall chunk quan trọng",
        "labeled_precision_lower_bound": "Precision cận dưới theo nhãn hiện có",
        "judged_precision": "Precision chỉ trên các đoạn đã gán nhãn",
        "judgment_coverage": "Tỷ lệ đầu ra đã có nhãn",
        "ndcg_lower_bound": "nDCG cận dưới theo nhãn hiện có",
        "date_eligibility_pass": "Tỷ lệ đúng bộ lọc phiên bản/ngày",
        "passage_fidelity_pass": "Tỷ lệ giữ nguyên toàn bộ nội dung các chunk được chọn",
        "expected_empty_pass": "Tỷ lệ ca không có corpus đủ điều kiện trả về rỗng",
        "graph_recall_gain": "Mức tăng recall từ các ứng viên có nguồn đồ thị",
        "latency_ms": "Thời gian trung bình (ms)",
        "selected_count": "Số đoạn cuối trung bình",
    }
    rows = [
        "# Đánh giá chất lượng truy xuất",
        "",
        "Trạng thái nhãn: **"
        + (
            "Đã được chuyên gia rà soát"
            if result["reference_status"] == "expert_reviewed"
            else "Bản nháp chờ chuyên gia rà soát"
        )
        + "**.",
        "",
        result["scope_vi"],
        "",
        f"Đã chạy {result['completed_count']}/{result['sample_count']} ca; "
        f"lỗi xử lý: {result['error_count']}; đầu ra suy giảm: {result['degraded_count']}; "
        f"đạt đủ phép kiểm tra đã gán nhãn: {result['passed_labeled_checks']}.",
        "",
        "Cảnh báo gói chứng cứ (số ca): "
        + (
            ", ".join(
                f"`{gap}`: {sum(gap in c.get('evidence_gaps', []) for c in result['cases'])}"
                for gap in sorted({g for c in result["cases"] for g in c.get("evidence_gaps", [])})
            )
            or "Không có"
        )
        + ". Các cảnh báo này được báo riêng, không bị xóa bởi kết quả đạt bộ nhãn tối thiểu.",
        "",
        "Nhãn chưa bao phủ hết đoạn liên quan. Precision/nDCG cận dưới coi đoạn chưa gán nhãn là 0 để chẩn đoán, "
        "không chứng minh chúng không liên quan. Precision trên nhãn phải đọc cùng tỷ lệ đầu ra đã có nhãn.",
        "",
        f"Số cạnh dẫn chiếu trong DB được chụp: **{result['graph_edges_in_snapshot']}**. "
        + (
            "Không đủ dữ liệu để đo lợi ích mở rộng đồ thị."
            if not result["graph_edges_in_snapshot"]
            else "Theo dõi nguồn ứng viên đồ thị riêng với tìm bổ sung."
        ),
        "",
        f"Corpus giữ nguyên sau lần chạy: **{fmt(result['corpus_stable_after_run'])}**.",
        "",
        f"Khoảng cách tối thiểu giữa các request rerank: {result['configuration'].get('rerank_request_interval_seconds', 0)} giây. "
        "Thời gian đo bao gồm chờ điều tiết API; không dùng làm độ trễ phục vụ người dùng.",
        "",
        "| Chỉ số | Trung bình | Số ca có điểm |",
        "| --- | --- | --- |",
    ]
    rows += [
        f"| {labels.get(k, k)} (`{k}`) | {fmt(v['mean'])} | {v['scored_count']} |"
        for k, v in result["averages"].items()
    ]
    stage_labels = {
        "similarity": "Ứng viên vector",
        "bm25": "Ứng viên BM25",
        "lexical": "Ứng viên từ khóa",
        "fused": "Pool RRF",
        "seeds": "Hạt giống top-5 cho đồ thị (không thay pool RRF)",
        "expanded": "Pool mở rộng và tìm bổ sung nếu có",
    }
    rows += [
        "",
        "## Recall theo giai đoạn",
        "",
        "| Giai đoạn | Recall trung bình | Số ca có điểm |",
        "| --- | --- | --- |",
    ]
    rows += [
        f"| {stage_labels.get(k, k)} | {fmt(v['mean'])} | {v['scored_count']} |"
        for k, v in result.get("stage_averages", {}).items()
    ]
    rows += [
        "",
        "## Kết quả từng ca",
        "",
        "| Ca | Recall ứng viên | Recall cuối | Đủ bộ nhãn | Recall quan trọng | Hệ thống khỏe |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in result["cases"]:
        m = case["metrics"] or {}
        rows.append(
            f"| {case['case_id']} | {fmt(m.get('candidate_recall'))} | {fmt(m.get('final_recall'))} | {fmt(m.get('complete_labeled_bundle'))} | {fmt(m.get('critical_chunk_recall'))} | {fmt(case.get('healthy'))} |"
        )
    rows += ["", "## Chi tiết chứng cứ và lỗi", ""]
    for case in result["cases"]:
        rows += [
            f"### {case['case_id']}",
            "",
            case["input"]["query"],
            "",
            f"Ngày dùng để lọc: {case['input']['incident_date']}.",
            "",
        ]
        if case["metrics"] is None:
            rows += [f"- Lỗi xử lý: `{case.get('error')}`; điểm để trống.", ""]
            continue
        rows += [
            f"- Đơn vị quan trọng bị thiếu: {case['missing_critical_units']}.",
            f"- Lỗi phiên bản/ngày: {case['ineligible_selected_ids']}.",
            f"- Đoạn bị thiếu hoặc thay đổi nội dung: {case['altered_selected_ids']}.",
            f"- Trạng thái suy giảm: {case['health_gaps']}.",
            f"- Cảnh báo gói chứng cứ: {case['evidence_gaps']}.",
            f"- Số đoạn chưa gán nhãn: {len(case['unjudged_selected_ids'])}.",
            "",
            "| Văn bản | Điều/khoản/điểm | Mức liên quan | UUID |",
            "| --- | --- | --- | --- |",
        ]
        rows += [
            f"| {r['policy_code']} | {r['article']}/{r['clause'] or '-'}/{r['point'] or '-'} | {r['grade'] if r['grade'] is not None else 'Chưa gán nhãn'} | `{r['chunk_id']}` |"
            for r in case["selected"]
        ]
        rows += [""]
    rows += [
        "## Giới hạn",
        "",
        "- Ngày hiệu lực là metadata của ứng dụng, chưa được xác minh như kết luận pháp lý. Ngày của các ca là giá trị giả lập được khai báo riêng.",
        "- Bộ nhãn được tạo trước khi chạy retrieval; không dùng đầu ra mô hình làm đáp án. Nhãn vẫn cần HR/pháp chế rà soát.",
        "- Đủ bộ nhãn chỉ có nghĩa giữ đủ nhóm chứng cứ tối thiểu đã định nghĩa, không chứng minh đủ mọi căn cứ pháp lý.",
        "- Các ca chỉ đo graph truy xuất thật với giao dịch chỉ đọc; không đo synthesis, lưu hồ sơ, hội thoại đầu cuối hoặc phê duyệt.",
        "- Lỗi xử lý có điểm null; đầu ra suy giảm vẫn được chấm như quan sát thực tế và được đếm riêng.",
    ]
    (output / "report.md").write_text("\n".join(rows) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "golden.json")
    parser.add_argument("--snapshot", type=Path, default=HERE / "corpus_snapshot.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "results/golden_live")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--allow-draft", action="store_true", help="Chỉ xem trước số đo với nhãn nháp; không xác nhận nhãn chuyên gia"
    )
    parser.add_argument("--live", action="store_true", help="Gọi DB chỉ đọc, Mistral và Cohere; có phí API")
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout", type=int, default=150)
    parser.add_argument(
        "--rerank-interval", type=float, default=0, help="Giãn cách request Cohere trong bộ chạy, không đổi thuật toán"
    )
    args = parser.parse_args()
    dataset, snapshot = json.loads(args.dataset.read_text()), json.loads(args.snapshot.read_text())
    validate(dataset, snapshot)
    if args.validate_only:
        print(f"Đã kiểm tra {len(dataset['cases'])} ca, UUID/nội dung và phiên bản trong ảnh chụp; không gọi API.")
        return 0
    if args.live == bool(args.runs):
        parser.error("Chọn đúng một trong --live hoặc --runs")
    reviewed = all(c["reference_status"] == "expert_reviewed" and c.get("reviewer") for c in dataset["cases"])
    if not reviewed and not args.allow_draft:
        parser.error("Nhãn chưa được chuyên gia duyệt. Chỉ dùng --allow-draft để xem trước và báo rõ giới hạn.")
    if args.timeout < 1 or args.rerank_interval < 0:
        parser.error("Timeout phải lớn hơn 0; khoảng cách request không được âm")
    if args.live and (args.output_dir / "runs.json").exists() and not args.resume:
        parser.error("Đã có lần chạy; dùng thư mục mới hoặc --resume")
    capture = (
        asyncio.run(
            collect(
                dataset,
                snapshot,
                args.output_dir,
                resume=args.resume,
                timeout=args.timeout,
                rerank_interval=args.rerank_interval,
            )
        )
        if args.live
        else json.loads(args.runs.read_text())
    )
    result = summarize(dataset, snapshot, capture)
    write_report(result, args.output_dir)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "reference_status",
                    "completed_count",
                    "error_count",
                    "degraded_count",
                    "passed_labeled_checks",
                    "averages",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return (
        0
        if result["error_count"] == 0 and result["degraded_count"] == 0 and result["corpus_stable_after_run"] is True
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
