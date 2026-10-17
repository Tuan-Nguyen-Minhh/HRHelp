import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { clearAuth, readAuth, writeAuth } from "@/lib/session";
import type {
  AnswerView,
  CaseListResponse,
  CaseView,
  DashboardSummary,
  DecisionPreview,
  DecisionView,
  ExportPayload,
  FactListResponse,
  IngestionDocument,
  IngestionDocumentList,
  MeResponse,
  MessageListResponse,
  NotificationList,
  NotificationView,
  OpenCaseBody,
  OpenCaseResponse,
  QueueItem,
  RecidivismView,
  RegisterBody,
  ReviewPack,
  ReviewView,
  ReturnReason,
  StaffAccount,
  StaffWrite,
  StandaloneConversation,
  StandaloneMessagesResponse,
  StandaloneTurnResponse,
  TimelineResponse,
  TokenResponse,
  TurnResponse,
} from "@/types/api";
import type { AssessmentForm, AssessmentPatch } from "@/types/assessment";

const root = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? "" : "http://localhost:8000");

export const http = axios.create({ baseURL: `${root}/api/v1` });

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let refreshing: Promise<string | null> | null = null;
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

http.interceptors.request.use((config) => {
  const auth = readAuth();
  if (auth?.access_token) config.headers.Authorization = `Bearer ${auth.access_token}`;
  return config;
});

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    const url = original?.url ?? "";
    if (error.response?.status === 401 && original && !original._retry && !url.includes("/auth/")) {
      original._retry = true;
      const token = await refreshAccess();
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return http(original);
      }
    }
    return Promise.reject(error);
  },
);

