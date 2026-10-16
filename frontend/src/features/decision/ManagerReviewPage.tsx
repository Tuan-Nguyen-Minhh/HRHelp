import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { StatusBadge, ToneBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { DocumentSections, EvidenceDetail, sectionLinks } from "@/features/assessment/form/Sections";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { sanctionLabel } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";
import type { EvidenceCard } from "@/types/assessment";

export function ManagerReviewPage() {
  const { caseId = "" } = useParams();
  // Reset form state when a different case is opened through a notification.
  return <ManagerReview key={caseId} caseId={caseId} />;
}

function ManagerReview({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const pack = useQuery({ queryKey: ["manager-review-pack", caseId], queryFn: () => api.managerReviewPack(caseId), retry: false });
  const waiting = pack.data?.status === "APPROVED";
  const preview = useQuery({ queryKey: ["decision-preview", caseId], queryFn: () => api.decisionPreview(caseId), enabled: waiting, retry: false });
  const [code, setCode] = useState("");
  const [summary, setSummary] = useState("");
  const [basis, setBasis] = useState("");
  const [comment, setComment] = useState("");
  const [confirm, setConfirm] = useState<"APPROVE" | "REJECT" | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EvidenceCard | null>(null);
  const submit = useMutation({
    mutationFn: async (decision: "APPROVE" | "REJECT") => {
      if (decision === "REJECT") {
        await api.rejectDecision(caseId, comment.trim(), idempotencyKey(`manager-reject:${caseId}`));
      } else {
        await api.issueDecision(caseId, { decision_code: code.trim(), summary: summary.trim(), legal_basis: basis.trim() || null }, idempotencyKey(`decision:${caseId}`));
      }
      return decision;
    },
    onSuccess: (decision) => {
      clearIdempotency(decision === "REJECT" ? `manager-reject:${caseId}` : `decision:${caseId}`);
      setDone(decision === "REJECT" ? "Đã không duyệt và trả hồ sơ về HR kèm lý do xử lý lại." : "Đã duyệt hồ sơ và ban hành quyết định.");
      setConfirm(null);
      setError(null);
      for (const queryKey of [["manager-review-pack", caseId], ["manager-queue"], ["decision-preview", caseId], ["cases"], ["dashboard"], ["notifications"], ["timeline", caseId]]) {
        void queryClient.invalidateQueries({ queryKey });
      }
    },
    onError: (err) => setError(errorMessage(err)),
  });

  if (pack.isLoading) return <p role="status" className="text-sm">Đang tải biên bản và hồ sơ duyệt…</p>;
  if (pack.isError || !pack.data) return (
    <div className="space-y-3">
      <Link className="text-sm text-son-dark underline" to="/dashboard">Bảng điều khiển</Link>
      <p role="alert" className="text-sm text-son-dark">{errorMessage(pack.error)}</p>
      <Button variant="secondary" onClick={() => void pack.refetch()}>Thử lại</Button>
    </div>
  );

  const assessment = pack.data.assessment;
  const minutes = pack.data.answer.drafts.filter((item) => item.draft_type === "MINUTES");
  const locked = !waiting || Boolean(done);
  const canApprove = !locked && Boolean(preview.data) && Boolean(code.trim()) && Boolean(summary.trim());

  function ask(decision: "APPROVE" | "REJECT") {
    setError(null);
    setConfirm(decision);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="space-y-2">
        <Link className="text-sm text-son-dark underline" to="/dashboard">Bảng điều khiển</Link>
        <h1 className="text-2xl font-semibold text-ink">Duyệt lần cuối · {pack.data.case_code}</h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-ink-3">
          <span>{pack.data.employee_name || "Chưa có tên người lao động"}</span>
          {waiting ? <ToneBadge tone="warning" label="Chờ duyệt cuối" /> : <StatusBadge status={pack.data.status} />}
        </div>
        <p className="text-sm text-ink-3">Đọc biên bản và căn cứ trước khi duyệt hoặc yêu cầu HR xử lý lại.</p>
        <Button asChild variant="secondary" size="sm"><a href="#manager-conclusion">Đến phần duyệt / không duyệt</a></Button>
      </header>

      {assessment ? (
        <div className="grid items-start gap-4 lg:grid-cols-[11rem_minmax(0,1fr)]">
          <nav className="flex gap-2 overflow-x-auto lg:sticky lg:top-24 lg:block lg:space-y-1" aria-label="Mục biên bản">
            {sectionLinks().map((item) => <a key={item.id} href={`#${item.id}`} className="block shrink-0 rounded-md px-3 py-1.5 text-sm text-ink hover:bg-paper-2">{item.label}</a>)}
          </nav>
          <DocumentSections
            view={assessment} sections={assessment.sections} editing={null} saving={false}
            onBegin={() => undefined} onCancel={() => undefined} onSave={() => undefined}
            onCase={() => undefined} onEmployee={() => undefined} onIncident={() => undefined}
            onFacts={() => undefined} onRationale={() => undefined} onOpen={setSelected}
          />
        </div>
      ) : (
        <Card>
          <CardHeader><CardTitle>Biên bản</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            {minutes.length ? minutes.map((item) => <p key={item.draft_id} className="whitespace-pre-wrap">{item.content}</p>) : <p>Hồ sơ chưa có biên bản đã lưu. Hãy yêu cầu HR bổ sung trong phần “Không duyệt” bên dưới.</p>}
          </CardContent>
        </Card>
      )}

      <Card id="manager-conclusion" className="scroll-mt-24">
        <CardHeader><CardTitle>Kết luận của quản lý</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {done ? <p role="status" className="rounded-lg bg-paper-2 p-3 text-sm">{done}</p> : null}
          {error ? <p role="alert" className="text-sm text-son-dark">{error}</p> : null}
          {locked ? <p className="text-sm text-ink-3">Hồ sơ đã rời hàng chờ duyệt cuối.</p> : (
            <>
              {preview.isLoading ? <p role="status" className="text-sm">Đang tải dự thảo quyết định…</p> : null}
              {preview.isError ? <p role="alert" className="rounded-lg border border-son-line bg-son-tint p-3 text-sm text-son-dark">Chưa thể duyệt: {errorMessage(preview.error)} Bạn vẫn có thể không duyệt và trả hồ sơ về HR để bổ sung.</p> : null}
              {preview.data ? (
                <div className="space-y-3">
                  <p className="text-sm">Mức trong báo cáo: <strong>{sanctionLabel(preview.data.sanction_type)}</strong></p>
                  <details className="rounded-lg border border-rule p-3 text-sm"><summary className="cursor-pointer font-medium">Xem dự thảo quyết định</summary><p className="mt-3 whitespace-pre-wrap">{preview.data.decision_draft}</p></details>
                  <div className="space-y-1.5"><Label htmlFor="manager-code">Mã quyết định</Label><Input id="manager-code" maxLength={100} value={code} disabled={submit.isPending} onChange={(event) => { setCode(event.target.value); setConfirm(null); }} /></div>
                  <div className="space-y-1.5"><Label htmlFor="manager-summary">Tóm tắt quyết định</Label><Textarea id="manager-summary" rows={3} maxLength={8000} value={summary} disabled={submit.isPending} onChange={(event) => { setSummary(event.target.value); setConfirm(null); }} /></div>
                  <div className="space-y-1.5"><Label htmlFor="manager-basis">Căn cứ ban hành (không bắt buộc)</Label><Textarea id="manager-basis" rows={2} maxLength={8000} value={basis} disabled={submit.isPending} onChange={(event) => { setBasis(event.target.value); setConfirm(null); }} /></div>
                </div>
              ) : null}
              <div className="space-y-1.5"><Label htmlFor="manager-comment">Lý do không duyệt / yêu cầu HR xử lý lại</Label><Textarea id="manager-comment" className="shadow-none focus-visible:border-rule focus-visible:outline-none focus-visible:ring-0" rows={3} maxLength={4000} value={comment} disabled={submit.isPending} onChange={(event) => { setComment(event.target.value); setConfirm(null); }} placeholder="Bắt buộc nhập khi không duyệt" /></div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={!canApprove || submit.isPending} onClick={() => ask("APPROVE")}>Duyệt</Button>
                <Button variant="destructive" disabled={!comment.trim() || submit.isPending} onClick={() => ask("REJECT")}>Không duyệt</Button>
              </div>
              <p className="text-xs text-ink-3">Duyệt sẽ ban hành quyết định theo mức đã lưu và cần mã, tóm tắt quyết định. Không duyệt sẽ trả hồ sơ về HR kèm lý do.</p>
              {confirm ? (
                <div className="space-y-3 rounded-lg border border-son-line bg-son-tint p-3 text-sm">
                  <p>{confirm === "APPROVE" ? `Duyệt và ban hành quyết định ${code.trim()} theo mức ${sanctionLabel(preview.data?.sanction_type)}?` : "Không duyệt và trả hồ sơ về HR?"}</p>
                  {confirm === "REJECT" ? <p className="whitespace-pre-wrap">{comment.trim()}</p> : null}
                  <div className="flex gap-2">
                    <Button variant="secondary" disabled={submit.isPending} onClick={() => setConfirm(null)}>Hủy</Button>
                    <Button disabled={submit.isPending || (confirm === "APPROVE" ? !canApprove : !comment.trim())} onClick={() => submit.mutate(confirm)}>{submit.isPending ? "Đang ghi…" : confirm === "APPROVE" ? "Xác nhận duyệt" : "Xác nhận không duyệt"}</Button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
      <Sheet open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }} title="Đoạn căn cứ">{selected ? <EvidenceDetail card={selected} /> : null}</Sheet>
    </div>
  );
}
