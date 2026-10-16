import { ArrowDown, BookOpen, FileCheck2, LoaderCircle } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { MessageInput } from "@/features/conversation/MessageInput";
import { MessageList } from "@/features/conversation/MessageList";

export function ConversationPanel() {
  const { messages, answer, sending, revealing, finishReply, error, needsLockedFactsPrompt, caseId } = useWorkspace();
  const scrollRef = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const latestId = useRef<string | undefined>(undefined);
  const [atBottom, setAtBottom] = useState(true);

  useLayoutEffect(() => {
    const node = scrollRef.current;
    const latest = messages.at(-1);
    if (node && (following.current || (latest?.role === "user" && latest.id !== latestId.current))) {
      node.scrollTop = node.scrollHeight;
    }
    latestId.current = latest?.id;
  }, [messages]);

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-paper" aria-label="Hội thoại hồ sơ">
      <div className="relative min-h-0 flex-1">
        <div ref={scrollRef} data-conversation-scroll role="region" aria-label="Nội dung hội thoại" tabIndex={0} className="h-full overflow-y-auto overscroll-contain" onScroll={(event) => {
          const node = event.currentTarget;
          const nearBottom = node.scrollHeight - node.scrollTop - node.clientHeight < 96;
          following.current = nearBottom;
          setAtBottom(nearBottom);
        }}>
          <div className="mx-auto w-full max-w-3xl px-4 py-6 md:px-6 md:py-8">
            <MessageList messages={messages} revealing={revealing} />
            {answer ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <Link className="inline-flex items-center gap-2 rounded-full border border-rule bg-white px-3 py-2 text-xs font-medium text-ink-2 hover:bg-paper-2" to={`/cases/${caseId}/assessment`}><FileCheck2 className="h-3.5 w-3.5 text-son" aria-hidden="true" />Mở biên bản</Link>
                <Link className="inline-flex items-center gap-2 rounded-full border border-rule bg-white px-3 py-2 text-xs font-medium text-ink-2 hover:bg-paper-2" to={`/cases/${caseId}/evidence`}><BookOpen className="h-3.5 w-3.5 text-son" aria-hidden="true" />Xem căn cứ</Link>
              </div>
            ) : null}
          </div>
        </div>
        {!atBottom ? (
          <button type="button" aria-label="Về tin nhắn mới nhất" title="Về tin nhắn mới nhất" className="absolute bottom-4 left-1/2 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-rule bg-paper text-ink shadow-md hover:bg-paper-2" onClick={() => {
            following.current = true;
            scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
          }}>
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>
      <div className="shrink-0 bg-paper px-3 pb-3 pt-2 md:px-6 md:pb-4">
        <div className="mx-auto w-full max-w-3xl">
          {revealing ? (
            <div className="mb-2 flex items-center justify-between gap-2 px-2 text-xs text-ink-3">
              <p role="status">Đang hiển thị câu trả lời…</p>
              <button type="button" className="font-medium text-son-dark underline" onClick={finishReply}>Hiện toàn bộ</button>
            </div>
          ) : sending ? <p className="mb-2 flex items-center gap-2 px-2 text-xs text-ink-3" role="status"><LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Trợ lý đang xử lý…</p> : null}
          {error ? <p className="mb-2 rounded-lg bg-son-tint px-3 py-2 text-xs text-son-dark" role="alert">{error}</p> : null}
          {needsLockedFactsPrompt ? <p className="mb-2 px-2 text-xs text-ink-3">Cần xác nhận tình tiết trước khi lập biên bản. <Link className="font-medium text-son-dark underline" to={`/cases/${caseId}/facts`}>Bổ sung tình tiết</Link></p> : null}
          <MessageInput />
          <p className="mt-2 text-center text-[10px] leading-4 text-ink-3">AI hỗ trợ đề xuất. Người có thẩm quyền xem xét và quyết định.</p>
        </div>
      </div>
    </section>
  );
}
