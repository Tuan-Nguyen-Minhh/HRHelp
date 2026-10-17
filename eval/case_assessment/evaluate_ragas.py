"""Evaluate real policy retrieval and case assessment with four RAGAS metrics."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import sys
import warnings
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
METRICS = ("faithfulness", "factual_correctness", "context_precision", "context_recall")
FACT_LABEL = "[Supporting case input; not a retrieved policy document]"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def validate(rows: list[dict]) -> dict:
    """Separate valid draft samples from samples ready for actual scoring."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("Dataset phải là danh sách JSON không rỗng.")
    missing, empty_retrieval = [], []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Mẫu {i + 1}: phải là object JSON.")
        for field in ("user_input", "reference"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Mẫu {i + 1}: {field} phải là chuỗi không rỗng.")
        for field in ("reference_contexts", "retrieved_contexts"):
            value = row.get(field)
            if value is not None and (not isinstance(value, list) or any(not isinstance(s, str) or not s.strip() for s in value)):
                raise ValueError(f"Mẫu {i + 1}: {field} phải là danh sách chuỗi hoặc null.")
        response = row.get("response")
        if response is not None and (not isinstance(response, str) or not response.strip()):
            raise ValueError(f"Mẫu {i + 1}: response phải là chuỗi không rỗng hoặc null.")
        fields = [field for field in ("response", "retrieved_contexts") if row.get(field) is None]
        if fields:
            missing.append({"row_index": i, "missing_fields": fields})
        if row.get("retrieved_contexts") == []:
            empty_retrieval.append(i)
    return {"sample_count": len(rows), "schema_valid": True,
            "scoring_ready": not missing, "missing_outputs": missing,
            "empty_retrieval_rows": empty_retrieval}


def metric_rows(rows: list[dict], name: str, policy_only_faithfulness: bool) -> list[dict]:
    """Keep case facts out of retrieval metrics, and references out of grounding."""
    result = []
    for i, row in enumerate(rows):
        sample = dict(row)
        sample["retrieved_contexts"] = list(row["retrieved_contexts"])
        if name == "faithfulness" and not policy_only_faithfulness:
            if not any(s.startswith(FACT_LABEL) for s in sample["retrieved_contexts"]):
                sample["retrieved_contexts"].append(FACT_LABEL + "\n" + row["user_input"])
        elif name in {"context_precision", "context_recall"}:
            if any(s.startswith(FACT_LABEL) for s in sample["retrieved_contexts"]):
                raise ValueError("Chỉ số truy xuất yêu cầu dataset chưa bổ sung ngữ cảnh tình tiết.")
            evidence = row.get("reference_contexts")
            if not evidence:
                raise ValueError(f"Mẫu {i + 1}: cần reference_contexts để đánh giá chứng cứ chính sách.")
            # Full reports contain employee facts, which policy chunks cannot recall.
            sample["reference"] = "\n\n".join(evidence)
        result.append(sample)
    return result


def aligned_metadata(path: Path, rows: list[dict]) -> list[dict]:
    manifest = read_json(path)
    cases = manifest["cases"]
    expected = read_json(path.parent / "ragas_dataset.json")
    if len(cases) != len(rows) or len(expected) != len(rows):
        raise ValueError("Metadata không khớp số mẫu của dataset.")
    for i, (row, original) in enumerate(zip(rows, expected, strict=True)):
        if row["user_input"] != original["user_input"] or row["reference"] != original["reference"]:
            raise ValueError(f"Mẫu {i + 1}: đầu vào/tham chiếu khác bộ dữ liệu gắn với metadata.")
    return cases


def evaluation_scope(dataset_path: Path, rows: list[dict], cases: list[dict]) -> str:
    provenance_path = dataset_path.parent / "generated_runs.json"
    if not provenance_path.exists():
        return "captured_outputs"
    records = read_json(provenance_path)
    by_id = {record["case_id"]: record for record in records}
    scopes = set()
    for row, case in zip(rows, cases, strict=True):
        record = by_id.get(case["case_id"], {})
        scopes.add(record.get("generation_scope"))
        if record.get("generation_scope") not in {"fixed_evidence_direct_component", "live_retrieval_direct_component"} or any(
            record.get(field) != row.get(field) for field in ("user_input", "response", "retrieved_contexts")
        ):
            return "captured_outputs"
    if scopes == {"live_retrieval_direct_component"}:
        return "live_retrieval_direct_component; not end-to-end chat"
    if scopes == {"fixed_evidence_direct_component"}:
        return "fixed_evidence_direct_component; not live retrieval or end-to-end chat"
    return "mixed_captured_outputs"


async def collect_live_outputs(rows: list[dict], cases: list[dict], output: Path, search, assess) -> list[dict]:
    """Capture actual ranked hits and the assessment produced from those hits.

    Search and assessment adapters are injectable for offline integration tests.
    References and snapshot passages are never supplied to either component.
    """
    from src.features.cite.model.graph import handoff_node, retrieve_node

    generated = [dict(row) for row in rows]
    previous_path = output / "generated_runs.json"
    previous = read_json(previous_path) if previous_path.exists() else []
    runs = []
    for row, case in zip(generated, cases, strict=True):
        if row.get("response") is not None and row.get("retrieved_contexts") is not None:
            matching = next((run for run in previous
                             if run.get("case_id") == case["case_id"]
                             and all(run.get(key) == row.get(key)
                                     for key in ("user_input", "response", "retrieved_contexts"))), None)
            if matching:
                runs.append(matching)
            continue
        print(f"Retrieve and assess {case['case_id']}...", flush=True)
        facts = dict(case["source_known_facts"])
        state = {
            "incident_date": date.fromisoformat(case["incident_date"]),
            "agent_run_id": uuid4(), "description": case["model_description"],
            "family": case["family"], "facts": facts,
            "fact_lines": [f"{key}: {value}" for key, value in facts.items()],
        }
        state.update(await retrieve_node(search)(state))
        handoff = handoff_node(state)["handoff"]
        print(f"Retrieved {len(handoff.passages)} passages ({handoff.retrieval}); assessing...", flush=True)
        # Keep the exact benchmark request visible to the assessment component.
        handoff = handoff.model_copy(update={"query": row["user_input"]})
        result = await assess(handoff)
        draft = result["draft"]
        if not isinstance(draft.prose, str) or not draft.prose.strip():
            raise RuntimeError(f"{case['case_id']}: assessment returned no output.")
        row["response"] = draft.prose
        # Preserve retrieval rank for context precision, including empty retrieval.
        row["retrieved_contexts"] = [p.content for p in handoff.passages]
        runs.append({
            "case_id": case["case_id"], "user_input": row["user_input"],
            "response": row["response"], "retrieved_contexts": row["retrieved_contexts"],
            "generation_scope": "live_retrieval_direct_component",
            "retrieval": handoff.retrieval, "retrieval_query": state["query"],
            "incident_date": case["incident_date"],
            "captured_at": datetime.now(UTC).isoformat(),
            "sanction_type": draft.decision.sanction_type,
            "risk_level": draft.decision.risk_level,
            "evidence_ids": [str(p.chunk_id) for p in handoff.passages],
            "passages": [p.model_dump(mode="json") for p in handoff.passages],
            "output_kind": ("assessment_report" if draft.prose.strip().startswith(
                "BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC") else "component_fallback"),
        })
        write_json(output / "generated_runs.json", runs)
        write_json(output / "dataset.completed.json", generated)
        write_json(output / "validation.json", validate(generated))
    return generated


async def generate_missing(rows: list[dict], cases: list[dict], output: Path, timeout: int = 180) -> list[dict]:
    """Run the production retrieval and assessment graphs without business writes."""
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from src.core.config import settings
    from src.features.answer.model.agent import build_recommend_agent
    from src.features.cite.model.pipeline import build_retrieval_graph
    from src.features.cite.model.terms import search_terms

    if not settings.MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is required for live retrieval and assessment.")
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, connect_args={"timeout": 10})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    agent = build_recommend_agent()

    async def search(query):
        async with sessions() as session:
            # Preflight fails visibly if the database is unavailable; the production
            # graph otherwise catches arm errors and continues with other arms.
            await session.execute(text("SET TRANSACTION READ ONLY"))
            await session.execute(text("SELECT 1"))
            state = await asyncio.wait_for(build_retrieval_graph(session).ainvoke({
                "query": query,
                "terms": search_terms(query.family, query.fact_lines, query.description),
            }), timeout=timeout)
            return list(state.get("hits") or [])

    async def assess(handoff):
        return await asyncio.wait_for(agent.ainvoke({"handoff": handoff}), timeout=timeout)

    try:
        return await collect_live_outputs(rows, cases, output, search, assess)
    finally:
        await engine.dispose()


