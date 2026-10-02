import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FAMILY_LABEL } from "@/lib/labels";
import { clip, formatDate, placeLabel } from "@/lib/utils";
import type {
  AssessmentForm,
  AssessmentSections,
  CaseInformation,
  ConfirmedFact,
  EmployeeInformation,
  EvidenceCard,
  FactStatus,
  FieldSource,
  IncidentSummary,
  ResultStatus,
} from "@/types/assessment";

export type EditKey = "case" | "employee" | "incident" | "facts" | "rationale";

const NAV = [
  ["case", "I. Vụ việc"],
  ["employee", "II. Người lao động"],
  ["incident", "III. Diễn biến"],
  ["facts", "IV. Tình tiết"],
  ["evidence", "V. Căn cứ"],
  ["assessment", "VI. Đánh giá"],
  ["result", "VII. Kết quả"],
  ["handling", "VIII. Đề xuất"],
  ["risk", "IX. Rủi ro"],
  ["steps", "X. Bước tiếp"],
  ["citations", "XI. Trích dẫn"],
] as const;

const FACT_STATUS: Record<FactStatus, string> = {
  CONFIRMED: "Đã xác nhận",
  MISSING: "Còn thiếu",
  UNCERTAIN: "Chưa chắc",
  HR_EDITED: "HR đã sửa",
};

const RESULT_LABEL: Record<ResultStatus, string> = {
  SUPPORTED: "Đủ căn cứ tham khảo",
  PARTIALLY_SUPPORTED: "Đủ một phần",
  INSUFFICIENT_EVIDENCE: "Chưa đủ căn cứ",
  CONFLICTING_EVIDENCE: "Căn cứ mâu thuẫn",
  NEED_LEGAL_REVIEW: "Cần pháp chế xem",
};

const LAYER_LABEL: Record<string, string> = {
  legal_basis: "Luật và nghị định",
  internal_rule: "Nội quy",
  precedent: "Tiền lệ",
  inspection_risk: "Cảnh báo thanh tra",
};

const EMPLOYEE_FIELDS: { key: keyof EmployeeInformation; label: string }[] = [
  { key: "employee_code", label: "Mã nhân viên" },
  { key: "employee_name", label: "Họ và tên" },
  { key: "department", label: "Đơn vị" },
  { key: "position", label: "Vị trí" },
  { key: "contract_type", label: "Loại hợp đồng" },
  { key: "employment_status", label: "Tình trạng làm việc" },
];

export function sectionLinks(): { id: string; label: string }[] {
  return NAV.map(([id, label]) => ({ id, label }));
}

