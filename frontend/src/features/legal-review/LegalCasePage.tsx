import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { DraftList } from "@/features/decision/DraftList";
import { riskLabel, sanctionLabel } from "@/lib/labels";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { api, errorMessage } from "@/services/api";
import type { CitationView } from "@/types/api";

export function LegalCasePage() {
  const { caseId = "" } = useParams();
  const queryClient = useQueryClient();
  const pack = useQuery({ queryKey: ["review-pack", caseId], queryFn: () => api.reviewPack(caseId), enabled: Boolean(caseId) });
  const [decision, setDecision] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
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

  const answer = pack.data.answer;
  const locked = pack.data.status !== "PENDING_LEGAL";

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <Link className="text-sm text-[#009EC1] underline" to="/legal-review">
          Hàng chờ
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-[#073642]">{pack.data.case_code}</h1>
        <p className="text-sm text-[#4d7380]">
          {pack.data.employee_name} · {pack.data.status}. Pháp chế không sửa tình tiết, mức hay trích dẫn.
        </p>
        {pack.data.description ? <p className="mt-2 whitespace-pre-wrap text-sm text-[#355861]">{pack.data.description}</p> : null}
        {answerRisk(pack.data.answer.risk_level) ? (
          <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            Cần thận trọng. Rủi ro {pack.data.answer.risk_level}. Rủi ro không tự quyết mức kỷ luật.
          </p>
        ) : null}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Đề xuất đã lưu</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>Mức trên báo cáo: {answer.sanction_type ? sanctionLabel(answer.sanction_type) : "Chưa chốt mức"}</p>
          <p>Rủi ro: {riskLabel(answer.risk_level)}</p>
          <p className="whitespace-pre-wrap">{answer.message}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Căn cứ</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Layer title="Căn cứ pháp lý" items={answer.legal_basis} />
          <Layer title="Nội quy" items={answer.internal_rule} />
          <Layer title="Tiền lệ — không tự quyết mức" items={answer.precedent} />
          <Layer title="Rủi ro thanh tra — không phải mức kỷ luật người lao động" items={answer.inspection_risk} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Biên bản và phiếu</CardTitle>
        </CardHeader>
        <CardContent>
          <DraftList drafts={answer.drafts ?? []} />
        </CardContent>
      </Card>
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
    </div>
  );
}

function answerRisk(level: string | null): boolean {
  return level === "HIGH" || level === "CRITICAL";
}

function Layer({ title, items }: { title: string; items: CitationView[] }) {
  return (
    <section>
      <h3 className="text-sm font-semibold text-[#073642]">{title}</h3>
      {items.length === 0 ? <p className="text-sm text-[#4d7380]">Không có đoạn.</p> : null}
      <ul className="mt-1 space-y-2">
        {items.map((item) => (
          <li key={item.citation_id} className="rounded-lg border border-[#d5e8ed] px-3 py-2 text-sm">
            <p className="font-medium">{item.policy_name || item.policy_code}</p>
            <p className="text-xs text-[#4d7380]">
              {[item.article && `Điều ${item.article}`, item.clause && `Khoản ${item.clause}`, item.point && `Điểm ${item.point}`]
                .filter(Boolean)
                .join(" · ") || "Không có vị trí điều khoản"}
            </p>
            <p className="mt-1 whitespace-pre-wrap">“{item.quote}”</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
