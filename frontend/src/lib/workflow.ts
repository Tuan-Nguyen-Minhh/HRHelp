import type { AgentEvent, AnswerView, TurnResponse } from "@/types/api";

export type StepId = "case" | "clarification" | "retrieval" | "assessment" | "legal_review" | "decision";
export type StepState = "completed" | "active" | "waiting" | "blocked";

export interface WorkflowStep {
  id: StepId;
  label: string;
  state: StepState;
}

const LABELS: Record<StepId, string> = {
  case: "Hồ sơ",
  clarification: "Làm rõ",
  retrieval: "Đối chiếu",
  assessment: "Đánh giá căn cứ",
  legal_review: "Pháp chế",
  decision: "Quyết định",
};

const ORDER: StepId[] = ["case", "clarification", "retrieval", "assessment", "legal_review", "decision"];

/** Statuses that still accept another chat turn. Mirrors the API guard. */
export const MUTABLE_CASE_STATUS = new Set(["OPEN", "NEED_INFO", "ANALYZED", "REJECTED"]);

const LEGAL_VISIBLE = new Set(["PENDING_LEGAL", "APPROVED", "REJECTED", "DECIDED", "CLOSED"]);

function blank(): WorkflowStep[] {
  return ORDER.map((id) => ({ id, label: LABELS[id], state: "waiting" }));
}

function mark(steps: WorkflowStep[], ids: StepId[], state: StepState): void {
  for (const step of steps) {
    if (ids.includes(step.id)) step.state = state;
  }
}

/**
 * Mirror the case status and the ticket disposition the API already stored.
 * This does not inspect facts or choose a sanction.
 */
export function workflowSteps(status: string, ticket: string | null): WorkflowStep[] {
  const steps = blank();
  switch (status) {
    case "OPEN":
      mark(steps, ["case"], "active");
      break;
    case "NEED_INFO":
      mark(steps, ["case"], "completed");
      mark(steps, ["clarification"], "active");
      break;
    case "RETRIEVING":
      mark(steps, ["case", "clarification"], "completed");
      mark(steps, ["retrieval"], "active");
      break;
    case "ANALYZING":
    case "ASSESSING":
      mark(steps, ["case", "clarification", "retrieval"], "completed");
      mark(steps, ["assessment"], "active");
      break;
    case "ANALYZED":
      mark(steps, ["case", "clarification", "retrieval", "assessment"], "completed");
      if (ticket === "PREVIEW") mark(steps, ["decision"], "active");
      break;
    case "PENDING_LEGAL":
      mark(steps, ["case", "clarification", "retrieval", "assessment"], "completed");
      mark(steps, ["legal_review"], "active");
      break;
    case "REJECTED":
      mark(steps, ["case", "clarification", "retrieval", "assessment"], "completed");
      mark(steps, ["legal_review"], "blocked");
      break;
    case "APPROVED":
      mark(steps, ["case", "clarification", "retrieval", "assessment", "legal_review"], "completed");
      mark(steps, ["decision"], "active");
      break;
    case "DECIDED":
    case "CLOSED":
      mark(steps, ["case", "clarification", "retrieval", "assessment", "legal_review", "decision"], "completed");
      break;
    default:
      mark(steps, ["case"], "active");
  }
  if (!LEGAL_VISIBLE.has(status)) {
    return steps.filter((step) => step.id !== "legal_review");
  }
  return steps;
}

export function agentAfterTurn(turn: TurnResponse): AgentEvent {
  const ticket = turn.answer?.ticket?.disposition ?? null;
  if (turn.case_status === "PENDING_LEGAL" || ticket === "SUBMIT") {
    return { type: "agent_status", agent: "legal_review", status: "completed" };
  }
  if (ticket === "PREVIEW") {
    return { type: "agent_status", agent: "decision", status: "completed" };
  }
  if (turn.handoff && turn.answer) {
    return { type: "agent_status", agent: "evidence_synthesis", status: "completed" };
  }
  if (turn.facts_locked) {
    return { type: "agent_status", agent: "retrieval", status: "completed" };
  }
  return { type: "agent_status", agent: "clarification", status: "completed" };
}

/** Show a stored company level only when law or an internal rule was attached. */
export function visibleSanction(answer: AnswerView | null | undefined): string | null {
  if (!answer?.sanction_type || answer.sanction_type === "TERMINATION") return null;
  if (answer.legal_basis.length + answer.internal_rule.length === 0) return null;
  return answer.sanction_type;
}

export type AssessmentView = "collecting" | "supported" | "held" | "review" | "open" | "withheld";

const REVIEW_STATUS = new Set(["PENDING_LEGAL", "APPROVED", "REJECTED", "DECIDED", "CLOSED"]);

/**
 * Pick which assessment card to draw from the stored case status and ticket.
 * This does not rank sanctions or fill a level the answer left empty.
 */
export function assessmentView(status: string, answer: AnswerView | null, missingFacts: number): AssessmentView {
  const ticket = answer?.ticket?.disposition ?? null;
  if (REVIEW_STATUS.has(status) || ticket === "SUBMIT") return "review";
  if (missingFacts > 0 || status === "OPEN" || status === "NEED_INFO" || !answer) return "collecting";
  if (answer.sanction_type === "TERMINATION" || (answer.sanction_type != null && visibleSanction(answer) == null)) {
    return "withheld";
  }
  if (ticket === "HOLD") return "held";
  if (visibleSanction(answer)) return "supported";
  return "open";
}
