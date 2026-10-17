import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { ArrowDown, BookOpen, LoaderCircle } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

import { ConversationHistory } from "@/features/conversation/ConversationHistory";
import { ChatComposer } from "@/features/conversation/MessageInput";
import { MessageList } from "@/features/conversation/MessageList";
import { useReplyReveal } from "@/features/conversation/useReplyReveal";
import { api, errorMessage } from "@/services/api";
import type { ChatMessage, StandaloneMessagesResponse } from "@/types/api";

function chatMessages(data?: StandaloneMessagesResponse): ChatMessage[] {
  return (data?.messages ?? []).filter((row) => row.role === "USER" || row.role === "ASSISTANT").map((row) => ({
    id: row.id, role: row.role === "USER" ? "user" : "assistant", text: row.content, at: row.created_at,
  }));
}

export function StandaloneChatPanel({ open, historyOpen, onHistoryOpenChange, historyTriggerRef }: {
  open: boolean;
  historyOpen: boolean;
  onHistoryOpenChange: (open: boolean) => void;
  historyTriggerRef: RefObject<HTMLButtonElement | null>;
}) {
  const [conversationId, setConversationId] = useState("");
  const queryClient = useQueryClient();
  const [optimistic, setOptimistic] = useState<ChatMessage | null>(null);
  const [failedDraft, setFailedDraft] = useState<string | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const pendingReveal = useRef<{ conversationId: string; message: ChatMessage } | null>(null);
  const { reply, start, finish } = useReplyReveal(conversationId);
  const conversations = useQuery({ queryKey: ["standalone-conversations"], queryFn: api.listConversations, enabled: open });
  const history = useQuery({
    queryKey: ["standalone-messages", conversationId],
    queryFn: () => api.standaloneMessages(conversationId), enabled: open && Boolean(conversationId),
  });
  const send = useMutation({
    mutationFn: (content: string) => api.sendStandaloneMessage(content, conversationId || undefined),
    onMutate: (content) => {
      finish();
      following.current = true;
      setOptimistic({ id: crypto.randomUUID(), role: "user", text: content, at: new Date().toISOString() });
    },
    onSuccess: (result) => {
      setFailedDraft(null);
      const latest = chatMessages(result).at(-1);
      if (latest?.role === "assistant") pendingReveal.current = { conversationId: result.conversation_id, message: latest };
      queryClient.setQueryData(["standalone-messages", result.conversation_id], result);
      setConversationId(result.conversation_id);
    },
    onError: (error, content) => {
      setFailedDraft(content);
      if (isAxiosError(error)) {
        const savedId = error.response?.data?.error?.details?.conversation_id;
        if (typeof savedId === "string") {
          void queryClient.invalidateQueries({ queryKey: ["standalone-messages", savedId] });
          setConversationId(savedId);
        }
      }
    },
    onSettled: () => {
      setOptimistic(null);
      void queryClient.invalidateQueries({ queryKey: ["standalone-conversations"] });
      if (conversationId) void queryClient.invalidateQueries({ queryKey: ["standalone-messages", conversationId] });
    },
  });
  const messages = chatMessages(history.data);
  if (optimistic) messages.push(optimistic);
  const visible = reply ? messages.map((message) => message.id === reply.id ? { ...message, text: reply.text } : message) : messages;

  useEffect(() => {
    if (pendingReveal.current?.conversationId === conversationId && history.data) {
      const message = pendingReveal.current.message;
      pendingReveal.current = null;
      start(message);
    }
  }, [conversationId, history.data]);

  useLayoutEffect(() => {
    if (following.current && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history.data, optimistic, reply?.text, conversationId, open]);

  function selectConversation(id: string) {
    if (send.isPending) return;
    finish();
    send.reset();
    setFailedDraft(null);
    following.current = true;
    setAtBottom(true);
    setConversationId(id);
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label="Hội thoại độc lập">
      <ConversationHistory
        conversations={conversations.data?.conversations ?? []}
        conversationId={conversationId}
        currentTitle={conversationId ? conversations.data?.conversations.find((item) => item.id === conversationId)?.title || messages.find((message) => message.role === "user")?.text || "Hội thoại hiện tại" : "Cuộc trò chuyện mới"}
        expanded={historyOpen}
        onExpandedChange={onHistoryOpenChange}
        triggerRef={historyTriggerRef}
        onSelect={selectConversation}
        loading={conversations.isLoading}
        disabled={send.isPending}
        error={conversations.isError ? errorMessage(conversations.error) : null}
        onRetry={() => void conversations.refetch()}
      />
      <div className="relative min-h-0 flex-1">
        <div ref={scrollRef} tabIndex={0} role="region" aria-label="Nội dung hội thoại" className="h-full overflow-y-auto overscroll-contain" onScroll={(event) => {
          const node = event.currentTarget;
          following.current = node.scrollHeight - node.scrollTop - node.clientHeight < 96;
          setAtBottom(following.current);
        }}>
          <div className="w-full px-3 py-4">
            {history.isLoading && conversationId ? <p className="text-sm text-ink-3" role="status">Đang tải hội thoại…</p> : null}
            {history.isError ? <div role="alert" className="text-sm text-son-dark">{errorMessage(history.error)} <button type="button" className="underline" onClick={() => void history.refetch()}>Tải lại</button></div> : null}
            {visible.length ? <MessageList messages={visible} revealing={Boolean(reply)} /> : !history.isLoading && !history.isError ? (
              <div className="rounded-2xl border border-rule bg-white p-4 shadow-sm">
                <h2 className="text-sm font-semibold text-ink">Mình có thể giúp gì cho bạn?</h2>
                <p className="mt-1 text-xs leading-5 text-ink-3">Hỏi quy định, tìm nguồn công khai hoặc trò chuyện cùng trợ lý.</p>
                <p className="mt-4 flex items-start gap-2 rounded-xl bg-paper-2 p-3 text-xs leading-5 text-ink-3"><BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-son" aria-hidden="true" />Bạn có thể hỏi: “Trình tự xử lý kỷ luật lao động gồm những bước nào?”</p>
                <p className="mt-3 text-xs leading-5 text-ink-3">Muốn thu thập tình tiết hoặc lập biên bản, hãy mở hội thoại trong hồ sơ.</p>
              </div>
            ) : null}
          </div>
        </div>
        {!atBottom ? <button type="button" aria-label="Về tin nhắn mới nhất" className="absolute bottom-3 left-1/2 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-rule bg-paper shadow-md" onClick={() => { following.current = true; scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }}><ArrowDown className="h-4 w-4" /></button> : null}
      </div>
      <div className="w-full shrink-0 px-3 pb-3 pt-2">
        {send.isPending ? <p className="mb-2 flex items-center gap-2 text-xs text-ink-3" role="status"><LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Trợ lý đang xử lý…</p> : null}
        {reply ? <div className="mb-2 flex justify-between text-xs text-ink-3"><span role="status">Đang hiển thị câu trả lời…</span><button type="button" className="text-son-dark underline" onClick={finish}>Hiện toàn bộ</button></div> : null}
        {send.isError ? <p className="mb-2 text-xs text-son-dark" role="alert">{errorMessage(send.error)}</p> : null}
        <ChatComposer key={conversationId || "new"} failedDraft={failedDraft} sending={send.isPending || Boolean(conversationId && (history.isLoading || history.isError))} send={async (content) => { await send.mutateAsync(content); }} placeholder="Nhập câu hỏi hoặc nội dung muốn trao đổi…" />
        <p className="mt-2 text-center text-[10px] leading-4 text-ink-3">AI hỗ trợ tra cứu và giải thích. Người có thẩm quyền xem xét và quyết định.</p>
      </div>
    </section>
  );
}
