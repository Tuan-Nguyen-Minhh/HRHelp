import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { FactItem } from "@/features/evidence/FactItem";
import { DraftList } from "@/features/decision/DraftList";
import { HOLD_LABEL, riskLabel, sanctionLabel } from "@/lib/labels";
import { visibleSanction } from "@/lib/workflow";
import { placeLabel } from "@/lib/utils";
import type { CitationView } from "@/types/api";

export function LegalReviewPage() {
  const { caseView, facts, answer } = useWorkspace();
  const ticket = answer?.ticket ?? null;
  const level = visibleSanction(answer);
  const queued = caseView.status === "PENDING_LEGAL" || ticket?.disposition === "SUBMIT";

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card className={queued ? "border-red-200" : ""}>
        <CardHeader>
          <CardTitle>Pháp chế</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="font-medium">{queued ? "Hồ sơ đang ở hàng chờ pháp chế." : "Hồ sơ chưa được đẩy sang pháp chế."}</p>
          <p>{ticket?.reason || "Chưa có lý do từ phiếu."}</p>
          {ticket?.hold_code ? <p className="text-xs text-neutral-500">{HOLD_LABEL[ticket.hold_code] ?? ticket.hold_code}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tình tiết</CardTitle>
        </CardHeader>
        <CardContent>
          {facts ? (
            <ul>
              {facts.facts.map((fact) => (
                <FactItem key={fact.fact_key} fact={fact} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-neutral-600">Chưa tải được tình tiết.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Căn cứ đã lưu</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Layer title="Luật và nghị định hướng dẫn" items={answer?.legal_basis ?? []} />
          <Layer title="Nội quy" items={answer?.internal_rule ?? []} />
          <Layer title="Tiền lệ — không phải mức kỷ luật" items={answer?.precedent ?? []} />
          <Layer title="Xử phạt hành chính — không phải mức kỷ luật của người lao động" items={answer?.inspection_risk ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Đánh giá đã lưu</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>Trạng thái hồ sơ: {answer?.case_status || caseView.status}</p>
          <p>
            Mức trình bày:{" "}
            {level
              ? `${sanctionLabel(level)} (${level})`
              : answer?.sanction_type === "TERMINATION"
                ? "Chấm dứt hợp đồng không được trình bày như mức kỷ luật"
                : "Chưa trình bày mức"}
          </p>
          <p>Rủi ro căn cứ: {answer ? `${riskLabel(answer.risk_level)} ${answer.risk_level ?? ""}`.trim() : "Chưa có"}</p>
          <p className="whitespace-pre-wrap">{answer?.rationale || "Chưa có lý do."}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bản thảo</CardTitle>
        </CardHeader>
        <CardContent>
          <DraftList drafts={answer?.drafts ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bước của pháp chế</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-[#355861]">
          <p>
            {queued
              ? "Hồ sơ đang chờ pháp chế. Duyệt hoặc từ chối nằm ở tài khoản pháp chế, không gửi từ màn hình của HR."
              : "Hồ sơ chưa vào hàng chờ pháp chế."}
          </p>
          <p>Pháp chế không sửa tình tiết, mức hay trích dẫn. HR không tự ban hành quyết định.</p>
        </CardContent>
      </Card>
    </div>
  );
}

function Layer({ title, items }: { title: string; items: CitationView[] }) {
  return (
    <section>
      <h3 className="text-sm font-medium">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-neutral-600">Không có đoạn.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.map((item) => (
            <li key={item.citation_id} className="rounded-md border border-neutral-200 px-3 py-2 text-sm">
              <p className="font-medium">{item.policy_name || item.policy_code}</p>
              <p className="text-xs text-neutral-500">{placeLabel(item.article, item.clause, item.point)}</p>
              <p className="mt-1 whitespace-pre-wrap">{item.quote}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
