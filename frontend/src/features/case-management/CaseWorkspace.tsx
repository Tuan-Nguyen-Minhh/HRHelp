import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

import { Sheet } from "@/components/ui/sheet";
import { ConversationPanel } from "@/features/conversation/ConversationPanel";
import { useReplyReveal } from "@/features/conversation/useReplyReveal";
import { CASE_SECTIONS } from "@/features/case-management/case-navigation";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { isRawHandoffMessage } from "@/lib/report";
import { clearHandoff, loadHandoff, loadMessages, rememberCase, saveHandoff, saveMessages } from "@/lib/session";
import { agentAfterTurn } from "@/lib/workflow";
import { api, errorMessage } from "@/services/api";
import { subscribeAgentEvents } from "@/services/sse";
import type { AgentEvent, AgentName, AnswerView, CaseHandoff, CaseView, ChatMessage, ChatRole, FactListResponse, TurnResponse } from "@/types/api";
import { CaseHeader } from "@/features/case-management/CaseHeader";

interface WorkspaceValue {
  caseId: string;
  caseView: CaseView;
  facts: FactListResponse | null;
  factsLoading: boolean;
  factsError: string | null;
  answer: AnswerView | null;
  answerLoading: boolean;
  answerError: string | null;
  handoff: CaseHandoff | null;
  messages: ChatMessage[];
  agent: AgentEvent | null;
  error: string | null;
  sending: boolean;
  revealing: boolean;
  finishReply: () => void;
  sendingTicket: boolean;
  failedDraft: string | null;
  send: (content: string) => Promise<void>;
  retry: () => Promise<void>;
  sendTicket: (legalCode: string) => Promise<void>;
  confirmFact: (factKey: string, factValue: string) => Promise<void>;
  confirming: boolean;
  needsLockedFactsPrompt: boolean;
  focusChat: () => void;
  registerChat: (node: HTMLTextAreaElement | null) => void;
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function useWorkspace(): WorkspaceValue {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace phải nằm trong hồ sơ.");
  return value;
}

export function CaseWorkspace() {
  const { caseId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const base = `/cases/${caseId}`;
  const section = location.pathname.slice(base.length).split("/").filter(Boolean)[0];
  const selectedPanel = CASE_SECTIONS.find((item) => item.path === section);
  const lastPanel = useRef("");
  const focusChatAfterClose = useRef(false);
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(caseId));
  const [handoff, setHandoff] = useState<CaseHandoff | null>(() => loadHandoff(caseId));
  const [agent, setAgent] = useState<AgentEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failedDraft, setFailedDraft] = useState<string | null>(null);
  const [needsLockedFactsPrompt, setNeedsLockedFactsPrompt] = useState(false);
  const [chatNode, setChatNode] = useState<HTMLTextAreaElement | null>(null);
  const serverSyncedAt = useRef(0);
  const sendingLocked = useRef(false);
  const { reply, start: revealReply, finish: finishReply } = useReplyReveal(caseId);
  const revealing = reply !== null;

  useEffect(() => {
    if (selectedPanel) lastPanel.current = selectedPanel.path;
  }, [selectedPanel]);

  useEffect(() => {
    setMessages(loadMessages(caseId));
    setHandoff(loadHandoff(caseId));
    setAgent(null);
    setError(null);
    setFailedDraft(null);
    setNeedsLockedFactsPrompt(false);
  }, [caseId]);

  useEffect(() => subscribeAgentEvents(caseId, setAgent), [caseId]);

  const caseQuery = useQuery({ queryKey: ["case", caseId], queryFn: () => api.getCase(caseId), enabled: Boolean(caseId) });
  const factsQuery = useQuery({ queryKey: ["facts", caseId], queryFn: () => api.getFacts(caseId), enabled: Boolean(caseId) });
  const answerQuery = useQuery({ queryKey: ["answer", caseId], queryFn: () => api.getAnswer(caseId), enabled: Boolean(caseId) });
  const messageQuery = useQuery({ queryKey: ["messages", caseId], queryFn: () => api.listMessages(caseId), enabled: Boolean(caseId) });

  useEffect(() => {
    if (caseQuery.data) rememberCase(caseId);
  }, [caseQuery.data, caseId]);

  function commitMessages(next: ChatMessage[]) {
    const normalized = dedupeQuickUserRepeats(next);
    saveMessages(caseId, normalized);
    setMessages(normalized);
  }

  function applyTurn(turn: TurnResponse) {
    queryClient.setQueryData<CaseView>(["case", caseId], (current) =>
      current ? { ...current, status: turn.case_status, conversation_id: turn.conversation_id } : current,
    );
    queryClient.setQueryData<FactListResponse>(["facts", caseId], {
      case_id: turn.case_id,
      case_status: turn.case_status,
      family: turn.family,
      facts: turn.facts,
      missing_fact_keys: turn.missing_fact_keys,
      facts_locked: turn.facts_locked,
    });
    if (turn.answer) queryClient.setQueryData(["answer", caseId], turn.answer);
    else if (turn.case_status === "NEED_INFO") queryClient.setQueryData(["answer", caseId], null);
    if (turn.handoff) {
      saveHandoff(caseId, turn.handoff);
      setHandoff(turn.handoff);
    } else if (turn.case_status === "NEED_INFO") {
      clearHandoff(caseId);
      setHandoff(null);
    }
    setAgent(agentAfterTurn(turn));
    setNeedsLockedFactsPrompt((current) => {
      if (turn.facts_locked || turn.missing_fact_keys.length === 0) return false;
      if (requiresLockedFacts(turn.requested_action)) return true;
      return current;
    });
  }