def make_judge(provider: str, model: str, timeout: int):
    from ragas.llms import LangchainLLMWrapper
    from ragas.run_config import RunConfig
    if provider == "mistral":
        from langchain_mistralai import ChatMistralAI
        key = os.environ.get("MISTRAL_API_KEY")
        if not key:
            raise ValueError("Thiếu MISTRAL_API_KEY cho mô hình chấm điểm.")
        kwargs = {"api_key": key}
        if os.environ.get("MISTRAL_BASE_URL"):
            kwargs["base_url"] = os.environ["MISTRAL_BASE_URL"]
        client = ChatMistralAI(model=model, temperature=0, timeout=timeout, max_tokens=8192, max_retries=1, **kwargs)
    elif provider == "gemini":
        key = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError("Set GOOGLE_API_KEY or GEMINI_API_KEY for the Gemini judge.")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as error:
            raise ValueError("Install eval/case_assessment/requirements.txt to use the Gemini judge.") from error
        # Use the API-key Developer API regardless of ambient Vertex configuration.
        # Google recommends temperature 1.0 for Gemini 3 reasoning models.
        temperature = 1.0 if model.removeprefix("models/").startswith("gemini-3") else 0
        client = ChatGoogleGenerativeAI(
            model=model, api_key=key, vertexai=False, temperature=temperature,
            timeout=timeout, max_tokens=8192, max_retries=1,
        )
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not key:
            raise ValueError("Set DEEPSEEK_API_KEY for the DeepSeek judge.")
        client = ChatOpenAI(
            model=model, api_key=key,
            base_url=(os.environ.get("DEEPSEEK_BASE_URL") or "").strip() or "https://api.deepseek.com",
            timeout=timeout, max_retries=1, max_tokens=8192,
            use_responses_api=False,
            # RAGAS claim extraction/inference can require several calls per
            # sample. Avoid spending the scoring deadline on hidden reasoning.
            extra_body={"thinking": {"type": "disabled"}},
        )
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        if not key:
            raise ValueError("Set OPENROUTER_API_KEY for the OpenRouter judge.")
        client = ChatOpenAI(
            model=model, api_key=key, base_url="https://openrouter.ai/api/v1",
            timeout=timeout, max_retries=1, max_tokens=8192,
            use_responses_api=False,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("Thiếu OPENAI_API_KEY cho mô hình chấm điểm.")
        client = ChatOpenAI(model=model, temperature=0, timeout=timeout, max_retries=1)
    else:
        raise ValueError(f"Unsupported judge provider: {provider}")
    # Preserve Gemini settings and compatible-provider sampling defaults.
    return LangchainLLMWrapper(
        client, run_config=RunConfig(timeout=timeout),
        bypass_temperature=(provider in {"gemini", "openrouter", "deepseek"}),
    )


class MetricScores(list):
    def __init__(self, values, errors):
        super().__init__(values)
        self.errors = errors


def run_metric(rows: list[dict], name: str, judge, timeout: int) -> list[float | None]:
    from langchain_core.callbacks import BaseCallbackHandler
    from ragas import EvaluationDataset, evaluate

    class ErrorRecorder(BaseCallbackHandler):
        def __init__(self):
            self.errors = []

        def on_chain_error(self, error, **kwargs):
            item = {"error_type": type(error).__name__}
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status is None and isinstance(getattr(error, "code", None), int):
                status = error.code  # Google GenAI API errors expose HTTP status as code.
            if status is not None:
                item["http_status"] = status
            if item not in self.errors:
                self.errors.append(item)

        on_llm_error = on_chain_error

    recorder = ErrorRecorder()
    # The evaluate API and its metric adapters are supported by the pinned 0.4.3 runtime.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from ragas.metrics import FactualCorrectness, Faithfulness, LLMContextPrecisionWithReference, LLMContextRecall
    from ragas.run_config import RunConfig
    classes = {"faithfulness": Faithfulness, "factual_correctness": FactualCorrectness,
               "context_precision": LLMContextPrecisionWithReference, "context_recall": LLMContextRecall}
    metric = classes[name]()
    print(f"Chấm {name} cho {len(rows)} mẫu...", flush=True)
    result = evaluate(
        EvaluationDataset.from_list(rows), metrics=[metric], llm=judge,
        run_config=RunConfig(timeout=timeout, max_retries=3, max_wait=30, max_workers=1),
        callbacks=[recorder], raise_exceptions=False, show_progress=True,
    )
    # RAGAS adds the scoring mode to FactualCorrectness's exported column name.
    column = f"{metric.name}(mode={metric.mode})" if name == "factual_correctness" else metric.name
    scores = result.to_pandas()[column].tolist()
    return MetricScores(
        [float(value) if value is not None and math.isfinite(float(value)) else None for value in scores],
        recorder.errors,
    )


def save_report(output: Path, summary: dict, scores: list[dict]) -> None:
    write_json(output / "summary.json", summary)
    write_json(output / "scores.json", scores)
    if scores:
        with (output / "scores.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(scores[0]))
            writer.writeheader()
            writer.writerows(scores)
    lines = ["# Kết quả đánh giá hồ sơ bằng RAGAS", "",
             f"Trạng thái: {summary['status']}. Số mẫu: {summary['sample_count']}.", "",
             f"Phạm vi: {summary['evaluation_scope']}.",
             "Đáp án tham chiếu là bản nháp chưa được chuyên gia xác nhận.", ""]
    if summary.get("metrics"):
        lines += ["| Chỉ số | Trung bình | Mẫu có điểm |", "| --- | --- | --- |"]
        for name, item in summary["metrics"].items():
            mean = f"{item['mean']:.4f}" if item["mean"] is not None else "Chưa có"
            lines.append(f"| {name} | {mean} | {item['scored_count']}/{summary['sample_count']} |")
    lines += ["", "Faithfulness mặc định kiểm tra cả tình tiết đầu vào và chứng cứ chính sách.",
              "Chỉ số truy xuất, nếu được chọn, chỉ dùng chứng cứ chính sách làm tham chiếu; không dùng tình tiết nhân viên.",
              "Điểm còn thiếu được ghi null, không chuyển thành 0 hoặc coi là thành công.",
              "Nếu dùng chứng cứ cố định, điểm không đo chất lượng bộ truy xuất trực tiếp.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def cached_metric(output: Path, current: dict, name: str, case_ids: list[str]) -> list[float] | None:
    if not (output / "summary.json").exists() or not (output / "scores.json").exists():
        return None
    previous = read_json(output / "summary.json")
    for field in ("source_dataset_sha256", "judge_provider", "judge_model", "ragas_version", "faithfulness_context", "evaluation_scope"):
        if previous.get(field) != current.get(field):
            raise ValueError(f"Không thể resume: cấu hình {field} khác lần chạy đã lưu.")
    if previous.get("metrics", {}).get(name, {}).get("scored_count") != len(case_ids):
        return None
    rows = read_json(output / "scores.json")
    if [row.get("case_id") for row in rows] != case_ids:
        raise ValueError("Không thể resume: mã hoặc thứ tự mẫu khác kết quả đã lưu.")
    values = [row.get(name) for row in rows]
    if any(not isinstance(value, (int, float)) or isinstance(value, bool)
           or not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        return None
    return [float(value) for value in values]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "ragas_dataset.json")
    parser.add_argument("--metadata", type=Path, default=HERE / "source_metadata.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "results" / "live_retrieval")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--generate-missing", action="store_true",
                        help="Run production retrieval and assessment for missing outputs")
    parser.add_argument("--generate-only", action="store_true",
                        help="Capture missing live outputs without calling the RAGAS judge")
    parser.add_argument("--resume", action="store_true", help="Dùng lại chỉ số đã chấm đủ nếu dữ liệu và cấu hình không đổi")
    parser.add_argument("--provider", choices=("mistral", "openai", "gemini", "openrouter", "deepseek"), default="mistral")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--metrics", default=",".join(METRICS))
    parser.add_argument("--policy-only-faithfulness", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    rows = read_json(args.dataset)
    validation = validate(rows)
    from ragas import EvaluationDataset
    EvaluationDataset.from_list(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "validation.json", validation)
    if args.validate_only:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0
    names = [name.strip() for name in args.metrics.split(",")]
    if not names or len(names) != len(set(names)) or any(name not in METRICS for name in names):
        raise ValueError(f"Chỉ số hợp lệ: {', '.join(METRICS)}; không được trùng.")
    if not validation["scoring_ready"] and not (args.generate_missing or args.generate_only):
        raise ValueError("Dataset chưa có response/retrieved_contexts. Cung cấp dataset đã ghép hoặc dùng --generate-missing để chạy thành phần đánh giá với truy xuất thực tế.")
    from dotenv import load_dotenv
    load_dotenv(args.env_file, override=False)
    model = args.judge_model or os.environ.get("RAGAS_JUDGE_MODEL") or (os.environ.get("MODEL_NAME") if args.provider == "mistral" else None)
    if not model and args.provider == "deepseek":
        model = "deepseek-flash"
    if not model and not args.generate_only:
        raise ValueError("Chỉ định --judge-model hoặc RAGAS_JUDGE_MODEL.")
    cases = aligned_metadata(args.metadata, rows)
    scope = evaluation_scope(args.dataset, rows, cases)
    if (args.generate_missing or args.generate_only) and not validation["scoring_ready"]:
        rows = asyncio.run(generate_missing(rows, cases, args.output_dir, args.timeout))
        args.dataset = args.output_dir / "dataset.completed.json"
        scope = evaluation_scope(args.dataset, rows, cases)
    if not validate(rows)["scoring_ready"]:
        raise ValueError("Vẫn còn mẫu thiếu đầu ra; chưa thể chấm điểm.")
    write_json(args.output_dir / "validation.json", validate(rows))
    if args.generate_only:
        print(f"Captured {len(rows)} samples. No RAGAS scoring requested.")
        return 0
    if scope.startswith("fixed_evidence") and any(name.startswith("context_") for name in names):
        raise ValueError("Fixed-evidence outputs cannot measure live retrieval. Use the draft dataset with --generate-missing and a new output directory.")
    scores = [{"case_id": case["case_id"], **{name: None for name in names}} for case in cases]
    summary = {"status": "running", "sample_count": len(rows), "evaluation_scope": scope,
               "ragas_version": importlib.metadata.version("ragas"), "judge_provider": args.provider,
               "judge_model": model, "created_at": datetime.now(UTC).isoformat(),
               "source_dataset": str(args.dataset),
               "source_dataset_sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
               "reference_status": "draft_pending_expert_review",
               "faithfulness_context": "policies_only" if args.policy_only_faithfulness else "policies_plus_supplied_case_input",
               "requested_metrics": names, "metrics": {}, "errors": []}
    cached = {name: cached_metric(args.output_dir, summary, name, [case["case_id"] for case in cases])
              if args.resume else None for name in names}
    for name in names:
        prepared = metric_rows(rows, name, args.policy_only_faithfulness)
        try:
            values = cached[name]
            if values is None:
                # Each evaluate() call owns a separate asyncio loop. HTTP clients
                # must not be reused across those loops (especially ChatMistralAI).
                judge = make_judge(args.provider, model, args.timeout)
                values = run_metric(prepared, name, judge, args.timeout)
                summary["errors"].extend({"metric": name, **item} for item in getattr(values, "errors", []))
            else:
                print(f"Dùng lại {name}: {len(values)} điểm đã lưu.", flush=True)
            if len(values) != len(rows):
                raise RuntimeError("RAGAS trả số điểm không khớp số mẫu.")
        except Exception as error:
            values = [None] * len(rows)
            summary["errors"].append({"metric": name, "error_type": type(error).__name__})
        for row, value in zip(scores, values, strict=True):
            row[name] = value
        valid = [value for value in values if value is not None]
        summary["metrics"][name] = {"mean": sum(valid) / len(valid) if valid else None,
                                    "scored_count": len(valid), "failed_count": len(values) - len(valid)}
        summary["status"] = (
            "running" if len(summary["metrics"]) < len(names)
            else "complete" if all(m["failed_count"] == 0 for m in summary["metrics"].values())
            else "partial_failure"
        )
        save_report(args.output_dir, summary, scores)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        # Avoid dumping request objects, API keys, or provider response bodies.
        print(f"Không thể đánh giá: {error}", file=sys.stderr)
        raise SystemExit(2)
    except Exception as error:
        print(f"Evaluation failed: {type(error).__name__}; check database/service availability.", file=sys.stderr)
        raise SystemExit(2)
