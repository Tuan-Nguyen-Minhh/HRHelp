"""Drafting minutes checks facts, persists a form, and does not approve a case."""

from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agents.case_graph import build_case_graph, route_after_intent
from src.agents.handoff import CaseHandoff
from src.common.errors import AppError
from src.features.answer.schema import AnswerView
from src.features.assessment import service
from src.features.clarify.model import turns
from src.features.clarify.model.assess import StoredFact, assess
from src.features.clarify.model.decision import CaseFamily, ClarifyDecision, RequestedAction, UserIntent
from src.features.clarify.model.graph import extract_node
from src.features.clarify.model.intent import IntentDecision, IntentFallback, IntentResult, Route
from src.features.clarify.model.memory import update_memory
from src.features.clarify.model.planner import PlannerResult
from src.features.clarify.model.policy import apply_decision
from src.models.agent_runs import AgentRun

_TEXT = "Nhân viên nghỉ không phép 5 ngày trong 30 ngày."
_REQUEST = "hãy lập hồ sơ biên bản xử lý vi phạm của người này cho tôi"
_STORED = {
    "contract_type": StoredFact("xác định thời hạn", True),
    "absence_days": StoredFact("5 ngày trong 30 ngày", True),
    "notice_form": StoredFact("không báo", True),
    "minutes_made": StoredFact("false", True),
    "explanation_requested": StoredFact("false", True),
}


def _decision(action=RequestedAction.NEED_CLARIFICATION, **kwargs):
    return ClarifyDecision(
        family=CaseFamily.UNAUTHORIZED_ABSENCE,
        family_confidence=0.99,
        confidence=0.99,
        user_intent=UserIntent.PROVIDE_FACTS,
        requested_action=action,
        **kwargs,
    )


@pytest.mark.parametrize(
    "action", [RequestedAction.DRAFT_MINUTES, RequestedAction.ANSWER_POLICY_QUESTION, RequestedAction.UNSUPPORTED]
)
def test_minutes_wording_cannot_override_the_model_action(action):
    plan = apply_decision(_REQUEST, {}, _decision(action))
    assert plan.requested_action == action.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stored,ready",
    [({}, False), (_STORED, True), ({**_STORED, "evidence_docs": StoredFact("Bảng chấm công", False)}, False)],
)
async def test_exact_screenshot_request_checks_facts_instead_of_refusing(monkeypatch, stored, ready):
    router = AsyncMock(
        return_value=IntentResult(
            IntentDecision(
                route=Route.WORKFLOW_ACTION,
                intent_label="prepare_case_record",
                requested_action="draft_minutes",
                requires_fact_planner=True,
                confidence=0.99,
            ),
            IntentFallback.NONE,
            None,
            1,
            "test",
        )
    )
    requirements = []
    if "evidence_docs" in stored:
        requirements = [
            {"key": "evidence_docs", "label": "Chứng cứ", "question": "Chứng cứ gồm những gì?", "required": True}
        ]
    planner = AsyncMock(
        return_value=PlannerResult(
            _decision(RequestedAction.UNSUPPORTED, fact_requirements=requirements), False, None, 1, "test"
        )
    )
    retriever = AsyncMock(side_effect=AssertionError("The turn service decides whether a stored answer can be reused"))
    monkeypatch.setattr("src.agents.case_graph.route_turn", router)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    result = await build_case_graph(retriever).ainvoke(
        {
            "semantic": True,
            "text": _TEXT,
            "latest_user_message": _REQUEST,
            "stored": stored,
            "locked_fact_keys": list(_STORED) if requirements else [],
            "incident_date": date(2026, 10, 14),
            "agent_run_id": uuid4(),
        }
    )
    assert result["requested_action"] == "draft_minutes"
    assert result["facts_locked"] is ready
    assert "thẩm quyền phê duyệt" not in result.get("question", "")
    if not ready:
        assert "ngay trong hội thoại" in result["question"]
        assert "Bổ sung thông tin" not in result["question"]
        assert "Nhấn" not in result["question"]
        for spec in result["specs"]:
            if spec.key in result["missing_keys"]:
                assert spec.question in result["question"]
    planner.assert_awaited_once()
    router.assert_awaited_once()
    retriever.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [_REQUEST, "Ghi lại sự việc này thành văn bản cho HR xem giúp tôi"])
