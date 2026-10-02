import { AlertTriangle } from "lucide-react";

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
    <Card className="border-amber-200">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-amber-950">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Cần thêm thông tin
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-neutral-700">Đánh giá cần các mục backend còn đánh dấu thiếu:</p>
        <ul className="space-y-2">
          {items.map((fact) => (
            <li key={fact.fact_key}>
              <p className="font-medium text-neutral-900">{fact.label}</p>
              <p className="text-xs text-neutral-500">{fact.fact_key}</p>
            </li>
          ))}
        </ul>
        <div>
          <p className="text-xs font-medium text-neutral-500">Câu hỏi từ trợ lý</p>
          <p className="mt-1 whitespace-pre-wrap text-neutral-800">
            {question || "Câu hỏi nằm trong hội thoại sau khi bạn mô tả vụ việc."}
          </p>
        </div>
        <Button variant="secondary" onClick={focusChat}>
          Trả lời trong hội thoại
        </Button>
      </CardContent>
    </Card>
  );
}
