export const CASE_STATUSES = ["OPEN", "NEED_INFO", "ANALYZED", "PENDING_LEGAL", "APPROVED", "REJECTED", "DECIDED", "CLOSED"];

export const STATUS_LABEL: Record<string, string> = {
  OPEN: "Mới mở",
  NEED_INFO: "Cần bổ sung",
  ANALYZING: "Đang phân tích",
  RETRIEVING: "Đang đối chiếu",
  ASSESSING: "Đang đánh giá",
  ANALYZED: "Đã phân tích",
  PENDING_LEGAL: "Chờ pháp chế",
  APPROVED: "Đã duyệt",
  REJECTED: "Đã trả lại",
  DECIDED: "Đã ban hành",
  CLOSED: "Đã đóng",
};

export type StatusTone = "info" | "success" | "warning" | "danger" | "neutral";

export function statusTone(status: string): StatusTone {
  if (status === "ANALYZED" || status === "APPROVED" || status === "DECIDED" || status === "CLOSED") return "success";
  if (status === "NEED_INFO" || status === "REJECTED") return "warning";
  if (status === "PENDING_LEGAL") return "danger";
  if (status === "OPEN" || status === "ANALYZING" || status === "RETRIEVING" || status === "ASSESSING") return "info";
  return "neutral";
}

export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status;
}

export const SANCTION_LABEL: Record<string, string> = {
  WARNING: "Khiển trách",
  REPRIMAND: "Cảnh cáo",
  WAGE_POSTPONEMENT: "Kéo dài thời hạn nâng lương",
  DEMOTION: "Cách chức",
  DISMISSAL: "Sa thải",
};

export function sanctionLabel(code: string | null | undefined): string {
  if (!code) return "Chưa chốt mức";
  if (code === "TERMINATION") return "Không dùng làm mức kỷ luật";
  return SANCTION_LABEL[code] ?? code;
}

export const RISK_LABEL: Record<string, string> = {
  LOW: "Thấp",
  MEDIUM: "Trung bình",
  HIGH: "Cao",
  CRITICAL: "Rất cao",
};

export function riskTone(level: string | null | undefined): StatusTone {
  if (level === "LOW") return "success";
  if (level === "MEDIUM") return "warning";
  if (level === "HIGH" || level === "CRITICAL") return "danger";
  return "neutral";
}

export function riskLabel(level: string | null | undefined): string {
  if (!level) return "Chưa có";
  return RISK_LABEL[level] ?? level;
}

export const FAMILY_LABEL: Record<string, string> = {
  UNSPECIFIED: "Chưa phân loại",
  UNAUTHORIZED_ABSENCE: "Nghỉ không phép",
  LATE: "Đi muộn",
  GENERAL: "Vi phạm khác",
};

export function familyLabel(family: string | null | undefined): string {
  if (!family) return "Chưa phân loại";
  return FAMILY_LABEL[family] ?? family;
}

export const ROLE_LABEL: Record<string, string> = {
  HR: "Nhân sự",
  MANAGER: "Quản lý",
  LEGAL: "Pháp chế",
  SIGNER: "Người ký",
  ADMIN: "Quản trị",
};

export const AGENT_LABEL: Record<string, string> = {
  clarification: "Làm rõ tình tiết",
  retrieval: "Đối chiếu văn bản",
  evidence_synthesis: "Đánh giá căn cứ",
  decision: "Phiếu xử lý",
  legal_review: "Pháp chế",
};

export const AGENT_STATUS_LABEL: Record<string, string> = {
  running: "đang xử lý",
  completed: "đã xong",
  failed: "không hoàn tất",
};

export const TICKET_LABEL: Record<string, string> = {
  PREVIEW: "Sẵn sàng đẩy phiếu",
  HOLD: "Đang giữ, chưa đẩy",
  SUBMIT: "Đã đẩy phiếu",
  NOT_SENT: "Chưa tạo phiếu",
};

export const HOLD_LABEL: Record<string, string> = {
  TERMINATION: "Mức không phải kỷ luật",
  OPEN_SANCTION: "Chưa chốt mức",
  RISK_HIGH: "Rủi ro căn cứ cao",
  MISSING_INTERNAL_RULE: "Thiếu nội quy",
  PROCEDURE_OPEN: "Thủ tục còn mở",
};

export const DRAFT_LABEL: Record<string, string> = {
  MINUTES: "Biên bản",
  EXPLANATION_REQUEST: "Yêu cầu giải trình",
  DECISION: "Dự thảo quyết định",
  TICKET: "Phiếu chuyển pháp chế",
};

export const DRAFT_STATUS_LABEL: Record<string, string> = {
  DRAFT: "Bản nháp",
  PREVIEW: "Xem trước",
  PENDING_REVIEW: "Chờ pháp chế xem",
  APPROVED: "Đã ghi nhận",
  REJECTED: "Đã trả lại",
  ISSUED: "Đã ban hành",
};

export const RETRIEVAL_LABEL: Record<string, string> = {
  hybrid: "Đã đối chiếu các nguồn còn hiệu lực",
  page_index: "Chỉ lấy được mục lục điều khoản",
  empty: "Không có đoạn còn hiệu lực",
};

export const EVIDENCE_KIND_LABEL: Record<string, string> = {
  LAW: "Luật",
  DECREE: "Nghị định hướng dẫn",
  INTERNAL_RULE: "Nội quy",
  PRECEDENT: "Tiền lệ",
  ADMINISTRATIVE_PENALTY: "Xử phạt hành chính",
  OTHER: "Nguồn khác",
};

export const QUEUE_LABEL: Record<string, string> = {
  READY: "Sẵn sàng",
  HELD: "Đang giữ",
  PENDING_LEGAL: "Hàng chờ pháp chế",
  NOT_SENT: "Chưa gửi",
};