async def test_minutes_command_never_bypasses_or_overrides_semantic_router(monkeypatch, text):
    router = AsyncMock(
        return_value=IntentResult(
            IntentDecision(route=Route.CLARIFY, intent_label="uncertain_goal", confidence=0.3),
            IntentFallback.NONE,
            None,
            1,
            "test",
        )
    )
    planner = AsyncMock(side_effect=AssertionError("A clarify route must remain clarify"))
    monkeypatch.setattr("src.agents.case_graph.route_turn", router)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    result = await build_case_graph(AsyncMock()).ainvoke(
        {"semantic": True, "text": _TEXT, "latest_user_message": text, "stored": {}}
    )
    assert result["selected_route"] == Route.CLARIFY
    router.assert_awaited_once()
    planner.assert_not_awaited()


@pytest.mark.parametrize(
    "action,edge", [("create_ticket_preview", "extract"), ("send_to_legal", "extract"), ("show_assessment", "action")]
)
def test_orchestrator_validates_preparation_actions_but_reads_saved_assessments_directly(action, edge):
    decision = IntentDecision(
        route=Route.WORKFLOW_ACTION,
        intent_label=action,
        requested_action=action,
        confidence=0.99,
        requires_fact_planner=False,
    )
    assert (
        route_after_intent(
            {"selected_route": Route.WORKFLOW_ACTION, "requested_action": action, "intent_decision": decision}
        )
        == edge
    )


@pytest.mark.parametrize("requires_planner", [True, False])
def test_preparing_minutes_cannot_bypass_validation_through_a_model_flag(requires_planner):
    decision = IntentDecision(
        route=Route.WORKFLOW_ACTION,
        intent_label="draft_minutes",
        requested_action="draft_minutes",
        confidence=0.99,
        requires_fact_planner=requires_planner,
    )
    assert (
        route_after_intent(
            {"selected_route": Route.WORKFLOW_ACTION, "requested_action": "draft_minutes", "intent_decision": decision}
        )
        == "extract"
    )


@pytest.mark.asyncio
async def test_draft_and_approval_together_still_use_the_unsupported_boundary(monkeypatch):
    router = AsyncMock(
        return_value=IntentResult(
            IntentDecision(route=Route.UNSUPPORTED, intent_label="approve", confidence=0.99),
            IntentFallback.NONE,
            None,
            1,
            "test",
        )
    )
    planner = AsyncMock(side_effect=AssertionError("Approval is separate"))
    monkeypatch.setattr("src.agents.case_graph.route_turn", router)
    monkeypatch.setattr("src.features.clarify.model.graph.plan_turn", planner)
    result = await build_case_graph(AsyncMock()).ainvoke(
        {
            "semantic": True,
            "text": _TEXT,
            "latest_user_message": "Lập biên bản rồi phê duyệt và đóng hồ sơ",
            "stored": _STORED,
        }
    )
    assert result["requested_action"] == "unsupported"
    planner.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("semantic", [True, False])
async def test_pending_draft_resumes_after_facts_are_provided_or_confirmed(monkeypatch, semantic):
    monkeypatch.setattr(
        "src.features.clarify.model.graph.plan_turn",
        AsyncMock(return_value=PlannerResult(_decision(RequestedAction.COMPLETE_FACTS), False, None, 1, "test")),
    )
    result = await extract_node(
        {
            "semantic": semantic,
            "text": _TEXT,
            "latest_user_message": "Đúng, xác nhận các tình tiết",
            "stored": _STORED,
            "pending_action": "draft_minutes",
        }
    )
    assert result["requested_action"] == "draft_minutes"
    assert result["facts_locked"] is True
    assert result["merged"]["minutes_made"].value == "false"