export function DocumentSections({
  view,
  sections,
  editing,
  saving,
  onBegin,
  onCancel,
  onSave,
  onCase,
  onEmployee,
  onIncident,
  onFacts,
  onRationale,
  onOpen,
}: {
  view: AssessmentForm;
  sections: AssessmentSections;
  editing: EditKey | null;
  saving: boolean;
  onBegin: (key: EditKey) => void;
  onCancel: () => void;
  onSave: () => void;
  onCase: (value: CaseInformation) => void;
  onEmployee: (value: EmployeeInformation) => void;
  onIncident: (value: IncidentSummary) => void;
  onFacts: (value: ConfirmedFact[]) => void;
  onRationale: (value: string) => void;
  onOpen: (card: EvidenceCard) => void;
}) {
  const canEdit = view.permissions.can_edit;
  const blocked = sections.confirmed_facts.filter((item) => item.blocking);
  return (
    <div className="space-y-4">
      <Section
        id="case"
        title="I. Thông tin vụ việc"
        editing={editing === "case"}
        canEdit={canEdit}
        saving={saving}
        onEdit={() => onBegin("case")}
        onCancel={onCancel}
        onSave={onSave}
        extra={<Origin source={view.sources["case_information.description"]} />}
      >
        <CaseBlock info={sections.case_information} editing={editing === "case"} onChange={onCase} />
      </Section>

      <Section
        id="employee"
        title="II. Người lao động"
        editing={editing === "employee"}
        canEdit={canEdit}
        saving={saving}
        onEdit={() => onBegin("employee")}
        onCancel={onCancel}
        onSave={onSave}
        extra={<Origin source={view.sources["employee_information.employee_name"]} />}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {EMPLOYEE_FIELDS.map((field) => (
            <label key={field.key} className="block text-sm">
              <span className="text-xs text-[#4d7380]">{field.label}</span>
              {editing === "employee" ? (
                <Input
                  className="mt-1"
                  value={sections.employee_information[field.key] ?? ""}
                  onChange={(event) =>
                    onEmployee({ ...sections.employee_information, [field.key]: event.target.value || null })
                  }
                />
              ) : (
                <p className="mt-1 font-medium text-[#073642]">{sections.employee_information[field.key] || "—"}</p>
              )}
            </label>
          ))}
        </div>
      </Section>

      <Section
        id="incident"
        title="III. Nội dung và diễn biến"
        editing={editing === "incident"}
        canEdit={canEdit}
        saving={saving}
        onEdit={() => onBegin("incident")}
        onCancel={onCancel}
        onSave={onSave}
        extra={<Origin source={view.sources["incident_summary.narrative"]} />}
      >
        <Narrative
          incident={sections.incident_summary}
          editing={editing === "incident"}
          onChange={onIncident}
        />
      </Section>

      <Section
        id="facts"
        title="IV. Tình tiết đã xác nhận"
        editing={editing === "facts"}
        canEdit={canEdit}
        saving={saving}
        onEdit={() => onBegin("facts")}
        onCancel={onCancel}
        onSave={onSave}
      >
        {blocked.length ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
            Hồ sơ vẫn còn {blocked.length} thông tin bắt buộc cần bổ sung.
          </p>
        ) : null}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-[#4d7380]">
              <tr className="border-b border-[#d5e8ed]">
                <th className="py-2 pr-3 font-medium">Tình tiết</th>
                <th className="py-2 pr-3 font-medium">Giá trị</th>
                <th className="py-2 font-medium">Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {sections.confirmed_facts.map((fact) => (
                <tr key={fact.fact_key} className="border-b border-[#e7f3f6]">
                  <td className="py-2 pr-3 text-[#073642]">{fact.label}</td>
                  <td className="py-2 pr-3">
                    {editing === "facts" ? (
                      <Input
                        value={fact.value ?? ""}
                        aria-label={fact.label}
                        onChange={(event) =>
                          onFacts(
                            sections.confirmed_facts.map((item) =>
                              item.fact_key === fact.fact_key ? { ...item, value: event.target.value || null } : item,
                            ),
                          )
                        }
                      />
                    ) : (
                      <span className="text-[#073642]">{fact.value || "—"}</span>
                    )}
                  </td>
                  <td className="py-2">
                    <FactBadge fact={fact} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sections.confirmed_facts.length === 0 ? <p className="text-sm text-[#4d7380]">Chưa có tình tiết trên biên bản.</p> : null}
      </Section>

      <Section id="evidence" title="V. Căn cứ và tài liệu">
        {sections.evidence_reviewed.length === 0 ? (
          <p className="text-sm text-[#4d7380]">Chưa có đoạn căn cứ trên báo cáo đã lưu.</p>
        ) : (
          <div className="grid gap-3">
            {sections.evidence_reviewed.map((card) => (
              <article key={card.evidence_id} className="rounded-lg border border-[#d5e8ed] bg-[#f4fafb] px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="neutral">Căn cứ đã truy xuất</Badge>
                  <Badge tone="info">{card.policy_type || LAYER_LABEL[card.layer] || card.layer}</Badge>
                </div>
                <h3 className="mt-2 text-sm font-semibold text-[#073642]">{card.title}</h3>
                <p className="text-xs text-[#4d7380]">{card.citation_label}</p>
                <blockquote className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#073642]">“{clip(card.quote, 360)}”</blockquote>
                <Button className="mt-2" size="sm" variant="secondary" onClick={() => onOpen(card)}>
                  Xem đoạn
                </Button>
              </article>
            ))}
          </div>
        )}
      </Section>

      <Section id="assessment" title="VI. Đánh giá và đối chiếu">
        <Read label="Nhận định" text={sections.assessment.narrative || "—"} />
        <Bullet label="Căn cứ áp dụng" items={sections.assessment.applied_basis} />
        <Bullet label="Điểm phù hợp" items={sections.assessment.matches} />
        <Bullet label="Điểm chưa đủ" items={sections.assessment.gaps} />
        <Bullet label="Mâu thuẫn" items={sections.assessment.conflicts} />
      </Section>

      <Section id="result" title="VII. Kết quả đánh giá">
        <Badge tone={resultTone(sections.assessment_result.status)}>{RESULT_LABEL[sections.assessment_result.status]}</Badge>
        <p className="text-xs text-[#4d7380]">{sections.assessment_result.status}</p>
        <p className="text-sm leading-6 text-[#073642]">{sections.assessment_result.summary}</p>
      </Section>

      <Section
        id="handling"
        title="VIII. Đề xuất hướng xử lý"
        editing={editing === "rationale"}
        canEdit={canEdit}
        saving={saving}
        onEdit={() => onBegin("rationale")}
        onCancel={onCancel}
        onSave={onSave}
        extra={<Origin source={view.sources["handling_proposal.rationale"]} />}
      >
        <p className="text-sm text-[#4d7380]">Đây là phương án tham khảo. Biên bản không chốt hình thức kỷ luật.</p>
        <OptionList title="Phương án tham khảo" items={sections.handling_proposal.proposed_actions} />
        <OptionList title="Phương án khác" items={sections.handling_proposal.alternatives} />
        {sections.handling_proposal.proposed_actions.length === 0 ? (
          <p className="text-sm text-[#073642]">Chưa có phương án tham khảo.</p>
        ) : null}
        {sections.handling_proposal.requires_legal_review ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">Cần pháp chế xem xét trước khi coi đây là hướng xử lý.</p>
        ) : null}
        <label className="block text-sm">
          <span className="text-xs text-[#4d7380]">Lý do</span>
          {editing === "rationale" ? (
            <Textarea className="mt-1" value={sections.handling_proposal.rationale} onChange={(event) => onRationale(event.target.value)} />
          ) : (
            <p className="mt-1 whitespace-pre-wrap leading-6 text-[#073642]">{sections.handling_proposal.rationale || "—"}</p>
          )}
        </label>
      </Section>

      <Section id="risk" title="IX. Rủi ro và khoảng trống chứng cứ">
        <p className="text-sm text-[#073642]">
          Mức rủi ro căn cứ: <span className="font-semibold">{sections.risk_and_gaps.risk_level || "Chưa có"}</span>
        </p>
        <Bullet label="Khoảng trống" items={sections.risk_and_gaps.evidence_gaps} />
        <Bullet label="Mâu thuẫn" items={sections.risk_and_gaps.conflicts} />
        {sections.risk_and_gaps.missing_information.length ? (
          <ul className="space-y-1 text-sm text-[#073642]">
            {sections.risk_and_gaps.missing_information.map((item) => (
              <li key={item.fact_key}>
                {item.blocking ? "Bắt buộc: " : "Không chặn xác nhận: "}
                {item.reason}
              </li>
            ))}
          </ul>
        ) : null}
        {sections.risk_and_gaps.legal_review_required ? <p className="text-sm text-[#4d7380]">Hồ sơ vẫn cần pháp chế xem khi phiếu được gửi.</p> : null}
      </Section>

      <Section id="steps" title="X. Các bước tiếp theo">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-[#073642]">
          {sections.next_steps.map((step) => (
            <li key={step.order}>{step.text}</li>
          ))}
        </ol>
      </Section>

      <Section id="citations" title="XI. Danh mục căn cứ trích dẫn">
        {sections.citations.length === 0 ? (
          <p className="text-sm text-[#4d7380]">Chưa có trích dẫn.</p>
        ) : (
          <ol className="space-y-3">
            {sections.citations.map((card, index) => (
              <li key={`${card.evidence_id}-${index}`} className="text-sm">
                <p className="font-medium text-[#073642]">
                  [{index + 1}] {card.title}
                </p>
                <p className="text-[#4d7380]">{card.citation_label}</p>
                <p className="text-xs text-[#4d7380]">Đoạn: {card.chunk_id || "Không có mã đoạn"}</p>
                <Button className="mt-1" size="sm" variant="secondary" onClick={() => onOpen(card)}>
                  Xem đoạn
                </Button>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </div>
  );
}

export function EvidenceDetail({ card }: { card: EvidenceCard }) {
  return (
    <div className="space-y-3 text-sm">
      <Badge tone="neutral">Căn cứ đã truy xuất</Badge>
      <h3 className="text-base font-semibold text-[#073642]">{card.title}</h3>
      <dl className="space-y-2">
        <Row label="Nhãn" value={card.citation_label} />
        <Row label="Loại" value={card.policy_type || "—"} />
        <Row label="Lớp" value={LAYER_LABEL[card.layer] || card.layer} />
        <Row label="Vị trí" value={placeLabel(card.article, card.clause, card.point) || "—"} />
        <Row label="Mã đoạn" value={card.chunk_id || "Không có"} />
        <Row label="Mã văn bản" value={card.document_id || "Đoạn đã lưu không có mã văn bản riêng."} />
      </dl>
      <blockquote className="whitespace-pre-wrap rounded-md border border-[#d5e8ed] bg-[#f4fafb] px-3 py-3 leading-6 text-[#073642]">
        {card.quote || "Đoạn không có nội dung trích."}
      </blockquote>
    </div>
  );
}

function CaseBlock({
  info,
  editing,
  onChange,
}: {
  info: CaseInformation;
  editing: boolean;
  onChange: (value: CaseInformation) => void;
}) {
  return (
    <div className="grid gap-3">
      <Read label="Mã vụ việc" text={info.case_code} />
      <div>
        <p className="text-xs text-[#4d7380]">Trạng thái hồ sơ</p>
        <div className="mt-1">
          <StatusBadge status={info.case_status} />
        </div>
      </div>
      <label className="block text-sm">
        <span className="text-xs text-[#4d7380]">Loại vi phạm</span>
        {editing ? (
          <select
            className="mt-1 flex h-9 w-full rounded-md border border-[#d5e8ed] bg-white px-3 text-sm text-[#073642]"
            value={info.violation_type ?? ""}
            onChange={(event) => onChange({ ...info, violation_type: event.target.value || null })}
          >
            <option value="">Chưa phân loại</option>
            {Object.entries(FAMILY_LABEL).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
        ) : (
          <p className="mt-1 font-medium text-[#073642]">{info.violation_type ? FAMILY_LABEL[info.violation_type] || info.violation_type : "—"}</p>
        )}
      </label>
      <label className="block text-sm">
        <span className="text-xs text-[#4d7380]">Ngày xảy ra</span>
        {editing ? (
          <Input
            className="mt-1"
            type="date"
            value={info.incident_date ?? ""}
            onChange={(event) => onChange({ ...info, incident_date: event.target.value || null })}
          />
        ) : (
          <p className="mt-1 font-medium text-[#073642]">{formatDate(info.incident_date)}</p>
        )}
      </label>
      <label className="block text-sm">
        <span className="text-xs text-[#4d7380]">Mô tả</span>
        {editing ? (
          <Textarea className="mt-1" value={info.description} onChange={(event) => onChange({ ...info, description: event.target.value })} />
        ) : (
          <p className="mt-1 whitespace-pre-wrap leading-6 text-[#073642]">{info.description || "—"}</p>
        )}
      </label>
    </div>
  );
}

function Narrative({
  incident,
  editing,
  onChange,
}: {
  incident: IncidentSummary;
  editing: boolean;
  onChange: (value: IncidentSummary) => void;
}) {
  const fields: { key: keyof IncidentSummary; label: string }[] = [
    { key: "narrative", label: "Diễn biến vụ việc" },
    { key: "timeline", label: "Dòng thời gian" },
    { key: "employee_statement", label: "Ý kiến người lao động" },
    { key: "hr_description", label: "Mô tả của HR" },
  ];
  return (
    <div className="space-y-3">
      {fields.map((field) => (
        <label key={field.key} className="block text-sm">
          <span className="text-xs text-[#4d7380]">{field.label}</span>
          {editing ? (
            <Textarea className="mt-1" value={incident[field.key]} onChange={(event) => onChange({ ...incident, [field.key]: event.target.value })} />
          ) : (
            <p className="mt-1 whitespace-pre-wrap leading-6 text-[#073642]">{incident[field.key] || "—"}</p>
          )}
        </label>
      ))}
    </div>
  );
}

function Section({
  id,
  title,
  children,
  editing = false,
  canEdit = false,
  saving = false,
  extra,
  onEdit,
  onCancel,
  onSave,
}: {
  id: string;
  title: string;
  children: ReactNode;
  editing?: boolean;
  canEdit?: boolean;
  saving?: boolean;
  extra?: ReactNode;
  onEdit?: () => void;
  onCancel?: () => void;
  onSave?: () => void;
}) {
  return (
    <section id={id} className="scroll-mt-4 rounded-xl border border-[#d5e8ed] bg-white">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[#d5e8ed] px-4 py-3">
        <h2 className="text-sm font-semibold tracking-wide text-[#073642]">{title}</h2>
        <div className="flex items-center gap-2">
          {extra}
          {canEdit && onEdit ? (
            editing ? (
              <>
                <Button size="sm" variant="secondary" disabled={saving} onClick={onCancel}>
                  Hủy
                </Button>
                <Button size="sm" disabled={saving} onClick={onSave}>
                  {saving ? "Đang lưu…" : "Lưu"}
                </Button>
              </>
            ) : (
              <Button size="sm" variant="secondary" onClick={onEdit}>
                Sửa
              </Button>
            )
          ) : null}
        </div>
      </header>
      <div className="space-y-3 px-4 py-4">{children}</div>
    </section>
  );
}

function Origin({ source }: { source?: FieldSource }) {
  if (source === "HR") return <Badge tone="info">HR đã sửa</Badge>;
  if (source === "CONFIRMED") return <Badge tone="success">Đã xác nhận</Badge>;
  return <Badge tone="neutral">AI đề xuất</Badge>;
}

function FactBadge({ fact }: { fact: ConfirmedFact }) {
  const tone = fact.status === "CONFIRMED" ? "success" : fact.status === "HR_EDITED" ? "info" : fact.blocking ? "warning" : "neutral";
  return <Badge tone={tone}>{FACT_STATUS[fact.status]}</Badge>;
}

function resultTone(status: ResultStatus): "success" | "warning" | "danger" | "info" {
  if (status === "SUPPORTED") return "success";
  if (status === "CONFLICTING_EVIDENCE") return "danger";
  if (status === "NEED_LEGAL_REVIEW") return "info";
  return "warning";
}

function Read({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-xs text-[#4d7380]">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#073642]">{text}</p>
    </div>
  );
}

function Bullet({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs text-[#4d7380]">{label}</p>
      {items.length ? (
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-[#073642]">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm text-[#073642]">—</p>
      )}
    </div>
  );
}

function OptionList({ title, items }: { title: string; items: { code: string; label: string }[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs text-[#4d7380]">{title}</p>
      <ul className="mt-1 space-y-2">
        {items.map((item) => (
          <li key={item.code} className="flex items-center gap-3 rounded-md border border-[#d5e8ed] px-3 py-2 text-sm">
            <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-[#009EC1]" aria-hidden="true" />
            <span className="font-medium text-[#073642]">{item.label}</span>
            <span className="text-xs text-[#4d7380]">{item.code}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-[#4d7380]">{label}</dt>
      <dd className="text-[#073642]">{value}</dd>
    </div>
  );
}