  const sendMutation = useMutation({
    mutationFn: ({ content }: { content: string; echo: boolean }) => api.postMessage(caseId, content),
    onMutate: ({ content, echo }) => {
      setError(null);
      setFailedDraft(null);
      const facts = queryClient.getQueryData<FactListResponse>(["facts", caseId]);
      const agentName: AgentName = facts?.facts_locked ? "retrieval" : "clarification";
      setAgent({ type: "agent_status", agent: agentName, status: "running" });
      const now = new Date().toISOString();
      const next = loadMessages(caseId).filter((item) => item.id !== "pending");
      if (echo) next.push({ id: crypto.randomUUID(), role: "user", text: content, at: now });
      next.push({ id: "pending", role: "system", text: "AI đang phân tích…", at: now });
      commitMessages(next);
    },
    onSuccess: (turn) => {
      if (turn.case_id !== caseId) return;
      applyTurn(turn);
      const next = loadMessages(caseId).filter((item) => item.id !== "pending");
      if (!isRawHandoffMessage(turn.assistant_message)) {
        const message: ChatMessage = { id: crypto.randomUUID(), role: "assistant", text: turn.assistant_message, at: new Date().toISOString() };
        next.push(message);
        revealReply(message);
      }
      commitMessages(next);
      serverSyncedAt.current = Date.now();
      void queryClient.invalidateQueries({ queryKey: ["messages", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["timeline", caseId] });
    },
    onError: (err, variables) => {
      const message = errorMessage(err);
      setError(message);
      setFailedDraft(variables.content);
      const facts = queryClient.getQueryData<FactListResponse>(["facts", caseId]);
      setAgent({
        type: "agent_status",
        agent: facts?.facts_locked ? "retrieval" : "clarification",
        status: "failed",
      });
      const next = loadMessages(caseId).filter((item) => item.id !== "pending");
      next.push({ id: crypto.randomUUID(), role: "system", text: message, at: new Date().toISOString() });
      commitMessages(next);
    },
  });

  const confirmMutation = useMutation({
    mutationFn: ({ factKey, factValue }: { factKey: string; factValue: string }) =>
      api.confirmFacts(caseId, [{ fact_key: factKey, fact_value: factValue, confirmed: true }]),
    onSuccess: (turn) => {
      if (turn.case_id !== caseId) return;
      applyTurn(turn);
      if (turn.assistant_message && !isRawHandoffMessage(turn.assistant_message)) {
        const next = loadMessages(caseId);
        const message: ChatMessage = { id: crypto.randomUUID(), role: "assistant", text: turn.assistant_message, at: new Date().toISOString() };
        next.push(message);
        revealReply(message);
        commitMessages(next);
        serverSyncedAt.current = Date.now();
      }
      void queryClient.invalidateQueries({ queryKey: ["messages", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["timeline", caseId] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const ticketMutation = useMutation({
    mutationFn: (legalCode: string) => api.sendTicket(caseId, legalCode, idempotencyKey(`ticket:${caseId}:${legalCode}`)),
    onMutate: () => {
      setError(null);
      setAgent({ type: "agent_status", agent: "decision", status: "running" });
    },
    onSuccess: (answer, legalCode) => {
      clearIdempotency(`ticket:${caseId}:${legalCode}`);
      queryClient.setQueryData(["answer", caseId], answer);
      queryClient.setQueryData<CaseView>(["case", caseId], (current) =>
        current ? { ...current, status: answer.case_status } : current,
      );
      const note = answer.ticket?.reason || "Đã nhận phản hồi phiếu.";
      const next = loadMessages(caseId);
      next.push({ id: crypto.randomUUID(), role: "system", text: note, at: new Date().toISOString() });
      commitMessages(next);
      setAgent({
        type: "agent_status",
        agent: answer.case_status === "PENDING_LEGAL" ? "legal_review" : "decision",
        status: "completed",
      });
      void queryClient.invalidateQueries({ queryKey: ["timeline", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["legal-queue"] });
    },
    onError: (err) => {
      setError(errorMessage(err));
      setAgent({ type: "agent_status", agent: "decision", status: "failed" });
    },
  });

  useEffect(() => {
    const rows = messageQuery.data?.messages;
    // A refetch assigns server IDs. Wait until display completes so it cannot
    // replace the partial reply with the complete text halfway through.
    if (!rows || sendMutation.isPending || confirmMutation.isPending || revealing) return;
    if (messageQuery.dataUpdatedAt < serverSyncedAt.current) return;
    const mapped: ChatMessage[] = rows
      .map((item) => ({
        id: item.id,
        role: toChatRole(item.role),
        text: item.content,
        at: item.created_at,
      }))
      .filter((item) => !isRawHandoffMessage(item.text));
    saveMessages(caseId, mapped);
    setMessages(mapped);
  }, [messageQuery.data, messageQuery.dataUpdatedAt, sendMutation.isPending, confirmMutation.isPending, revealing, caseId]);

  if (caseQuery.isLoading) {
    return <div className="space-y-2" role="status" aria-label="Đang tải hồ sơ"><div className="skeleton h-24" aria-hidden="true" /><div className="skeleton h-40" aria-hidden="true" /></div>;
  }
  if (caseQuery.isError || !caseQuery.data) {
    return (
      <div className="rounded-xl border border-son-line bg-son-tint px-4 py-4 text-sm text-son-dark">
        <p>{errorMessage(caseQuery.error)}</p>
        <Link className="mt-2 inline-block font-medium text-son-dark underline" to="/cases">
          Về danh sách
        </Link>
      </div>
    );
  }

  const value: WorkspaceValue = {
    caseId,
    caseView: caseQuery.data,
    facts: factsQuery.data ?? null,
    factsLoading: factsQuery.isLoading,
    factsError: factsQuery.isError ? errorMessage(factsQuery.error) : null,
    answer: answerQuery.data ?? null,
    answerLoading: answerQuery.isLoading,
    answerError: answerQuery.isError ? errorMessage(answerQuery.error) : null,
    handoff,
    messages: reply ? messages.map((message) => message.id === reply.id ? { ...message, text: reply.text } : message) : messages,
    agent,
    error,
    sending: sendMutation.isPending || revealing,
    revealing,
    finishReply,
    sendingTicket: ticketMutation.isPending,
    failedDraft,
    needsLockedFactsPrompt,
    async send(content) {
      if (sendingLocked.current || revealing) return;
      sendingLocked.current = true;
      try {
        await sendMutation.mutateAsync({ content, echo: true });
      } finally {
        sendingLocked.current = false;
      }
    },
    async retry() {
      if (!failedDraft || sendingLocked.current || revealing) return;
      sendingLocked.current = true;
      try {
        await sendMutation.mutateAsync({ content: failedDraft, echo: false });
      } finally {
        sendingLocked.current = false;
      }
    },
    async sendTicket(legalCode) {
      await ticketMutation.mutateAsync(legalCode);
    },
    confirming: confirmMutation.isPending,
    async confirmFact(factKey, factValue) {
      await confirmMutation.mutateAsync({ factKey, factValue });
    },
    focusChat() {
      if (selectedPanel) {
        focusChatAfterClose.current = true;
        navigate(base, { replace: true, preventScrollReset: true });
      } else chatNode?.focus();
    },
    registerChat: setChatNode,
  };

  return (
    <WorkspaceContext.Provider value={value}>
      <div className="case-workspace flex h-full min-h-0 flex-col">
        <CaseHeader />
        <ConversationPanel />
        <Sheet
          open={Boolean(selectedPanel)}
          onOpenChange={(open) => { if (!open) navigate(base, { replace: true, preventScrollReset: true }); }}
          title={`${selectedPanel?.label ?? "Hồ sơ"} · ${caseQuery.data.case_code.toLocaleUpperCase("vi-VN")}`}
          description="Xem và xử lý thông tin hồ sơ. Đóng bảng để tiếp tục hội thoại; nội dung đang soạn được giữ nguyên."
          className={selectedPanel?.path === "assessment" || selectedPanel?.path === "legal-review" ? "case-detail-panel max-w-6xl" : selectedPanel?.path === "overview" ? "case-detail-panel max-w-2xl" : "case-detail-panel max-w-4xl"}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (focusChatAfterClose.current) {
              focusChatAfterClose.current = false;
              chatNode?.focus();
            } else document.getElementById(`case-tool-${lastPanel.current}`)?.focus();
          }}
        >
          {selectedPanel ? <Outlet /> : null}
        </Sheet>
      </div>
    </WorkspaceContext.Provider>
  );
}

function requiresLockedFacts(action: string | null | undefined): boolean {
  return action === "draft_minutes" || action === "create_ticket_preview" || action === "send_to_legal";
}

function toChatRole(role: string): ChatRole {
  const value = role.toUpperCase();
  if (value === "USER") return "user";
  if (value === "ASSISTANT") return "assistant";
  return "system";
}

function dedupeQuickUserRepeats(messages: ChatMessage[]): ChatMessage[] {
  const result: ChatMessage[] = [];
  for (const message of messages) {
    const previous = result.at(-1);
    if (
      previous?.role === "user" &&
      message.role === "user" &&
      previous.text.trim() === message.text.trim() &&
      Math.abs(new Date(message.at).getTime() - new Date(previous.at).getTime()) <= 5000
    ) {
      continue;
    }
    result.push(message);
  }
  return result;
}
