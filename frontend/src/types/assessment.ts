export type FormStatus = "AI_DRAFT" | "HR_EDITING" | "READY_FOR_CONFIRM" | "CONFIRMED" | "SUPERSEDED";
export type ReportStatus = "DRAFT" | "CONFIRMED" | "SUPERSEDED";
export type FactStatus = "CONFIRMED" | "MISSING" | "UNCERTAIN" | "HR_EDITED";
export type FieldSource = "AI" | "HR" | "CONFIRMED";
export type ResultStatus =
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "INSUFFICIENT_EVIDENCE"
  | "CONFLICTING_EVIDENCE"
  | "NEED_LEGAL_REVIEW";

export interface CaseInformation {
  case_code: string;
  incident_date: string | null;
  violation_type: string | null;
  description: string;
  case_status: string;
}

export interface EmployeeInformation {
  employee_code: string | null;
  employee_name: string | null;
  department: string | null;
  position: string | null;
  contract_type: string | null;
  employment_status: string | null;
}

export interface IncidentSummary {
  narrative: string;
  timeline: string;
  employee_statement: string;
  hr_description: string;
}

export interface ConfirmedFact {
  fact_key: string;
  label: string;
  value: string | null;
  status: FactStatus;
  blocking: boolean;
  source: FieldSource;
}

export interface EvidenceCard {
  evidence_id: string;
  document_id: string | null;
  chunk_id: string | null;
  policy_type: string | null;
  title: string;
  citation_label: string;
  quote: string;
  article: string | null;
  clause: string | null;
  point: string | null;
  layer: string;
}

export interface AssessmentSection {
  narrative: string;
  applied_basis: string[];
  matches: string[];
  gaps: string[];
  conflicts: string[];
}

export interface AssessmentResult {
  status: ResultStatus;
  summary: string;
}

export interface ProposedAction {
  code: string;
  label: string;
}

export interface HandlingProposal {
  proposed_actions: ProposedAction[];
  alternatives: ProposedAction[];
  confidence: string;
  requires_legal_review: boolean;
  rationale: string;
  manual_text?: string | null;
}

export interface MissingItem {
  fact_key: string;
  reason: string;
  blocking: boolean;
}

export interface RiskAndGaps {
  risk_level: string | null;
  evidence_gaps: string[];
  conflicts: string[];
  missing_information: MissingItem[];
  legal_review_required: boolean;
}

export interface NextStep {
  order: number;
  text: string;
}

export interface AssessmentSections {
  case_information: CaseInformation;
  employee_information: EmployeeInformation;
  incident_summary: IncidentSummary;
  confirmed_facts: ConfirmedFact[];
  evidence_reviewed: EvidenceCard[];
  assessment: AssessmentSection;
  assessment_result: AssessmentResult;
  handling_proposal: HandlingProposal;
  risk_and_gaps: RiskAndGaps;
  next_steps: NextStep[];
  citations: EvidenceCard[];
}

export interface AssessmentValidation {
  is_valid: boolean;
  blocking_errors: string[];
  warnings: string[];
}

export interface AssessmentPermissions {
  can_edit: boolean;
  can_confirm: boolean;
  can_reanalyze: boolean;
  can_create_ticket: boolean;
}

export interface AssessmentForm {
  assessment_id: string;
  case_id: string;
  version: number;
  status: ReportStatus;
  form_status: FormStatus;
  sections: AssessmentSections;
  validation: AssessmentValidation;
  permissions: AssessmentPermissions;
  metadata: {
    generated_at: string | null;
    case_created_date?: string | null;
    minutes_profile: {
      company_name: string;
      city: string;
      document_number: string;
      meeting_location: string;
      leadership_name: string;
      leadership_position: string;
      hr_name: string;
      hr_position: string;
      hr_department: string;
    };
    source: "AI" | "HR";
    recommendation_id: string | null;
    prompt_version: string;
  };
  sources: Record<string, FieldSource>;
}

export interface AssessmentPatch {
  case_information?: CaseInformation;
  employee_information?: EmployeeInformation;
  incident_summary?: IncidentSummary;
  confirmed_facts?: ConfirmedFact[];
  handling_rationale?: string;
}
