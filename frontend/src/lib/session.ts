import type { CaseHandoff, ChatMessage, TokenResponse } from "@/types/api";
import { isRawHandoffMessage } from "@/lib/report";

const AUTH_KEY = "hr_auth";
const CASE_KEY = "hr_case_id";

function readJson<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function readAuth(): TokenResponse | null {
  const value = readJson<TokenResponse>(AUTH_KEY);
  if (!value?.access_token || !value.refresh_token) return null;
  return value;
}

export function writeAuth(value: TokenResponse): void {
  sessionStorage.setItem(AUTH_KEY, JSON.stringify(value));
}

export function clearAuth(): void {
  sessionStorage.removeItem(AUTH_KEY);
}

export function rememberCase(caseId: string): void {
  sessionStorage.setItem(CASE_KEY, caseId);
}

export function rememberedCase(): string | null {
  return sessionStorage.getItem(CASE_KEY);
}

function messageKey(caseId: string): string {
  return `hr_messages_${caseId}`;
}

function handoffKey(caseId: string): string {
  return `hr_handoff_${caseId}`;
}

export function loadMessages(caseId: string): ChatMessage[] {
  const value = readJson<ChatMessage[]>(messageKey(caseId));
  return Array.isArray(value) ? value.filter((item) => !isRawHandoffMessage(item.text)) : [];
}

export function saveMessages(caseId: string, messages: ChatMessage[]): void {
  const visible = messages.filter((item) => !isRawHandoffMessage(item.text));
  sessionStorage.setItem(messageKey(caseId), JSON.stringify(visible.slice(-200)));
}

export function loadHandoff(caseId: string): CaseHandoff | null {
  const value = readJson<CaseHandoff>(handoffKey(caseId));
  if (!value || !Array.isArray(value.passages)) return null;
  return value;
}

export function saveHandoff(caseId: string, handoff: CaseHandoff): void {
  sessionStorage.setItem(handoffKey(caseId), JSON.stringify(handoff));
}

export function clearHandoff(caseId: string): void {
  sessionStorage.removeItem(handoffKey(caseId));
}