async function refreshAccess(): Promise<string | null> {
  const auth = readAuth();
  if (!auth?.refresh_token) {
    clearAuth();
    onUnauthorized();
    return null;
  }
  if (!refreshing) {
    refreshing = axios
      .post<TokenResponse>(`${root}/api/v1/auth/refresh`, { refresh_token: auth.refresh_token })
      .then((response) => {
        writeAuth(response.data);
        return response.data.access_token;
      })
      .catch(() => {
        clearAuth();
        onUnauthorized();
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Không thể kết nối API. Hãy kiểm tra backend ở cổng 8000.";
    const data = error.response.data as { detail?: unknown; error?: { message?: string } } | undefined;
    if (typeof data?.error?.message === "string" && data.error.message.trim()) return data.error.message;
    const detail = data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const text = detail
        .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
        .filter(Boolean)
        .join(" · ");
      if (text) return text;
    }
    return `Yêu cầu không thành công (${error.response.status}).`;
  }
  if (error instanceof Error && error.message) return error.message;
  return "Không thể kết nối đến máy chủ. Vui lòng thử lại.";
}

function isNotFound(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

export const api = {
  async listConversations(): Promise<{ conversations: StandaloneConversation[] }> {
    const response = await http.get<{ conversations: StandaloneConversation[] }>("/conversations");
    return response.data;
  },
  async standaloneMessages(conversationId: string): Promise<StandaloneMessagesResponse> {
    const response = await http.get<StandaloneMessagesResponse>(`/conversations/${conversationId}/messages`);
    return response.data;
  },
  async sendStandaloneMessage(content: string, conversationId?: string): Promise<StandaloneTurnResponse> {
    const response = await http.post<StandaloneTurnResponse>("/conversations/messages", {
      content, conversation_id: conversationId,
    });
    return response.data;
  },
  async login(email: string, password: string): Promise<TokenResponse> {
    const body = new URLSearchParams({ username: email, password });
    const response = await http.post<TokenResponse>("/auth/login", body);
    return response.data;
  },
  async register(body: RegisterBody): Promise<TokenResponse> {
    const response = await http.post<TokenResponse>("/auth/register", body);
    return response.data;
  },
  async createCase(body: OpenCaseBody): Promise<OpenCaseResponse> {
    const response = await http.post<OpenCaseResponse>("/cases", body);
    return response.data;
  },
  async getCase(caseId: string): Promise<CaseView> {
    const response = await http.get<CaseView>(`/cases/${caseId}`);
    return response.data;
  },
  async getFacts(caseId: string): Promise<FactListResponse> {
    const response = await http.get<FactListResponse>(`/cases/${caseId}/facts`);
    return response.data;
  },
  async getAssessment(caseId: string): Promise<AssessmentForm | null> {
    try {
      const response = await http.get<AssessmentForm>(`/cases/${caseId}/assessment`);
      return response.data;
    } catch (error) {
      if (isNotFound(error)) return null;
      throw error;
    }
  },
  async generateAssessment(caseId: string): Promise<AssessmentForm> {
    const response = await http.post<AssessmentForm>(`/cases/${caseId}/assessment/generate`);
    return response.data;
  },
  async saveAssessment(caseId: string, body: AssessmentPatch): Promise<AssessmentForm> {
    const response = await http.post<AssessmentForm>(`/cases/${caseId}/assessment/save`, body);
    return response.data;
  },
  async confirmAssessment(caseId: string): Promise<AssessmentForm> {
    const response = await http.post<AssessmentForm>(`/cases/${caseId}/assessment/confirm`);
    return response.data;
  },
  async reanalyzeAssessment(caseId: string): Promise<AssessmentForm> {
    const response = await http.post<AssessmentForm>(`/cases/${caseId}/assessment/reanalyze`);
    return response.data;
  },
  async getAnswer(caseId: string): Promise<AnswerView | null> {
    try {
      const response = await http.get<AnswerView>(`/cases/${caseId}/answer`);
      return response.data;
    } catch (error) {
      if (isNotFound(error)) return null;
      throw error;
    }
  },
  async postMessage(caseId: string, content: string): Promise<TurnResponse> {
    const response = await http.post<TurnResponse>(`/cases/${caseId}/messages`, { content });
    return response.data;
  },
  async legalOfficers(): Promise<{ users: { email: string; full_name: string | null }[] }> {
    const response = await http.get<{ users: { email: string; full_name: string | null }[] }>("/legal-officers");
    return response.data;
  },
  async sendTicket(caseId: string, legalCode: string, idempotencyKey: string): Promise<AnswerView> {
    const response = await http.post<AnswerView>(
      `/cases/${caseId}/ticket`,
      { legal_code: legalCode },
      { headers: { "Idempotency-Key": idempotencyKey } },
    );
    return response.data;
  },
  async escalate(caseId: string, idempotencyKey: string): Promise<AnswerView> {
    const response = await http.post<AnswerView>(`/cases/${caseId}/escalate`, {}, { headers: { "Idempotency-Key": idempotencyKey } });
    return response.data;
  },
  async latestReview(caseId: string): Promise<ReviewView | null> {
    try {
      const response = await http.get<ReviewView>(`/cases/${caseId}/reviews/latest`);
      return response.data;
    } catch (error) {
      if (isNotFound(error)) return null;
      throw error;
    }
  },
  async managerQueue(): Promise<{ cases: QueueItem[] }> {
    const response = await http.get<{ cases: QueueItem[] }>("/manager/queue");
    return response.data;
  },
  async latestReturnReason(caseId: string): Promise<ReturnReason | null> {
    const response = await http.get<ReturnReason | null>(`/cases/${caseId}/returns/latest`);
    return response.data;
  },
  async managerReviewPack(caseId: string): Promise<ReviewPack> {
    const response = await http.get<ReviewPack>(`/manager/cases/${caseId}/review-pack`);
    return response.data;
  },
  async rejectDecision(caseId: string, comment: string, idempotencyKey: string): Promise<{ case_id: string; status: string }> {
    const response = await http.post<{ case_id: string; status: string }>(
      `/manager/cases/${caseId}/reject`, { comment }, { headers: { "Idempotency-Key": idempotencyKey } },
    );
    return response.data;
  },
  async staffAccounts(): Promise<{ users: StaffAccount[] }> {
    const response = await http.get<{ users: StaffAccount[] }>("/manager/users");
    return response.data;
  },
  async createStaff(body: StaffWrite): Promise<StaffAccount> {
    const response = await http.post<StaffAccount>("/manager/users", body);
    return response.data;
  },
  async updateStaff(userId: string, body: StaffWrite): Promise<StaffAccount> {
    const response = await http.patch<StaffAccount>(`/manager/users/${userId}`, body);
    return response.data;
  },
  async deleteStaff(userId: string): Promise<StaffAccount> {
    const response = await http.delete<StaffAccount>(`/manager/users/${userId}`);
    return response.data;
  },
  async me(): Promise<MeResponse> {
    const response = await http.get<MeResponse>("/auth/me");
    return response.data;
  },
  async logout(refreshToken: string): Promise<void> {
    await http.post("/auth/logout", { refresh_token: refreshToken });
  },
  async listCases(): Promise<CaseListResponse> {
    const response = await http.get<CaseListResponse>("/cases");
    return response.data;
  },
  async listMessages(caseId: string): Promise<MessageListResponse> {
    const response = await http.get<MessageListResponse>(`/cases/${caseId}/messages`);
    return response.data;
  },
  async confirmFacts(
    caseId: string,
    facts: { fact_key: string; fact_value: string | null; confirmed: boolean }[],
  ): Promise<TurnResponse> {
    const response = await http.post<TurnResponse>(`/cases/${caseId}/facts/confirm`, { facts });
    return response.data;
  },
  async timeline(caseId: string): Promise<TimelineResponse> {
    const response = await http.get<TimelineResponse>(`/cases/${caseId}/timeline`);
    return response.data;
  },
  async notifications(): Promise<NotificationList> {
    const response = await http.get<NotificationList>("/notifications");
    return response.data;
  },
  async readNotification(id: string): Promise<NotificationView> {
    const response = await http.post<NotificationView>(`/notifications/${id}/read`);
    return response.data;
  },
  async dashboardSummary(): Promise<DashboardSummary> {
    const response = await http.get<DashboardSummary>("/dashboard/summary");
    return response.data;
  },
  async legalQueue(): Promise<{ reviews: QueueItem[] }> {
    const response = await http.get<{ reviews: QueueItem[] }>("/legal/reviews/queue");
    return response.data;
  },
  async reviewPack(caseId: string): Promise<ReviewPack> {
    const response = await http.get<ReviewPack>(`/cases/${caseId}/review-pack`);
    return response.data;
  },
  async submitReview(caseId: string, decision: "APPROVE" | "REJECT", comment: string, idempotencyKey: string): Promise<ReviewView> {
    const response = await http.post<ReviewView>(
      `/cases/${caseId}/reviews`,
      { decision, comment: comment || null },
      { headers: { "Idempotency-Key": idempotencyKey } },
    );
    return response.data;
  },
  async reopen(caseId: string, target: "NEED_INFO" | "ANALYZED" | null, idempotencyKey: string): Promise<{ case_id: string; status: string }> {
    const response = await http.post<{ case_id: string; status: string }>(
      `/cases/${caseId}/reopen`,
      target ? { target } : {},
      { headers: { "Idempotency-Key": idempotencyKey } },
    );
    return response.data;
  },
  async decisionPreview(caseId: string): Promise<DecisionPreview> {
    const response = await http.get<DecisionPreview>(`/cases/${caseId}/decision-preview`);
    return response.data;
  },
  async issueDecision(
    caseId: string,
    body: { decision_code: string; summary: string; legal_basis?: string | null },
    idempotencyKey: string,
  ): Promise<DecisionView> {
    const response = await http.post<DecisionView>(`/cases/${caseId}/decisions`, body, {
      headers: { "Idempotency-Key": idempotencyKey },
    });
    return response.data;
  },
  async markPrecedent(caseId: string, precedentSummary: string, idempotencyKey: string): Promise<DecisionView> {
    const response = await http.post<DecisionView>(
      `/cases/${caseId}/decisions/precedent`,
      { precedent_summary: precedentSummary },
      { headers: { "Idempotency-Key": idempotencyKey } },
    );
    return response.data;
  },
  async closeCase(caseId: string, idempotencyKey: string): Promise<{ case_id: string; status: string }> {
    const response = await http.post<{ case_id: string; status: string }>(
      `/cases/${caseId}/close`,
      {},
      { headers: { "Idempotency-Key": idempotencyKey } },
    );
    return response.data;
  },
  async recidivism(caseId: string): Promise<RecidivismView> {
    const response = await http.post<RecidivismView>(`/cases/${caseId}/recidivism`);
    return response.data;
  },
  async exportCase(caseId: string, kind: "assessment" | "ticket" | "decision", format: "markdown" | "docx" = "markdown"): Promise<ExportPayload> {
    const response = await http.get<ExportPayload>(`/cases/${caseId}/export/${kind}`, { params: { format } });
    return response.data;
  },
  async uploadIngestionDocument(file: File, effectiveFrom?: string): Promise<IngestionDocument> {
    const form = new FormData();
    form.append("file", file);
    if (effectiveFrom) form.append("effective_from", effectiveFrom);
    const response = await http.post<IngestionDocument>("/admin/ingestion/documents", form);
    return response.data;
  },
  async listIngestionDocuments(): Promise<IngestionDocumentList> {
    const response = await http.get<IngestionDocumentList>("/admin/ingestion/documents");
    return response.data;
  },
  async getIngestionDocument(documentId: string): Promise<IngestionDocument> {
    const response = await http.get<IngestionDocument>(`/admin/ingestion/documents/${documentId}`);
    return response.data;
  },
  async retryIngestionDocument(documentId: string): Promise<IngestionDocument> {
    const response = await http.post<IngestionDocument>(`/admin/ingestion/documents/${documentId}/retry`);
    return response.data;
  },
};
