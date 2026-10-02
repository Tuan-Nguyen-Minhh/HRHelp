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
    <Card className="border-amber-200 bg-amber-50/30">
      <CardHeader className="border-amber-100 bg-white">
        <CardTitle className="flex items-center gap-2 text-amber-950">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Cần thêm thông tin
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-neutral-700">Bổ sung các mục dưới đây để agent có đủ căn cứ đối chiếu quy định và lập đề xuất.</p>
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          {items.map((fact) => (
            <li key={fact.fact_key} className="rounded-xl border border-amber-100 bg-white px-3 py-2">
              <p className="font-medium text-neutral-900">{fact.label}</p>
              <p className="text-xs text-neutral-500">{fact.fact_key}</p>
            </li>
          ))}
        </ul>
        <div className="rounded-xl border border-[#d8e9ee] bg-white p-3">
          <p className="flex items-center gap-2 text-xs font-semibold text-[#315867]">
            <MessageSquareText className="h-4 w-4 text-[#009ec1]" aria-hidden="true" />
            Câu hỏi từ agent pháp chế
          </p>
          <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-neutral-800">
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
