import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { FactItem } from "@/features/evidence/FactItem";
import { familyLabel } from "@/lib/labels";
import { MUTABLE_CASE_STATUS } from "@/lib/workflow";
import { errorMessage } from "@/services/api";
import type { FactView } from "@/types/api";

export function FactPanel() {
  const { facts, factsLoading, factsError, caseView, confirmFact, confirming } = useWorkspace();
  const [editing, setEditing] = useState<FactView | null>(null);
  const [draft, setDraft] = useState("");
  const [ask, setAsk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = MUTABLE_CASE_STATUS.has(caseView.status);

  function start(fact: FactView) {
    setEditing(fact);
    setDraft(fact.fact_value ?? "");
    setAsk(false);
    setError(null);
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Tình tiết</CardTitle>
          <p className="mt-1 text-xs text-[#4d7380]">{facts ? familyLabel(facts.family) : "Đang đọc nhóm tình tiết"}</p>
        </div>
      </CardHeader>
      <CardContent>
        {factsLoading ? <p className="text-sm text-[#4d7380]">Đang tải tình tiết…</p> : null}
        {factsError ? <p className="text-sm text-red-800">{factsError}</p> : null}
        {facts ? (
          <ul>
            {facts.facts.map((fact) => (
              <FactItem key={fact.fact_key} fact={fact} onEdit={editable ? start : undefined} />
            ))}
          </ul>
        ) : null}
        {!factsLoading && !facts ? <p className="text-sm text-[#4d7380]">Chưa đọc được tình tiết.</p> : null}
        {editing ? (
          <div className="mt-3 rounded-lg border border-[#d5e8ed] bg-[#f4fafb] p-3 text-sm">
            <p className="font-medium text-[#073642]">{editing.label}</p>
            <p className="mt-1 text-[#4d7380]">AI nhận diện: {editing.fact_value}</p>
            <label className="mt-2 block space-y-1" htmlFor="fact-correction">
              <span className="text-xs font-medium">Giá trị HR xác nhận</span>
              <Input id="fact-correction" value={draft} onChange={(event) => setDraft(event.target.value)} />
            </label>
            {error ? <p className="mt-2 text-red-800">{error}</p> : null}
            {ask ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
                <p>AI nhận diện: {editing.fact_value}</p>
                <p className="mt-1">Giá trị của bạn: {draft.trim()}</p>
                <div className="mt-2 flex gap-2">
                  <Button variant="secondary" onClick={() => setAsk(false)}>
                    Hủy
                  </Button>
                  <Button
                    disabled={confirming || !draft.trim()}
                    onClick={() => {
                      void confirmFact(editing.fact_key, draft.trim())
                        .then(() => setEditing(null))
                        .catch((err: unknown) => setError(errorMessage(err)));
                    }}
                  >
                    {confirming ? "Đang lưu…" : "Xác nhận"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex gap-2">
                <Button variant="secondary" onClick={() => setEditing(null)}>
                  Đóng
                </Button>
                <Button disabled={!draft.trim()} onClick={() => setAsk(true)}>
                  Kiểm tra lại
                </Button>
              </div>
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
