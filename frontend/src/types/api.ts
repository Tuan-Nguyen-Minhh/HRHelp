import type { AssessmentForm } from "@/types/assessment";

export type CaseStatus =
  | "OPEN"
  | "NEED_INFO"
  | "ANALYZING"
  | "RETRIEVING"
  | "ASSESSING"
  | "ANALYZED"
  | "PENDING_LEGAL"
  | "APPROVED"
  | "REJECTED"
  | "DECIDED"
  | "CLOSED";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  roles: string[];
}

export interface RegisterBody {
  email: string;
  password: string;
  full_name?: string;
  role: "HR" | "MANAGER" | "LEGAL";
}

export interface OpenCaseBody {
  case_code: string;
  employee_code: string;
  employee_name: string;
  description: string;
  incident_date: string;
  family?: "UNAUTHORIZED_ABSENCE" | "LATE" | "GENERAL";
}

export interface StaffAccount {
  user_id: string;
  email: string;
  full_name: string | null;
  role: "HR" | "LEGAL" | string;
  is_active: boolean;
}

export interface StaffWrite {
  email?: string;
  password?: string;
  full_name?: string | null;
  role?: "HR" | "LEGAL";
  is_active?: boolean;
}

export interface IngestionDocument {
  document_id: string;
  file_name: string;
  ingest_status: string;
  policy_code: string | null;
  policy_name: string | null;
  chunk_count: number;
  embedded_chunk_count: number;
  error: string | null;
  created_at: string;
}

export interface IngestionDocumentList {
  documents: IngestionDocument[];
}

export interface MeResponse {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  roles: string[];
  permissions: string[];
}

export interface CaseListResponse {
  cases: CaseView[];
}

export interface OpenCaseResponse {
  case_id: string;
  conversation_id: string;
  status: string;
}

export interface CaseView {
  case_id: string;
  conversation_id: string | null;
  case_code: string;
  employee_code: string | null;
  employee_name: string | null;
  description: string | null;
  incident_date: string | null;
  status: string;
  family?: string | null;
}

export interface FactView {
  fact_key: string;
  label: string;
  fact_value: string | null;
  confirmed: boolean;
  confidence?: number | null;
}

export interface FactListResponse {
  case_id: string;
  case_status: string;
  family: string;
  facts: FactView[];
  missing_fact_keys: string[];
  facts_locked: boolean;
}

export interface ProcessStep {
  code: string;
  label: string;
  done: boolean;
}

export interface CitationView {
  citation_id: string;
  chunk_id: string | null;
  layer: string;
  policy_type: string | null;
  policy_code: string | null;
  policy_name: string | null;
  quote: string;
  article: string | null;
  clause: string | null;
  point: string | null;
  score: number | null;
}

export interface LayerEffect {
  layer: string;
  effect: string;
  note: string;
}

export interface AppliedStandard {
  sanction_type: string | null;
  process_steps: ProcessStep[];
  risk_level: string | null;
  aligned: boolean;
  rule: string;
  layers: LayerEffect[];
}

export interface DraftView {
  draft_id: string;
  draft_type: string;
  title: string;
  content: string;
  status: string;
}

export interface TicketRequest {
  disposition: string;
  hold_code: string | null;
  reason: string;
  queue: string;
}

export interface AnswerView {
  recommendation_id: string;
  case_id: string;
  case_status: string;
  agent_run_id: string | null;
  rationale: string | null;
  sanction_type: string | null;
  process_steps: ProcessStep[];
  risk_level: string | null;
  missing_internal_rule: boolean;
  message: string;
  legal_basis: CitationView[];
  internal_rule: CitationView[];
  precedent: CitationView[];
  inspection_risk: CitationView[];
  standard: AppliedStandard;
  drafts: DraftView[];
  ticket: TicketRequest | null;
}

export interface CitedPassage {
  chunk_id: string;
  policy_version_id: string;
  content: string;
  article: string | null;
  clause: string | null;
  point: string | null;
  score: number;
  policy_type: string | null;
  policy_code: string;
  policy_name: string;
  origin: string;
}

