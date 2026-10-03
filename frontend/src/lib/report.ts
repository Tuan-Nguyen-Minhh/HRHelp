export interface DownstreamHandoffView {
  assessment_status?: string;
  recommended_sanction?: string | null;
  risk_level?: string | null;
  legal_basis_found?: boolean;
  internal_rule_found?: boolean;
  procedure_status?: string | null;
  needs_more_facts?: boolean;
  missing_facts?: string[];
  hr_decision_required?: boolean;
  can_create_legal_ticket?: boolean;
  next_allowed_actions?: string[];
}

const STATUS_LABEL: Record<string, string> = {
  SUPPORTED: "Đủ căn cứ",
  NOT_SUPPORTED: "Chưa đủ căn cứ",
  NEED_MORE_FACTS: "Cần bổ sung tình tiết",
  NEED_LEGAL_REVIEW: "Cần pháp chế xem xét",
  MULTIPLE_SUPPORTED: "Có nhiều hướng có căn cứ",
  CONFLICTED: "Có mâu thuẫn căn cứ",
};

const ACTION_LABEL: Record<string, string> = {
  CONTINUE: "Tiếp tục xử lý",
  REQUEST_MORE_INFORMATION: "Yêu cầu bổ sung thông tin",
  SEND_TO_LEGAL: "Gửi pháp chế",
  REJECT_ASSESSMENT: "Không sử dụng đánh giá",
};

export function parseDownstreamHandoff(text: string | null | undefined): DownstreamHandoffView | null {
  if (!text) return null;
  const marker = "HANDOFF:";
  const start = text.indexOf(marker);
  if (start < 0) return null;
  const raw = extractJsonObject(text.slice(start + marker.length).trim());
  if (!raw.startsWith("{")) return null;
  try {
    const parsed = JSON.parse(raw) as { downstream_handoff?: DownstreamHandoffView };
    return parsed.downstream_handoff ?? null;
  } catch {
    return null;
  }
}

export function isRawHandoffMessage(text: string | null | undefined): boolean {
  return parseDownstreamHandoff(text) !== null;
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return "Chưa xác định";
  return STATUS_LABEL[status] ?? status;
}

export function handoffSummary(handoff: DownstreamHandoffView): string {
  const missing = handoff.missing_facts?.filter(Boolean) ?? [];
  const actions = handoff.next_allowed_actions?.map((item) => ACTION_LABEL[item] ?? item).join(", ");
  const lines = [
    `Trạng thái đánh giá: ${statusLabel(handoff.assessment_status)}`,
    `Rủi ro: ${handoff.risk_level ?? "Chưa xác định"}`,
    `Mức đề xuất: ${handoff.recommended_sanction ?? "Chưa khóa mức xử lý"}`,
    `Căn cứ pháp luật: ${handoff.legal_basis_found ? "đã tìm thấy" : "chưa có"}`,
    `Nội quy: ${handoff.internal_rule_found ? "đã tìm thấy" : "chưa có"}`,
    `Quy trình: ${handoff.procedure_status ?? "Chưa xác định"}`,
  ];
  if (missing.length) lines.push(`Cần bổ sung: ${missing.join("; ")}`);
  if (actions) lines.push(`Bước tiếp theo: ${actions}`);
  return lines.join("\n");
}

export function readableAssistantText(text: string): string {
  const handoff = parseDownstreamHandoff(text);
  if (!handoff) return text;
  return `Đã lập bản đánh giá nháp.\n${handoffSummary(handoff)}`;
}

export function visibleReportText(text: string | null | undefined): string | null {
  if (!text || isRawHandoffMessage(text)) return null;
  return text;
}

function extractJsonObject(raw: string): string {
  const first = raw.indexOf("{");
  const last = raw.lastIndexOf("}");
  if (first < 0 || last < first) return raw;
  return raw.slice(first, last + 1);
}
