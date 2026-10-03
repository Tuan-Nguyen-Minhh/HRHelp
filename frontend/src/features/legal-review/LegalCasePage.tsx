import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Sheet } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { DocumentSections, EvidenceDetail, sectionLinks } from "@/features/assessment/form/Sections";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { api, errorMessage } from "@/services/api";
import type { EvidenceCard } from "@/types/assessment";

export function LegalCasePage() {
  const { caseId = "" } = useParams();
  const queryClient = useQueryClient();
  const pack = useQuery({ queryKey: ["review-pack", caseId], queryFn: () => api.reviewPack(caseId), enabled: Boolean(caseId) });
  const [decision, setDecision] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [selected, setSelected] = useState<EvidenceCard | null>(null);
  const submit = useMutation({
    mutationFn: () => api.submitReview(caseId, decision, comment, idempotencyKey(`review:${caseId}`)),
    onSuccess: (view) => {
      clearIdempotency(`review:${caseId}`);
      setDone(view.case_status);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["legal-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["review-pack", caseId] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  if (pack.isLoading) return <p className="text-sm">Đang tải gói duyệt…</p>;
  if (pack.isError || !pack.data) {
    return (
      <div className="space-y-2 text-sm text-red-800">
        <p>{errorMessage(pack.error)}</p>
        <Link className="text-[#009EC1] underline" to="/legal-review">
          Về hàng chờ
        </Link>
      </div>
    );
  }

  const assessment = pack.data.assessment;
  const locked = pack.data.status !== "PENDING_LEGAL";

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <Link className="text-sm text-[#009EC1] underline" to="/legal-review">
          Hàng chờ
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-[#073642]">{pack.data.case_code}</h1>
        <p className="text-sm text-[#4d7380]">
          {pack.data.employee_name} · {pack.data.status}. Pháp chế không sửa tình tiết, mức hay trích dẫn.
        </p>
        {answerRisk(pack.data.answer.risk_level) ? (
          <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
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
                className="block shrink-0 rounded-md px-3 py-1.5 text-sm text-[#073642] hover:bg-[#e7f6f9]"
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
          <CardContent className="text-sm text-[#4d7380]">
            Hồ sơ này chưa có biên bản đã xác nhận. Vui lòng yêu cầu HR lập và xác nhận biên bản trước khi pháp chế duyệt.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Quyết định của pháp chế</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {done ? <p className="rounded-md bg-[#e7f6f9] px-3 py-2 text-sm">Hồ sơ chuyển sang {done}.</p> : null}
          {error ? <p className="text-sm text-red-800">{error}</p> : null}
          <fieldset className="space-y-2 text-sm" disabled={locked || submit.isPending}>
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
            disabled={locked}
          />
          <Button disabled={locked || submit.isPending || (decision === "REJECT" && !comment.trim())} onClick={() => submit.mutate()}>
            {submit.isPending ? "Đang ghi…" : "Gửi kết luận"}
          </Button>
          <p className="text-xs text-[#4d7380]">
            Duyệt chuyển hồ sơ sang quản lý. Yêu cầu xử lý lại trả hồ sơ cho HR và bắt buộc có ghi chú.
          </p>
          {locked ? <p className="text-xs text-[#4d7380]">Hồ sơ không còn ở hàng chờ nên không nhận thêm kết luận.</p> : null}
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
