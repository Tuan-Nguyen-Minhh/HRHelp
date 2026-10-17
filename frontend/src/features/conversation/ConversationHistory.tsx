import { Check, ChevronDown, History, MessageSquare, Plus } from "lucide-react";
import { useEffect, useId, useRef, type RefObject } from "react";

import { cn, formatDate } from "@/lib/utils";
import type { StandaloneConversation } from "@/types/api";

interface ConversationHistoryProps {
  conversations: StandaloneConversation[];
  conversationId: string;
  currentTitle: string;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  onSelect: (id: string) => void;
  loading: boolean;
  disabled: boolean;
  error: string | null;
  onRetry: () => void;
}

export function ConversationHistory({ conversations, conversationId, currentTitle, expanded, onExpandedChange, triggerRef, onSelect, loading, disabled, error, onRetry }: ConversationHistoryProps) {
  const panelId = useId();
  const headingId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const title = currentTitle.replace(/\s+/g, " ").trim() || "Cuộc trò chuyện mới";

  useEffect(() => {
    if (!expanded) return;
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) onExpandedChange(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [expanded, onExpandedChange]);

  function select(id: string) {
    onSelect(id);
    onExpandedChange(false);
    triggerRef.current?.focus();
  }

  return (
    <div ref={rootRef} className="relative shrink-0 border-b border-rule bg-paper px-3 py-3" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) onExpandedChange(false);
    }}>
      <div className="flex min-w-0 items-center gap-2">
        <button ref={triggerRef} type="button" aria-label={`Lịch sử trò chuyện: Cuộc trò chuyện ${title}`} aria-expanded={expanded} aria-controls={panelId} disabled={disabled} title={title} onClick={() => onExpandedChange(!expanded)} className={cn(
          "chat-history-control flex min-h-11 min-w-0 flex-1 items-center gap-2.5 rounded-xl border border-rule bg-white px-3 py-2 text-left transition-colors hover:border-rule-2 hover:bg-paper-2 disabled:cursor-not-allowed disabled:opacity-50",
          expanded && "border-rule-2 bg-paper-2",
        )}>
          <History className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] font-medium leading-4 text-ink-3">Cuộc trò chuyện</span>
            <span className="block truncate text-xs font-semibold leading-5 text-ink">{title}</span>
          </span>
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-ink-3 transition-transform", expanded && "rotate-180")} aria-hidden="true" />
        </button>
        <button type="button" disabled={disabled} onClick={() => select("")} className="chat-history-control inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-xl border border-son-line bg-son-tint px-3 text-xs font-semibold text-son-dark transition-colors hover:border-son hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50">
          <Plus className="h-4 w-4" aria-hidden="true" />Chat mới
        </button>
      </div>
      <div id={panelId} hidden={!expanded} role="region" aria-labelledby={headingId} className="absolute left-3 right-3 top-[calc(100%-4px)] z-10 overflow-hidden rounded-xl border border-rule bg-white shadow-lg">
        <div className="flex items-center justify-between gap-2 border-b border-rule bg-paper px-3 py-2.5">
          <h2 id={headingId} className="text-xs font-semibold text-ink">Lịch sử trò chuyện</h2>
          {!loading && !error ? <span className="text-[10px] tabular-nums text-ink-3">{conversations.length} hội thoại</span> : null}
        </div>
        <div className="max-h-[min(280px,40dvh)] overflow-y-auto overscroll-contain p-1.5" aria-busy={loading}>
          {loading ? <div role="status" aria-label="Đang tải lịch sử trò chuyện" className="space-y-2 p-2">{[0, 1, 2].map((key) => <div key={key} className="skeleton h-11 rounded-lg" aria-hidden="true" />)}</div> : null}
          {error ? <div className="px-3 py-4"><p role="alert" className="text-xs leading-5 text-son-dark">{error}</p><button type="button" onClick={onRetry} className="chat-history-control mt-2 min-h-11 rounded-xl px-2 text-xs font-semibold text-son-dark underline">Thử tải lại</button></div> : null}
          {!loading && !error && !conversations.length ? <div className="px-4 py-5 text-center"><MessageSquare className="mx-auto mb-2 h-5 w-5 text-ink-3" aria-hidden="true" /><p className="text-xs font-medium text-ink">Chưa có cuộc trò chuyện</p><p className="mt-1 text-[11px] leading-5 text-ink-3">Gửi tin nhắn đầu tiên để bắt đầu. Hội thoại sẽ được lưu tại đây.</p></div> : null}
          {!loading && !error && conversations.length ? (
            <ul className="space-y-1">
              {conversations.map((item) => {
                const current = item.id === conversationId;
                return <li key={item.id}>
                  <button type="button" aria-current={current ? "true" : undefined} disabled={disabled} title={item.title} onClick={() => select(item.id)} className={cn("chat-history-control flex min-h-11 w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-paper-2 disabled:cursor-not-allowed disabled:opacity-50", current && "bg-paper-2")}>
                    <MessageSquare className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
                    <span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium leading-5 text-ink">{item.title}</span><span className="block text-[10px] leading-4 text-ink-3">{current ? "Đang mở · " : ""}{formatDate(item.updated_at)}</span></span>
                    {current ? <Check className="h-4 w-4 shrink-0 text-ink-2" aria-hidden="true" /> : null}
                  </button>
                </li>;
              })}
            </ul>
          ) : null}
        </div>
      </div>
      {error && !expanded ? <p role="alert" className="mt-2 text-xs leading-5 text-son-dark">Không tải được lịch sử. <button type="button" onClick={() => onExpandedChange(true)} className="font-semibold underline">Thử lại</button></p> : null}
    </div>
  );
}
