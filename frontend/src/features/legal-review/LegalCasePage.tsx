import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { DocumentSections, EvidenceDetail, sectionLinks } from "@/features/assessment/form/Sections";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { statusLabel } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";
import type { ReviewView } from "@/types/api";
import type { EvidenceCard } from "@/types/assessment";

export function LegalCasePage() {
  const { caseId = "" } = useParams();
  return <LegalCase key={caseId} caseId={caseId} />;
}

function LegalCase({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const pack = useQuery({ queryKey: ["review-pack", caseId], queryFn: () => api.reviewPack(caseId), enabled: Boolean(caseId) });
  const [decision, setDecision] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<ReviewView | null>(null);
  const [selected, setSelected] = useState<EvidenceCard | null>(null);
  const submit = useMutation({
    mutationFn: () => api.submitReview(caseId, decision, comment, idempotencyKey(`review:${caseId}`)),
    onSuccess: (view) => {
      clearIdempotency(`review:${caseId}`);
      setDone(view);
      setError(null);
      queryClient.setQueryData<Awaited<ReturnType<typeof api.reviewPack>>>(["review-pack", caseId], (current) => current ? {
        ...current, status: view.case_status, answer: { ...current.answer, case_status: view.case_status },
      } : current);
      void queryClient.invalidateQueries({ queryKey: ["legal-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["review-pack", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["manager-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  if (pack.isLoading) return <p className="text-sm">Đang tải gói duyệt…</p>;
  if (!pack.data) {
    return (
      <div className="space-y-2 text-sm text-son-dark">
        <p>{errorMessage(pack.error)}</p>
        <Link className="text-son-dark underline" to="/legal-review">
          Về hàng chờ
        </Link>
      </div>
    );
  }

  const assessment = pack.data.assessment;
  const caseStatus = done?.case_status ?? pack.data.status;
  const locked = caseStatus !== "PENDING_LEGAL";
  const completedMessage = done
    ? done.decision === "APPROVE"
      ? { title: "Đã gửi kết luận thành công", description: "Hồ sơ đã chuyển sang hàng chờ của quản lý để duyệt lần cuối. HR và quản lý đã được thông báo." }
      : { title: "Đã gửi yêu cầu xử lý lại thành công", description: "Hồ sơ đã trả về HR kèm nhận xét của bạn. HR đã được thông báo." }
    : caseStatus === "APPROVED"
      ? { title: "Hồ sơ đã chuyển sang quản lý", description: "Kết luận pháp chế đã được ghi nhận. Hồ sơ đang chờ quản lý duyệt lần cuối." }
      : caseStatus === "REJECTED"
        ? { title: "Hồ sơ đã trả về HR", description: "Hồ sơ đang chờ HR bổ sung và xử lý lại." }
        : { title: "Hồ sơ đã hoàn tất bước pháp chế", description: `Trạng thái hiện tại: ${statusLabel(caseStatus)}.` };

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <Link className="text-sm text-son-dark underline" to="/legal-review">
          Hàng chờ
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-ink">{pack.data.case_code}</h1>
        <p className="text-sm text-ink-3">
          {pack.data.employee_name} · {caseStatus === "APPROVED" ? "Chờ quản lý duyệt cuối" : statusLabel(caseStatus)}. Pháp chế không sửa tình tiết, mức hay trích dẫn.
        </p>
        {answerRisk(pack.data.answer.risk_level) ? (
          <p className="mt-3 rounded-lg border border-son-line bg-son-tint px-3 py-2 text-sm text-son-dark">
            Cần thận trọng. Rủi ro {pack.data.answer.risk_level}. Rủi ro không tự quyết mức kỷ luật.
          </p>
        ) : null}
      </div>

      {assessment ? (
        <div className="grid items-start gap-4 lg:grid-cols-[13rem_minmax(0,1fr)]">
          <nav className="flex gap-2 overflow-x-auto lg:sticky lg:top-4 lg:block lg:space-y-1" aria-label="Mục biên bản">
            {sectionLinks().map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="block shrink-0 rounded-md px-3 py-1.5 text-sm text-ink hover:bg-paper-2"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <DocumentSections
            view={assessment}
            sections={assessment.sections}
            editing={null}
            saving={false}
            onBegin={() => undefined}
            onCancel={() => undefined}
            onSave={() => undefined}
            onCase={() => undefined}
            onEmployee={() => undefined}
            onIncident={() => undefined}
            onFacts={() => undefined}
            onRationale={() => undefined}
            onOpen={setSelected}
          />
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Biên bản</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-ink-3">
            Hồ sơ này chưa có biên bản đã xác nhận. Vui lòng yêu cầu HR lập và xác nhận biên bản trước khi pháp chế duyệt.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Quyết định của pháp chế</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {locked ? (
            <div className="space-y-4">
              <div role="status" aria-live="polite" className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
                <div>
                  <h3 className="font-semibold">{completedMessage.title}</h3>
                  <p className="mt-1 text-sm leading-6">{completedMessage.description}</p>
                </div>
              </div>
              {done?.comment ? <div className="text-sm"><p className="font-medium text-ink">Nhận xét đã gửi</p><p className="mt-1 whitespace-pre-wrap text-ink-2">{done.comment}</p></div> : null}
              <div className="flex flex-wrap gap-2">
                <Button asChild><Link to="/legal-review">Về hàng chờ pháp chế</Link></Button>
                <Button asChild variant="secondary"><Link to="/dashboard">Bảng điều khiển</Link></Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3" aria-busy={submit.isPending}>
              {error ? <p role="alert" className="text-sm text-son-dark">{error}</p> : null}
              <fieldset className="space-y-2 text-sm" disabled={submit.isPending}>
                <legend className="font-medium">Kết luận của pháp chế</legend>
                <label className="flex gap-2">
                  <input type="radio" checked={decision === "APPROVE"} onChange={() => setDecision("APPROVE")} /> Duyệt và chuyển quản lý
                </label>
                <label className="flex gap-2">
                  <input type="radio" checked={decision === "REJECT"} onChange={() => setDecision("REJECT")} /> Yêu cầu HR xử lý lại
                </label>
              </fieldset>
              <Textarea
                rows={4}
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder={decision === "REJECT" ? "Việc HR cần làm lại" : "Nhận xét, có thể để trống khi duyệt"}
                disabled={submit.isPending}
              />
              <Button disabled={submit.isPending || (decision === "REJECT" && !comment.trim())} onClick={() => submit.mutate()}>
                {submit.isPending ? <><LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />Đang gửi kết luận…</> : "Gửi kết luận"}
              </Button>
              <p className="text-xs text-ink-3">
                Duyệt chuyển hồ sơ sang quản lý. Yêu cầu xử lý lại trả hồ sơ cho HR và bắt buộc có ghi chú.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
      <Sheet open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }} title="Đoạn căn cứ">
        {selected ? <EvidenceDetail card={selected} /> : null}
      </Sheet>
    </div>
  );
}

function answerRisk(level: string | null): boolean {
  return level === "HIGH" || level === "CRITICAL";
}
