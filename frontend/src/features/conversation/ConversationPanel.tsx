import { Check, MessageSquareText, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { MessageInput } from "@/features/conversation/MessageInput";
import { MessageList } from "@/features/conversation/MessageList";
import { MUTABLE_CASE_STATUS } from "@/lib/workflow";
import { errorMessage } from "@/services/api";
import type { FactView } from "@/types/api";

export function ConversationPanel() {
  const { messages } = useWorkspace();
  return (
    <Card className="flex min-h-[520px] flex-col overflow-hidden border-[#d8e9ee] bg-[#f7fbfd] shadow-sm xl:max-h-[calc(100vh-6rem)]">
      <CardHeader className="border-b border-[#d8e9ee] bg-white/90">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-14 w-14 shrink-0 items-end justify-center overflow-hidden rounded-2xl border border-[#cfe5ec] bg-[#e7f7fb] shadow-sm">
              <img className="h-full w-full object-cover object-top" src="/legal-agent-avatar.png" alt="Agent pháp chế" />
            </span>
            <div>
              <CardTitle>Agent pháp chế</CardTitle>
              <p className="mt-1 text-xs leading-5 text-[#4d7380]">
                Hỏi phần còn thiếu, gợi ý căn cứ và giữ hội thoại dễ tra lại. Người phụ trách vẫn là người duyệt cuối.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 font-medium text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Đang sẵn sàng
            </span>
            <span className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 font-medium text-[#007c9d]">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Có ngữ cảnh hồ sơ
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
        <div className="h-full min-h-[260px] overflow-y-auto px-4 py-5 md:px-6 xl:max-h-[calc(100vh-22rem)]">
          <MessageList messages={messages} />
          <MissingFactPrompt />
          {messages.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {["Tóm tắt tình tiết", "Cần bổ sung chứng cứ gì?", "Kiểm tra rủi ro quy trình"].map((item) => (
                <span key={item} className="inline-flex items-center gap-1.5 rounded-full border border-[#cfe5ec] bg-white px-3 py-1.5 text-xs font-medium text-[#315867] shadow-sm">
                  <MessageSquareText className="h-3.5 w-3.5 text-[#009ec1]" aria-hidden="true" />
                  {item}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </CardContent>
      <MessageInput />
    </Card>
  );
}

function MissingFactPrompt() {
  const { caseView, facts, confirmFact, confirming, send, sending, needsLockedFactsPrompt } = useWorkspace();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [chatDraft, setChatDraft] = useState("");
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const editable = MUTABLE_CASE_STATUS.has(caseView.status);
  const missing = useMemo(() => missingFacts(facts?.facts ?? [], facts?.missing_fact_keys ?? []), [facts]);

  if (!editable || !needsLockedFactsPrompt || facts?.facts_locked || missing.length === 0) return null;

  async function save(fact: FactView) {
    const value = (drafts[fact.fact_key] ?? "").trim();
    if (!value) return;
    setError(null);
    setSavingKey(fact.fact_key);
    try {
      await confirmFact(fact.fact_key, value);
      setDrafts((current) => {
        const next = { ...current };
        delete next[fact.fact_key];
        return next;
      });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSavingKey(null);
    }
  }

  async function sendChatAnswer() {
    const value = chatDraft.trim();
    if (!value) return;
    setError(null);
    try {
      await send(value);
      setChatDraft("");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="mt-4 rounded-xl border border-[#cfe5ec] bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#073642]">Cần bổ sung để tạo biên bản</p>
          <p className="mt-1 text-xs leading-5 text-[#607d88]">
            Agent cần khóa đủ các tình tiết dưới đây trước khi lập biên bản, tạo phiếu hoặc chuyển bước xử lý.
          </p>
        </div>
        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">
          {missing.length} mục
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {missing.map((fact) => {
          const value = drafts[fact.fact_key] ?? "";
          const saving = confirming && savingKey === fact.fact_key;
          return (
            <div key={fact.fact_key} className="grid gap-2 rounded-lg border border-[#e1eef2] bg-[#f8fbfd] p-2 md:grid-cols-[minmax(9rem,14rem)_1fr_auto] md:items-center">
              <label className="text-sm font-medium text-[#073642]" htmlFor={`missing-${fact.fact_key}`}>
                {fact.label}
              </label>
              <Input
                id={`missing-${fact.fact_key}`}
                value={value}
                disabled={confirming}
                placeholder={placeholderFor(fact)}
                onChange={(event) => setDrafts((current) => ({ ...current, [fact.fact_key]: event.target.value }))}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void save(fact);
                  }
                }}
              />
              <Button className="md:w-24" size="sm" disabled={confirming || !value.trim()} onClick={() => void save(fact)}>
                <Check className="h-4 w-4" aria-hidden="true" />
                {saving ? "Lưu…" : "Lưu"}
              </Button>
            </div>
          );
        })}
      </div>
      <div className="mt-3 rounded-lg border border-dashed border-[#cfe5ec] bg-[#f8fbfd] p-2">
        <label className="text-xs font-semibold text-[#315867]" htmlFor="missing-fact-chat">
          Hoặc trả lời bằng chat
        </label>
        <textarea
          id="missing-fact-chat"
          rows={2}
          value={chatDraft}
          disabled={sending}
          placeholder={chatPlaceholder(missing)}
          className="mt-1 w-full resize-none rounded-lg border border-[#d7e8ee] bg-white px-3 py-2 text-sm leading-5 text-[#073642] placeholder:text-[#7b96a0] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009ec1]/30 disabled:bg-neutral-100"
          onChange={(event) => setChatDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void sendChatAnswer();
            }
          }}
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <p className="text-xs text-[#607d88]">Agent sẽ tự nhận diện các thông tin này và cập nhật vào hồ sơ.</p>
          <Button size="sm" variant="secondary" disabled={sending || !chatDraft.trim()} onClick={() => void sendChatAnswer()}>
            {sending ? "Đang gửi…" : "Gửi chat"}
          </Button>
        </div>
      </div>
      {error ? <p className="mt-2 text-xs text-red-800">{error}</p> : null}
    </section>
  );
}

function missingFacts(facts: FactView[], keys: string[]): FactView[] {
  const wanted = new Set(keys);
  return facts.filter((fact) => wanted.has(fact.fact_key) || (!fact.confirmed && !fact.fact_value));
}

function placeholderFor(fact: FactView): string {
  if (fact.fact_key.includes("minutes") || fact.fact_key.includes("explanation")) return "Ví dụ: có / chưa";
  if (fact.fact_key.includes("days")) return "Ví dụ: 5 ngày";
  if (fact.fact_key.includes("contract")) return "Ví dụ: xác định thời hạn";
  if (fact.fact_key.includes("notice")) return "Ví dụ: không báo / có đơn";
  return "Nhập giá trị cần xác nhận";
}

function chatPlaceholder(facts: FactView[]): string {
  const labels = facts.slice(0, 3).map((fact) => fact.label.toLowerCase());
  if (labels.length === 0) return "Ví dụ: hợp đồng xác định thời hạn, đã lập biên bản.";
  return `Ví dụ: ${labels.join(", ")}...`;
}