export interface CaseHandoff {
  case_id: string | null;
  incident_date: string;
  employee_name: string | null;
  description: string;
  family: string;
  facts: Record<string, string>;
  fact_lines: string[];
  passages: CitedPassage[];
  missing_internal_rule: boolean;
  agent_run_id: string;
  query: string;
  retrieval: string;
}

export interface MessageView {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

export interface MessageListResponse {
  case_id: string;
  conversation_id: string | null;
  messages: MessageView[];
}

export interface TimelineEvent {
  at: string;
  kind: string;
  label: string;
  entity_type: string | null;
  entity_id: string | null;
}

export interface TimelineResponse {
  case_id: string;
  events: TimelineEvent[];
}

export interface NotificationView {
  id: string;
  case_id: string | null;
  event: string;
  title: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface NotificationList {
  notifications: NotificationView[];
}

export interface DashboardSummary {
  cases_by_status: Record<string, number>;
  cases_by_family: Record<string, number>;
  recommendation_rejection_rate: number | null;
  legal_approval_rate: number | null;
  legal_rejection_rate: number | null;
  agent_failure_rate: number | null;
  retrieval_empty_rate: number | null;
}

export interface QueueItem {
  case_id: string;
  case_code: string;
  employee_code: string | null;
  employee_name: string | null;
  incident_date: string | null;
  status: string;
  updated_at: string;
}

export interface ReviewPack {
  case_id: string;
  case_code: string;
  status: string;
  employee_code: string | null;
  employee_name: string | null;
  incident_date: string | null;
  description: string | null;
  answer: AnswerView;
  assessment: AssessmentForm | null;
}

export interface ReviewView {
  review_id: string;
  case_id: string;
  decision: string;
  comment: string | null;
  case_status: string;
}

export interface DecisionPreview {
  case_id: string;
  case_status: string;
  draft_id: string;
  recommendation_id: string;
  sanction_type: string;
  decision_draft: string;
  summary_hint: string | null;
}

export interface ReturnReason {
  reviewer_role: "LEGAL" | "MANAGER";
  reviewer_name: string | null;
  comment: string | null;
  returned_at: string;
}

export interface DecisionView {
  decision_id: string;
  case_id: string;
  decision_code: string;
  sanction_type: string;
  summary: string;
  legal_basis: string | null;
  issued_by: string;
  issued_at: string;
  case_status: string;
  is_precedent: boolean;
}

export interface RecidivismView {
  case_id: string;
  prior_sanction_count: number;
  prior_cases: { case_id: string; case_code: string; status: string }[];
  prior_decisions: { decision_code: string; sanction_type: string; issued_at: string }[];
  possible_recurrence: boolean;
  confirmed: boolean;
}

export interface ExportPayload {
  format: string;
  kind: string;
  content:
    | string
    | {
        path?: string;
        file_name?: string;
        content_type?: string;
        preview?: string;
      }
    | Record<string, unknown>;
}

export interface TurnResponse {
  case_id: string;
  case_status: string;
  conversation_id: string;
  family: string;
  assistant_message: string;
  facts: FactView[];
  missing_fact_keys: string[];
  facts_locked: boolean;
  answer: AnswerView | null;
  handoff: CaseHandoff | null;
  agent_run_id: string | null;
  requested_action?: string | null;
  user_intent?: string | null;
  reply_kind?: string | null;
  state_update?: "preserve" | "progress";
}

export type AgentName = "clarification" | "retrieval" | "evidence_synthesis" | "decision" | "legal_review";

export type AgentRunStatus = "running" | "completed" | "failed";

export interface AgentEvent {
  type: "agent_status";
  agent: AgentName;
  status: AgentRunStatus;
}

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  at: string;
}

export type EvidenceKind = "LAW" | "DECREE" | "INTERNAL_RULE" | "PRECEDENT" | "ADMINISTRATIVE_PENALTY" | "OTHER";

export interface EvidenceItem {
  id: string;
  chunkId: string | null;
  kind: EvidenceKind;
  policyType: string | null;
  policyCode: string | null;
  policyName: string | null;
  article: string | null;
  clause: string | null;
  point: string | null;
  content: string;
  retrievedBecause: string | null;
  caseCode: string | null;
}