def _turn_setup(monkeypatch, *, locked=True):
    actor = SimpleNamespace(id=uuid4())
    case = SimpleNamespace(id=uuid4(), status="ANALYZED", incident_date=date(2026, 10, 14))
    conversation = SimpleNamespace(id=uuid4())
    run = AgentRun(id=uuid4(), status="RUNNING")
    session = AsyncMock()
    session.get.return_value = actor
    plan = replace(assess(_TEXT, _STORED if locked else {}), requested_action="draft_minutes")
    answer = AnswerView.model_construct(
        case_id=case.id,
        recommendation_id=uuid4(),
        case_status=case.status,
        sanction_type=None,
        internal_rule=[],
        legal_basis=[],
    )
    monkeypatch.setattr(turns, "_stored", AsyncMock(return_value=_STORED if locked else {}))
    monkeypatch.setattr(turns, "_planned", AsyncMock(return_value=(plan, None)))
    monkeypatch.setattr(turns, "load", AsyncMock(return_value=answer))
    monkeypatch.setattr(turns, "_reopen", AsyncMock())
    monkeypatch.setattr(turns, "add_message", AsyncMock(return_value=SimpleNamespace(id=uuid4())))
    monkeypatch.setattr(turns, "update_memory", AsyncMock())
    monkeypatch.setattr(
        turns, "ensure_assessment", AsyncMock(return_value=SimpleNamespace(assessment_id=uuid4(), status="DRAFT"))
    )
    return session, actor, case, conversation, run


@pytest.mark.asyncio
async def test_ready_chat_saves_form_before_saying_open_minutes(monkeypatch):
    session, actor, case, conversation, run = _turn_setup(monkeypatch)
    result = await turns._clarify(session, case, conversation, run, uuid4(), actor.id, _REQUEST)
    assert result.assessment_id is not None
    assert "Mở biên bản" in result.assistant_message
    assert run.status == "SUCCEEDED"
    turns.ensure_assessment.assert_awaited_once_with(session, actor, case.id)
    turns.update_memory.assert_awaited_once()
    assert turns.update_memory.call_args.kwargs["action_completed"] is True
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_incomplete_chat_asks_and_does_not_create_form(monkeypatch):
    session, actor, case, conversation, run = _turn_setup(monkeypatch, locked=False)
    result = await turns._clarify(session, case, conversation, run, uuid4(), actor.id, _REQUEST)
    assert not result.facts_locked
    assert result.assessment_id is None
    assert result.missing_fact_keys
    turns.ensure_assessment.assert_not_awaited()


