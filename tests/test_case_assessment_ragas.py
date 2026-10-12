"""Offline checks for missing-output guards and separation of evaluator evidence."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "eval/case_assessment/evaluate_ragas.py"
SPEC = importlib.util.spec_from_file_location("assessment_evaluation", SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def sample(**changes):
    return {"user_input": "Nhân viên vắng 5 ngày; lý do chưa xác minh.",
            "reference": "Chưa đủ thông tin để chốt mức.",
            "reference_contexts": ["Quy định yêu cầu không có lý do chính đáng."],
            "response": "Cần xác minh lý do.",
            "retrieved_contexts": ["Quy định yêu cầu không có lý do chính đáng."], **changes}


def test_draft_is_valid_but_cannot_be_scored():
    result = runner.validate([sample(response=None, retrieved_contexts=None)])
    assert result["schema_valid"]
    assert not result["scoring_ready"]
    assert result["missing_outputs"][0]["missing_fields"] == ["response", "retrieved_contexts"]


def test_empty_actual_retrieval_is_not_missing():
    assert runner.validate([sample(retrieved_contexts=[])])["scoring_ready"]


@pytest.mark.parametrize("changes", [{"response": ""}, {"retrieved_contexts": "not a list"}, {"retrieved_contexts": [None]}])
def test_malformed_outputs_rejected(changes):
    with pytest.raises(ValueError):
        runner.validate([sample(**changes)])


def test_faithfulness_adds_case_input_without_reference_leakage():
    original = sample()
    prepared = runner.metric_rows([original], "faithfulness", False)[0]
    assert prepared["retrieved_contexts"][-1] == runner.FACT_LABEL + "\n" + original["user_input"]
    assert original["reference"] not in prepared["retrieved_contexts"]
    assert len(original["retrieved_contexts"]) == 1


def test_recall_uses_policy_evidence_not_employee_report():
    original = sample()
    prepared = runner.metric_rows([original], "context_recall", False)[0]
    assert prepared["reference"] == original["reference_contexts"][0]
    assert prepared["retrieved_contexts"] == original["retrieved_contexts"]


def test_retrieval_metrics_reject_case_augmented_context():
    augmented = runner.metric_rows([sample()], "faithfulness", False)
    with pytest.raises(ValueError, match="Chỉ số truy xuất"):
        runner.metric_rows(augmented, "context_precision", False)


def test_failed_scores_saved_as_null_not_zero(tmp_path):
    summary = {"status": "partial_failure", "sample_count": 1, "evaluation_scope": "test",
               "metrics": {"faithfulness": {"mean": None, "scored_count": 0}}}
    runner.save_report(tmp_path, summary, [{"case_id": "CA01", "faithfulness": None}])
    saved = json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))
    assert saved[0]["faithfulness"] is None


def test_factual_correctness_reads_mode_qualified_ragas_column(monkeypatch):
    ragas = pytest.importorskip("ragas")
    import pandas as pd

    class Result:
        def to_pandas(self):
            return pd.DataFrame({"factual_correctness(mode=f1)": [0.75]})

    # Exercise the installed metric constructor/export naming, without judge calls.
    monkeypatch.setattr(ragas, "evaluate", lambda *args, **kwargs: Result())
    assert runner.run_metric([sample()], "factual_correctness", object(), 30) == [0.75]


def test_fixed_evidence_scope_requires_matching_captured_outputs(tmp_path):
    row = sample()
    path = tmp_path / "dataset.completed.json"
    provenance = [{"case_id": "CA01", "generation_scope": "fixed_evidence_direct_component", **row}]
    runner.write_json(tmp_path / "generated_runs.json", provenance)
    assert runner.evaluation_scope(path, [row], [{"case_id": "CA01"}]).startswith("fixed_evidence")
    assert runner.evaluation_scope(path, [sample(response="Changed response")], [{"case_id": "CA01"}]) == "captured_outputs"


def test_resume_requires_matching_dataset_and_judge(tmp_path):
    current = {"source_dataset_sha256": "same", "judge_provider": "mistral", "judge_model": "judge",
               "ragas_version": "0.4.3", "faithfulness_context": "policies_plus_supplied_case_input"}
    runner.write_json(tmp_path / "summary.json", {**current, "metrics": {"faithfulness": {"scored_count": 1}}})
    runner.write_json(tmp_path / "scores.json", [{"case_id": "CA01", "faithfulness": 0.7}])
    assert runner.cached_metric(tmp_path, current, "faithfulness", ["CA01"]) == [0.7]
    assert runner.cached_metric(tmp_path, current, "factual_correctness", ["CA01"]) is None
    with pytest.raises(ValueError, match="judge_model"):
        runner.cached_metric(tmp_path, {**current, "judge_model": "different"}, "faithfulness", ["CA01"])


def test_provider_failure_keeps_null_score_and_safe_diagnostic(monkeypatch):
    ragas = pytest.importorskip("ragas")
    import httpx
    import pandas as pd

    class Result:
        def to_pandas(self):
            return pd.DataFrame({"faithfulness": [float("nan")]})

    def evaluate(*args, **kwargs):
        request = httpx.Request("POST", "https://example.invalid")
        response = httpx.Response(429, request=request)
        error = httpx.HTTPStatusError("Sensitive provider message", request=request, response=response)
        kwargs["callbacks"][0].on_llm_error(error)
        return Result()

    monkeypatch.setattr(ragas, "evaluate", evaluate)
    scores = runner.run_metric([sample()], "faithfulness", object(), 30)
    assert scores == [None]
    assert scores.errors == [{"error_type": "HTTPStatusError", "http_status": 429}]


@pytest.mark.parametrize("provider", ["mistral", "gemini", "openrouter"])
def test_each_metric_gets_a_fresh_judge_client(monkeypatch, tmp_path, provider):
    pytest.importorskip("ragas")
    pytest.importorskip("dotenv")
    dataset = tmp_path / "input.json"
    runner.write_json(dataset, [sample()])
    monkeypatch.setattr(runner, "aligned_metadata", lambda *args: [{"case_id": "CA01"}])
    clients, observed = [], []

    def make(*args):
        assert args[0] == provider
        client = object()
        clients.append(client)
        return client

    def score(rows, name, judge, timeout):
        observed.append(judge)
        return [0.8]

    monkeypatch.setattr(runner, "make_judge", make)
    monkeypatch.setattr(runner, "run_metric", score)
    assert runner.main(["--dataset", str(dataset), "--judge-model", "offline-test",
                        "--provider", provider, "--output-dir", str(tmp_path / "out")]) == 0
    assert len(observed) == 4 and len({id(client) for client in observed}) == 4
    saved = runner.read_json(tmp_path / "out" / "scores.json")
    assert set(saved[0]) == {"case_id", *runner.METRICS}
    assert runner.read_json(tmp_path / "out" / "summary.json")["status"] == "complete"


@pytest.mark.parametrize("empty", [False, True])
def test_live_capture_passes_actual_hits_to_assessment_without_reference_leakage(tmp_path, empty):
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4
    from src.features.cite.model.passage import Passage

    hits = [] if empty else [
        Passage(uuid4(), uuid4(), content, "1", None, None, 0.9,
                "INTERNAL_RULE", "POLICY", "Policy")
        for content in ("Actual retrieved passage B", "Actual retrieved passage A")
    ]
    row = sample(response=None, retrieved_contexts=None)
    case = {"case_id": "CA01", "incident_date": "2026-10-05", "family": "GENERAL",
            "model_description": "Source case facts", "source_known_facts": {"minutes_made": "true"},
            "reference_evidence_ids": ["must-not-be-used"]}
    observed = []

    async def search(query):
        assert query.text == "Source case facts\nminutes_made: true"
        assert row["reference"] not in query.text
        return hits

    async def assess(handoff):
        observed.append(handoff)
        assert [p.content for p in handoff.passages] == [p.content for p in hits]
        assert handoff.query == row["user_input"]
        return {"draft": SimpleNamespace(prose="Actual component output",
                decision=SimpleNamespace(sanction_type=None, risk_level="HIGH"))}

    rows = asyncio.run(runner.collect_live_outputs([row], [case], tmp_path, search, assess))
    assert rows[0]["response"] == "Actual component output"
    assert rows[0]["retrieved_contexts"] == [p.content for p in hits]
    assert runner.read_json(tmp_path / "validation.json")["scoring_ready"]
    assert row["response"] is None  # Source fixture is preserved.
    run = runner.read_json(tmp_path / "generated_runs.json")[0]
    assert run["evidence_ids"] == [str(p.chunk_id) for p in hits]
    assert run["retrieval"] == ("empty" if empty else "hybrid")
    assert run["output_kind"] == "component_fallback"
    assert runner.evaluation_scope(tmp_path / "dataset.completed.json", rows, [case]).startswith("live_retrieval")
    changed = [dict(rows[0], retrieved_contexts=["Changed passage"])]
    assert runner.evaluation_scope(tmp_path / "dataset.completed.json", changed, [case]) == "captured_outputs"


def test_fixed_evidence_cannot_be_scored_as_live_retrieval(monkeypatch, tmp_path):
    pytest.importorskip("ragas")
    pytest.importorskip("dotenv")
    row = sample()
    dataset = tmp_path / "dataset.completed.json"
    runner.write_json(dataset, [row])
    runner.write_json(tmp_path / "generated_runs.json", [
        {"case_id": "CA01", "generation_scope": "fixed_evidence_direct_component", **row}])
    monkeypatch.setattr(runner, "aligned_metadata", lambda *args: [{"case_id": "CA01"}])
    with pytest.raises(ValueError, match="Fixed-evidence"):
        runner.main(["--dataset", str(dataset), "--judge-model", "offline-test",
                     "--output-dir", str(tmp_path / "out")])


def test_generation_scores_completed_outputs_and_updates_validation(monkeypatch, tmp_path):
    import hashlib
    pytest.importorskip("ragas")
    pytest.importorskip("dotenv")
    dataset = tmp_path / "draft.json"
    original = sample(response=None, retrieved_contexts=None)
    runner.write_json(dataset, [original])
    output = tmp_path / "out"
    monkeypatch.setattr(runner, "aligned_metadata", lambda *args: [{"case_id": "CA01"}])

    async def generate(rows, cases, destination, timeout):
        completed = [dict(rows[0], response="Actual output", retrieved_contexts=["Live passage"])]
        runner.write_json(destination / "dataset.completed.json", completed)
        runner.write_json(destination / "generated_runs.json", [
            {"case_id": "CA01", "generation_scope": "live_retrieval_direct_component", **completed[0]}])
        return completed

    observed = []
    def score(rows, name, judge, timeout):
        observed.append(name)
        assert rows[0]["response"] == "Actual output"
        assert rows[0]["retrieved_contexts"][0] == "Live passage"
        return [0.8]

    monkeypatch.setattr(runner, "generate_missing", generate)
    monkeypatch.setattr(runner, "make_judge", lambda *args: object())
    monkeypatch.setattr(runner, "run_metric", score)
    assert runner.main(["--dataset", str(dataset), "--generate-missing", "--judge-model", "offline-test",
                        "--output-dir", str(output)]) == 0
    assert observed == list(runner.METRICS)
    assert runner.read_json(output / "validation.json")["scoring_ready"]
    summary = runner.read_json(output / "summary.json")
    completed = runner.read_json(output / "dataset.completed.json")
    expected_hash = hashlib.sha256(json.dumps(completed, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert summary["source_dataset_sha256"] == expected_hash
    assert summary["evaluation_scope"].startswith("live_retrieval")
    assert runner.read_json(dataset) == [original]


@pytest.mark.parametrize("key_name", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
@pytest.mark.parametrize("model,temperature", [("gemini-2.5-flash", 0), ("models/gemini-3.1-pro-preview", 1.0)])
def test_gemini_judge_constructs_installed_client_without_api_calls(monkeypatch, key_name, model, temperature):
    pytest.importorskip("ragas")
    genai = pytest.importorskip("langchain_google_genai")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv(key_name, "offline-test-key")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    judge = runner.make_judge("gemini", model, 60)
    assert isinstance(judge.langchain_llm, genai.ChatGoogleGenerativeAI)
    client = judge.langchain_llm
    assert client.google_api_key.get_secret_value() == "offline-test-key"
    assert client.vertexai is False
    assert client.model.removeprefix("models/") == model.removeprefix("models/")
    assert client.temperature == temperature
    assert client.timeout == 60
    assert client.max_retries == 1
    assert judge.bypass_temperature


def test_gemini_key_precedence_and_missing_credentials(monkeypatch):
    pytest.importorskip("ragas")
    pytest.importorskip("langchain_google_genai")
    monkeypatch.setenv("GOOGLE_API_KEY", "primary-offline-key")
    monkeypatch.setenv("GEMINI_API_KEY", "secondary-offline-key")
    judge = runner.make_judge("gemini", "gemini-2.5-flash", 30)
    assert judge.langchain_llm.google_api_key.get_secret_value() == "primary-offline-key"
    monkeypatch.delenv("GOOGLE_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ValueError, match="GOOGLE_API_KEY or GEMINI_API_KEY"):
        runner.make_judge("gemini", "gemini-2.5-flash", 30)


def test_gemini_model_resolves_from_judge_env_without_using_generation_model(monkeypatch, tmp_path):
    pytest.importorskip("ragas")
    pytest.importorskip("dotenv")
    dataset = tmp_path / "input.json"
    runner.write_json(dataset, [sample()])
    monkeypatch.setenv("RAGAS_JUDGE_MODEL", "independent-gemini-judge")
    monkeypatch.setenv("MODEL_NAME", "mistral-generation-model")
    monkeypatch.setattr(runner, "aligned_metadata", lambda *args: [{"case_id": "CA01"}])
    def make(provider, model, timeout):
        assert provider == "gemini"
        assert model == "independent-gemini-judge"
        return object()
    monkeypatch.setattr(runner, "make_judge", make)
    monkeypatch.setattr(runner, "run_metric", lambda *args: [0.8])
    assert runner.main(["--dataset", str(dataset), "--provider", "gemini",
                        "--output-dir", str(tmp_path / "out")]) == 0
    summary = runner.read_json(tmp_path / "out" / "summary.json")
    assert summary["judge_provider"] == "gemini"
    assert summary["judge_model"] == "independent-gemini-judge"
    assert set(summary["metrics"]) == set(runner.METRICS)
    assert "offline-test-key" not in (tmp_path / "out" / "summary.json").read_text()


def test_google_provider_failure_records_http_code_without_message(monkeypatch):
    ragas = pytest.importorskip("ragas")
    import pandas as pd
    class GoogleError(Exception):
        code = 429
    class Result:
        def to_pandas(self):
            return pd.DataFrame({"faithfulness": [float("nan")]})
    def evaluate(*args, **kwargs):
        kwargs["callbacks"][0].on_llm_error(GoogleError("Sensitive provider message"))
        return Result()
    monkeypatch.setattr(ragas, "evaluate", evaluate)
    scores = runner.run_metric([sample()], "faithfulness", object(), 30)
    assert scores == [None]
    assert scores.errors == [{"error_type": "GoogleError", "http_status": 429}]


def test_ragas_preserves_gemini_reasoning_temperature_during_generation(monkeypatch):
    import asyncio
    pytest.importorskip("ragas")
    genai = pytest.importorskip("langchain_google_genai")
    from langchain_core.outputs import Generation, LLMResult
    from langchain_core.prompt_values import StringPromptValue
    monkeypatch.setenv("GOOGLE_API_KEY", "offline-test-key")
    judge = runner.make_judge("gemini", "gemini-3.1-pro-preview", 30)
    observed = []
    async def generate(self, **kwargs):
        observed.append(self.temperature)
        return LLMResult(generations=[[Generation(text='{"score": 1}')]])
    monkeypatch.setattr(genai.ChatGoogleGenerativeAI, "agenerate_prompt", generate)
    result = asyncio.run(judge.agenerate_text(StringPromptValue(text="offline prompt"), temperature=0.01))
    assert observed == [1.0]
    assert result.generations[0][0].text == '{"score": 1}'


def test_openrouter_judge_uses_own_key_and_endpoint(monkeypatch):
    pytest.importorskip("ragas")
    openai = pytest.importorskip("langchain_openai")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-router-key")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unrelated.invalid/v1")
    judge = runner.make_judge("openrouter", "vendor/judge-model", 60)
    client = judge.langchain_llm
    assert isinstance(client, openai.ChatOpenAI)
    assert client.openai_api_key.get_secret_value() == "offline-router-key"
    assert client.openai_api_base == "https://openrouter.ai/api/v1"
    assert client.model_name == "vendor/judge-model"
    assert client.request_timeout == 60
    assert client.max_retries == 1
    assert client.use_responses_api is False
    assert judge.bypass_temperature


def test_openrouter_requires_its_api_key_even_with_openai_credentials(monkeypatch):
    pytest.importorskip("ragas")
    pytest.importorskip("langchain_openai")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-openai-key")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        runner.make_judge("openrouter", "vendor/judge-model", 30)


def test_openrouter_adapter_sends_chat_request_and_reads_completion(monkeypatch):
    import asyncio
    import httpx
    pytest.importorskip("ragas")
    openai = pytest.importorskip("langchain_openai")
    from langchain_core.prompt_values import StringPromptValue
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-router-key")
    observed = []
    def handle(request):
        observed.append(request)
        return httpx.Response(200, json={
            "id": "offline-completion", "object": "chat.completion", "created": 0,
            "model": "vendor/judge-model", "choices": [{"index": 0,
                "message": {"role": "assistant", "content": '{"score": 1}'},
                "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })
    original = openai.ChatOpenAI
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            monkeypatch.setattr(openai, "ChatOpenAI", lambda **kwargs: original(**kwargs, http_async_client=http))
            judge = runner.make_judge("openrouter", "vendor/judge-model", 30)
            result = await judge.agenerate_text(StringPromptValue(text="Assess this output."))
            assert result.generations[0][0].text == '{"score": 1}'
            assert judge.is_finished(result)
    asyncio.run(exercise())
    assert len(observed) == 1
    assert str(observed[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert observed[0].headers["authorization"] == "Bearer offline-router-key"
    payload = json.loads(observed[0].content)
    assert payload["model"] == "vendor/judge-model"
    assert payload["messages"][0]["content"] == "Assess this output."
    assert "temperature" not in payload
