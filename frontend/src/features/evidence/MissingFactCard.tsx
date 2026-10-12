import { AlertTriangle, MessageSquareText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";

export function MissingFactCard() {
  const { facts, messages, focusChat } = useWorkspace();
  if (!facts || facts.missing_fact_keys.length === 0) return null;
  const missing = new Set(facts.missing_fact_keys);
  const items = facts.facts.filter((fact) => missing.has(fact.fact_key));
  const question = [...messages].reverse().find((message) => message.role === "assistant")?.text;
  return (
    <Card className="border-son-line bg-son-tint/30">
      <CardHeader className="border-son-line bg-white">
        <CardTitle className="flex items-center gap-2 text-son-dark">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Cần thêm thông tin
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-ink-2">Bổ sung các mục dưới đây để agent có đủ căn cứ đối chiếu quy định và lập đề xuất.</p>
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          {items.map((fact) => (
            <li key={fact.fact_key} className="rounded-xl border border-son-line bg-white px-3 py-2">
              <p className="font-medium text-ink">{fact.label}</p>
              <p className="text-xs text-ink-3">{fact.fact_key}</p>
            </li>
          ))}
        </ul>
        <div className="rounded-xl border border-rule bg-white p-3">
          <p className="flex items-center gap-2 text-xs font-semibold text-ink-2">
            <MessageSquareText className="h-4 w-4 text-son-dark" aria-hidden="true" />
            Câu hỏi từ agent pháp chế
          </p>
          <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-ink">
            {question || "Câu hỏi nằm trong hội thoại sau khi bạn mô tả vụ việc."}
          </p>
        </div>
        <Button className="w-full sm:w-auto" variant="secondary" onClick={focusChat}>
          Trả lời trong hội thoại
        </Button>
      </CardContent>
    </Card>
  );
}