@pytest.mark.asyncio
async def test_side_answer_does_not_reopen_case_or_start_a_workflow(monkeypatch):
    session, actor, case, conversation, run = _turn_setup(monkeypatch, locked=False)
    plan = replace(
        assess(_TEXT, {}), requested_action="", question="Thông tin đang lưu trong hồ sơ.", state_update="preserve"
    )
    turns._planned.return_value = (plan, None)
    result = await turns._clarify(session, case, conversation, run, uuid4(), actor.id, "Hồ sơ có gì?")
    assert result.assistant_message == plan.question
    turns._reopen.assert_not_awaited()
    turns.ensure_assessment.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_form_save_never_promises_success_or_commits(monkeypatch):
    session, actor, case, conversation, run = _turn_setup(monkeypatch)
    turns.ensure_assessment.side_effect = AppError(409, "Chưa có báo cáo đã lưu")
    with pytest.raises(AppError):
        await turns._clarify(session, case, conversation, run, uuid4(), actor.id, _REQUEST)
    turns.add_message.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_synthesis_saves_only_one_visible_final_reply(monkeypatch):
    session, actor, case, conversation, run = _turn_setup(monkeypatch)
    plan = turns._planned.return_value[0]
    handoff = CaseHandoff(
        incident_date=date(2026, 10, 14),
        family=plan.family,
        facts={key: item.value for key, item in plan.merged.items()},
        agent_run_id=uuid4(),
        missing_internal_rule=True,
    )
    turns._planned.return_value = (replace(plan, requested_action="complete_facts"), handoff)
    answer = turns.load.return_value.model_copy(
        update={"chat_message": "Tôi chưa thể đề xuất mức xử lý vì căn cứ còn thiếu."}
    )
    monkeypatch.setattr(
        turns,
        "run_downstream_agents",
        AsyncMock(
            return_value=SimpleNamespace(
                answer=answer, agent_run_id=uuid4(), assistant_text="BIÊN BẢN ĐÁNH GIÁ VỤ VIỆC"
            )
        ),
    )
    result = await turns._clarify(session, case, conversation, run, uuid4(), actor.id, "Các tình tiết đã đủ")
    assert "Mở biên bản" in result.assistant_message
    assert "BIÊN BẢN ĐÁNH GIÁ" not in result.assistant_message
    drafts = [call.args[1] for call in turns.add_message.await_args_list]
    visible = [draft for draft in drafts if not (draft.metadata or {}).get("internal")]
    assert len(visible) == 1 and visible[0].content == result.assistant_message
    turns.ensure_assessment.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,source,same_answer", [("CONFIRMED", "AI", False), ("DRAFT", "HR", False), ("DRAFT", "AI", True)]
)
async def test_repeated_request_preserves_existing_version_and_hr_edits(monkeypatch, status, source, same_answer):
    case, actor = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    answer = SimpleNamespace(recommendation_id=uuid4())
    report = SimpleNamespace(recommendation_id=answer.recommendation_id if same_answer else uuid4())
    version = SimpleNamespace(status=status, source=source)
    monkeypatch.setattr(service, "_editable", AsyncMock(return_value=case))
    monkeypatch.setattr(service, "get_report", AsyncMock(return_value=report))
    monkeypatch.setattr(service, "current_version", AsyncMock(return_value=version))
    monkeypatch.setattr(service, "load", AsyncMock(return_value=answer))
    monkeypatch.setattr(service, "_present", AsyncMock(return_value="existing"))
    monkeypatch.setattr(service, "generate_assessment", AsyncMock())
    assert await service.ensure_assessment(AsyncMock(), actor, case.id) == "existing"
    service.generate_assessment.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_chat_draft_uses_the_callers_transaction(monkeypatch):
    case, actor = SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())
    monkeypatch.setattr(service, "_editable", AsyncMock(return_value=case))
    monkeypatch.setattr(service, "get_report", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "generate_assessment", AsyncMock(return_value="saved"))
    session = AsyncMock()
    assert await service.ensure_assessment(session, actor, case.id) == "saved"
    service.generate_assessment.assert_awaited_once_with(session, actor, case.id, commit=False)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_keeps_pending_draft_through_questions_then_clears_on_success(monkeypatch):
    memory = SimpleNamespace(pending_action="draft_minutes")
    monkeypatch.setattr("src.features.clarify.model.memory.ensure_memory", AsyncMock(return_value=memory))
    monkeypatch.setattr("src.features.clarify.model.memory._recent_messages", AsyncMock(return_value=[]))
    plan = replace(assess(_TEXT, _STORED), requested_action="answer_policy_question")
    session, conversation_id = AsyncMock(), uuid4()
    await update_memory(session, conversation_id, plan, "Tra quy định")
    assert memory.pending_action == "draft_minutes"
    await update_memory(
        session, conversation_id, replace(plan, requested_action="draft_minutes"), "Mở biên bản", action_completed=True
    )
    assert memory.pending_action is None
