import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { clip, cn, placeLabel } from "@/lib/utils";
import type {
  AssessmentForm,
  AssessmentSections,
  CaseInformation,
  ConfirmedFact,
  EmployeeInformation,
  EvidenceCard,
  IncidentSummary,
} from "@/types/assessment";

export type EditKey = "case" | "employee" | "incident" | "facts" | "rationale" | "all";

const NAV = [
  ["minutes", "Biên bản"],
  ["participants", "Thành phần"],
  ["content", "Nội dung"],
  ["signatures", "Chữ ký"],
  ["evidence", "Căn cứ"],
] as const;

const LAYER_LABEL: Record<string, string> = {
  legal_basis: "Luật và nghị định",
  internal_rule: "Nội quy",
  precedent: "Tiền lệ",
  inspection_risk: "Cảnh báo thanh tra",
};

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
  const isEditing = (key: EditKey) => editing === key || editing === "all";
  const profile = view.metadata.minutes_profile;
  const employee = sections.employee_information;
  const incident = sections.incident_summary;
  const info = sections.case_information;
  const caseMeta = caseDescriptionMeta(info.description);
  const employeePosition = employee.position || caseMeta.position || "";
  const employeeDepartment = employee.department || caseMeta.department || "";
  const incidentNarrative = incidentNarrativeValue(incident.narrative, info.description, sections.confirmed_facts);
  const resultSummary =
    cleanMinutesText(sections.assessment_result.summary) ||
    "HR xem xét trên thông tin đã thu thập và căn cứ áp dụng trước khi quyết định hình thức xử lý.";
  const proposed = sections.handling_proposal.proposed_actions.map((item) => item.label).join("; ") || "Chưa xác định do chưa đủ căn cứ.";
  const handlingText = isEditing("rationale") ? sections.handling_proposal.rationale : sections.handling_proposal.manual_text ?? proposed;
  const basisCards = orderedBasis(sections.citations.length ? sections.citations : sections.evidence_reviewed);
  const evidence = groupedBasis(basisCards);
  return (
    <div className="space-y-4">
      <section id="minutes" className="scroll-mt-4 rounded-xl border border-rule bg-white">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold tracking-wide text-ink">Biên bản xử lý vi phạm kỷ luật</h2>
            <p className="text-xs text-ink-3">Mẫu xem trước đúng cấu trúc Word. HR sửa các ô cần thiết rồi xuất DOCX.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canEdit ? (
              <>
                {editing ? (
                  <>
                    <Button size="sm" variant="secondary" disabled={saving} onClick={onCancel}>
                      Hủy
                    </Button>
                    <Button size="sm" disabled={saving} onClick={onSave}>
                      {saving ? "Đang lưu…" : "Lưu"}
                    </Button>
                  </>
                ) : (
                  <>
                    <Button size="sm" variant="secondary" onClick={() => onBegin("case")}>
                      Sửa vụ việc
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => onBegin("employee")}>
                      Sửa người lao động
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => onBegin("incident")}>
                      Sửa nội dung
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => onBegin("rationale")}>
                      Sửa xử phạt
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => onBegin("facts")}>
                      Sửa thông tin xác nhận
                    </Button>
                  </>
                )}
              </>
            ) : null}
          </div>
        </header>

        <div className="overflow-x-auto bg-paper-2 px-3 py-4">
          <article className="minutes-document mx-auto bg-white text-black shadow-sm">
            <div className="minutes-columns minutes-letterhead text-center">
              <div className="text-left">
                <p className="text-center font-bold">{profile.company_name.split(" – ")[0]}<br />– {profile.company_name.split(" – ")[1]}</p>
                <p className="text-center">Số: {profile.document_number}</p>
              </div>
              <div>
                <p className="font-bold">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>
                <p className="font-bold">Độc lập - Tự do - Hạnh phúc</p>
                <p className="mt-4">{profile.city}, ngày {dateParts(view.metadata.case_created_date ?? null)}</p>
              </div>
            </div>

            <h1 className="minutes-title">BIÊN BẢN XỬ LÝ VI PHẠM KỶ LUẬT</h1>

            <p>Biên bản xem xét xử lý vi phạm kỷ luật lao động đối với:</p>
            <div className="minutes-columns">
              <EditableLine
                label="Ông/Bà"
                value={employee.employee_name || ""}
                uppercase
                placeholder="........................................"
                editing={isEditing("employee")}
                onChange={(value) => onEmployee({ ...employee, employee_name: value || null })}
              />
              <EditableLine
                label="Mã số nhân viên"
                value={employee.employee_code || ""}
                uppercase
                placeholder="......................................"
                editing={isEditing("employee")}
                onChange={(value) => onEmployee({ ...employee, employee_code: value || null })}
              />
              <EditableLine
                label="Chức vụ/Chức danh"
                value={employeePosition}
                placeholder="....................."
                editing={isEditing("employee")}
                onChange={(value) => onEmployee({ ...employee, position: value || null })}
              />
              <EditableLine
                label="Phòng ban/Bộ phận"
                value={employeeDepartment}
                placeholder="................................."
                editing={isEditing("employee")}
                onChange={(value) => onEmployee({ ...employee, department: value || null })}
              />
            </div>
            <p>
              Vào lúc: ..... giờ ..... phút, ngày {dateParts(view.metadata.case_created_date ?? null)}
            </p>
            <p>Tại: {profile.meeting_location}</p>

            <h2 id="participants" className="minutes-section-title">
              I. THÀNH PHẦN THAM DỰ:
            </h2>
            <p>- Đại diện Ban lãnh đạo:</p>
            <div className="minutes-columns">
              <StaticLine label="Ông/Bà" value={profile.leadership_name} />
              <StaticLine label="Chức vụ" value={profile.leadership_position} />
            </div>
            <p>- Đại diện nhân sự công ty:</p>
            <StaticLine label="Ông/Bà" value={profile.hr_name} />
            <div className="minutes-columns">
              <StaticLine label="Chức vụ" value={profile.hr_position} />
              <StaticLine label="Phòng ban" value={profile.hr_department} />
            </div>
            <p>- Người bị lập biên bản:</p>
            <StaticLine label="Ông/Bà" value={employee.employee_name} />
            <div className="minutes-columns">
              <StaticLine label="Chức vụ" value={employeePosition} />
              <StaticLine label="Phòng ban" value={employeeDepartment} />
            </div>
            <p>- Người làm chứng:</p>
            <StaticLine label="Ông/Bà" />
            <div className="minutes-columns">
              <StaticLine label="Chức vụ" />
              <StaticLine label="Phòng ban" />
            </div>

            <h2 id="content" className="minutes-section-title">
              II. NỘI DUNG:
            </h2>
            <EditableArea
              label="- Diễn biến sự việc"
              value={incidentNarrative}
              placeholder="...................................................................................................................."
              editing={isEditing("incident") || editing === "case"}
              bulleted
              onChange={(value) => {
                if (editing === "case") onCase({ ...info, description: value });
                else onIncident({ ...incident, narrative: value });
              }}
            />
            <p>- Đối chiếu quy định:</p>
            {evidence.length ? <ul className="minutes-bullets">{evidence.map((item) => <li key={item}>{item}</li>)}</ul> : <WritingLines />}
            <StaticLine label="- Thiệt hại của công ty" />
            <EditableArea
              label="- Ý kiến của người bị lập biên bản"
              value={incident.employee_statement}
              placeholder="............................................................................................"
              editing={isEditing("incident")}
              onChange={(value) => onIncident({ ...incident, employee_statement: value })}
            />
            <p>- Kết quả đánh giá: {resultSummary}</p>
            <EditableArea
              label="- Hình thức xử phạt của Ban lãnh đạo"
              value={handlingText}
              placeholder="......................................................................................."
              editing={isEditing("rationale")}
              onChange={onRationale}
            />
            <p>- Ý kiến của người làm chứng và đại diện nhân sự công ty:</p>
            <WritingLines count={2} />

            <div id="signatures" className="mt-10 grid grid-cols-2 gap-x-8 gap-y-14 text-center">
              <Signature title="Đại diện Ban lãnh đạo" subtitle="(Ký tên, ghi họ tên và đóng dấu)" />
              <Signature title="Người bị lập biên bản" subtitle="(Ký tên, ghi rõ họ tên)" />
              <Signature title="Đại diện nhân sự công ty" subtitle="(Ký tên, ghi rõ họ tên)" />
              <Signature title="Người làm chứng" subtitle="(Ký tên, ghi rõ họ tên)" />
            </div>
          </article>
        </div>
      </section>

      {canEdit && isEditing("facts") ? (
        <Section id="manual-facts" title="Thông tin HR xác nhận">
          <p className="mb-3 text-sm text-ink-3">Sửa các thông tin đã xác minh. Thay đổi được lưu vào bản nháp trước khi xác nhận lại.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {sections.confirmed_facts.map((fact, index) => (
              <label key={fact.fact_key} className="space-y-1 text-sm">
                <span className="block font-medium">{fact.label}{fact.blocking ? " (cần bổ sung)" : ""}</span>
                <Input value={fact.value || ""} disabled={saving} onChange={(event) => onFacts(sections.confirmed_facts.map((item, position) => position === index ? { ...item, value: event.target.value || null } : item))} />
              </label>
            ))}
          </div>
        </Section>
      ) : null}
      <Section id="evidence" title="V. Căn cứ và tài liệu">
        {sections.evidence_reviewed.length === 0 ? (
          <p className="text-sm text-ink-3">Chưa có đoạn căn cứ trên báo cáo đã lưu.</p>
        ) : (
          <div className="grid gap-3">
            {sections.evidence_reviewed.map((card) => (
              <article key={card.evidence_id} className="rounded-lg border border-rule bg-paper-2 px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="neutral">Căn cứ đã truy xuất</Badge>
                  <Badge tone="info">{card.policy_type || LAYER_LABEL[card.layer] || card.layer}</Badge>
                </div>
                <h3 className="mt-2 text-sm font-semibold text-ink">{card.title}</h3>
                <p className="text-xs text-ink-3">{card.citation_label}</p>
                <blockquote className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink">“{clip(card.quote, 360)}”</blockquote>
                <Button className="mt-2" size="sm" variant="secondary" onClick={() => onOpen(card)}>
                  Xem đoạn
                </Button>
              </article>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

export function EvidenceDetail({ card }: { card: EvidenceCard }) {
  return (
    <div className="space-y-3 text-sm">
      <Badge tone="neutral">Căn cứ đã truy xuất</Badge>
      <h3 className="text-base font-semibold text-ink">{card.title}</h3>
      <dl className="space-y-2">
        <Row label="Nhãn" value={card.citation_label} />
        <Row label="Loại" value={card.policy_type || "—"} />
        <Row label="Lớp" value={LAYER_LABEL[card.layer] || card.layer} />
        <Row label="Vị trí" value={placeLabel(card.article, card.clause, card.point) || "—"} />
        <Row label="Mã văn bản" value={card.document_id || "Đoạn đã lưu không có mã văn bản riêng."} />
      </dl>
      <blockquote className="whitespace-pre-wrap rounded-md border border-rule bg-paper-2 px-3 py-3 leading-6 text-ink">
        {card.quote || "Đoạn không có nội dung trích."}
      </blockquote>
    </div>
  );
}

function EditableLine({
  label,
  value,
  placeholder,
  editing,
  uppercase = false,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  editing: boolean;
  uppercase?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="minutes-field">
      <span>{label}: </span>
      {editing ? (
        <Input className={cn("minutes-input min-w-0 flex-1 rounded-none border-0 border-b border-dotted border-black px-1 shadow-none", uppercase && "uppercase")} placeholder={placeholder} autoCapitalize={uppercase ? "characters" : undefined} value={value} onChange={(event) => onChange(event.target.value)} />
      ) : (
        value ? <span className={uppercase ? "uppercase" : undefined}>{value}</span> : <span className="minutes-blank" aria-label="Chưa điền" />
      )}
    </label>
  );
}

function EditableArea({
  label,
  value,
  placeholder,
  editing,
  bulleted = false,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  editing: boolean;
  bulleted?: boolean;
  onChange: (value: string) => void;
}) {
  const bullets = bulleted ? minutesBullets(value) : [];
  return (
    <div className="minutes-area">
      <p>
        {label}:{editing || bulleted || !value ? null : ` ${cleanMinutesText(value)}`}
      </p>
      {!editing && bulleted && bullets.length ? (
        <ul className="minutes-bullets">
          {bullets.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      ) : null}
      {editing ? (
        <Textarea className="minutes-input mt-1 min-h-24 rounded-none border border-dotted border-black" placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} />
      ) : value || bullets.length ? null : (
        <WritingLines count={2} />
      )}
    </div>
  );
}

function minutesBullets(value: string): string[] {
  const clean = cleanMinutesText(value);
  const roughLines = clean.split(/\n+/);
  return [...new Set(roughLines
    .map((line) => line.replace(/^[-•]\s*/, "").replace(/[.;]\s*$/, "").trim())
    .filter((line) => Boolean(line) && !looksLikeAssessmentReport(line))
    )].map((line) => `${line}.`);
}

function cleanMinutesText(value: string): string {
  return value
    .replace(/\s*-?\s*Chunk[_\s-]*id\s*:\s*[\w-]+/gi, "")
    .replace(/[*_`]+/g, "")
    .replace(/^[ \t]*[IVXLCDM]{1,6}\.[ \t]+/gm, "")
    .replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, "$3/$2/$1")
    .replace(/[ \t]+/g, " ")
    .trim();
}

function incidentNarrativeValue(narrative: string, description: string, facts: ConfirmedFact[]): string {
  if (narrative && !looksLikeAssessmentReport(narrative) && !looksLikeCaseMetadata(narrative)) return narrative;
  const meta = caseDescriptionMeta(description);
  const rows: string[] = [];
  if (meta.violation) rows.push(meta.violation);
  if (meta.body && !looksLikeAssessmentReport(meta.body)) rows.push(meta.body);
  for (const fact of facts) {
    if (INCIDENT_FACT_KEYS.has(fact.fact_key) && fact.value) rows.push(`${fact.label}: ${fact.value}`);
  }
  return rows.map((item) => `- ${cleanMinutesText(item).replace(/[.;]\s*$/, "")}.`).join("\n");
}

function caseDescriptionMeta(description: string): { department?: string; position?: string; violation?: string; body?: string } {
  const meta: { department?: string; position?: string; violation?: string; body?: string } = {};
  const body: string[] = [];
  for (const rawLine of description.split(/\n+/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const separator = line.indexOf(":");
    const key = separator >= 0 ? line.slice(0, separator).trim().toLocaleLowerCase("vi-VN") : "";
    const value = separator >= 0 ? line.slice(separator + 1).trim() : "";
    if (key === "phòng ban") meta.department = value;
    else if (key === "chức danh" || key === "chức vụ" || key === "vị trí") meta.position = value;
    else if (key === "vi phạm") meta.violation = value;
    else body.push(line);
  }
  if (body.length) meta.body = body.join(" ");
  return meta;
}

function looksLikeAssessmentReport(value: string): boolean {
  const upper = value.toUpperCase();
  return (
    upper.includes("BIÊN BẢN ĐÁNH GIÁ") ||
    upper.includes("BIEN BAN ĐANH GIA") ||
    upper.includes("KẾT QUẢ ĐÁNH GIÁ") ||
    upper.includes("CĂN CỨ ĐÁNH GIÁ") ||
    upper.includes("PHÂN TÍCH ĐIỀU KIỆN") ||
    upper.includes("QUY TRÌNH XỬ LÝ") ||
    upper.includes("CHUNK_ID") ||
    upper.includes("CHUNK ID")
  );
}

function looksLikeCaseMetadata(value: string): boolean {
  return value
    .split(/\n+/)
    .map((line) => line.trim().toLocaleLowerCase("vi-VN"))
    .some(
      (line) =>
        line.startsWith("phòng ban:") ||
        line.startsWith("chức danh:") ||
        line.startsWith("chức vụ:") ||
        line.startsWith("vị trí:") ||
        line.startsWith("vi phạm:"),
    );
}

const INCIDENT_FACT_KEYS = new Set([
  "absence_days",
  "late_days",
  "notice_form",
  "violation_time",
  "violation_place",
  "violation_description",
]);

function orderedBasis(items: EvidenceCard[]): EvidenceCard[] {
  return items.map((item, index) => ({ item, index })).sort((left, right) => basisRank(left.item) - basisRank(right.item) || left.index - right.index).map(({ item }) => item);
}

function groupedBasis(items: EvidenceCard[]): string[] {
  const groups = new Map<string, Set<string>>();
  for (const item of items) {
    const label = item.citation_label || item.title;
    const [title, ...parts] = label.split(/\s+[—–]\s+/);
    const references = groups.get(title) ?? new Set<string>();
    if (parts.length) references.add(parts.join(" — "));
    groups.set(title, references);
  }
  return [...groups].map(([title, references]) => references.size ? `${title} — ${[...references].join("; ")}.` : `${title}.`);
}

function StaticLine({ label, value }: { label: string; value?: string | null }) {
  return <p className="minutes-field"><span>{label}: </span>{value ? <span>{value}</span> : <span className="minutes-blank" aria-label="Chưa điền" />}</p>;
}

function WritingLines({ count = 1 }: { count?: number }) {
  return <div aria-label="Phần để trống">{Array.from({ length: count }, (_, index) => <div key={index} className="minutes-writing-line" />)}</div>;
}

function basisRank(item: EvidenceCard): number {
  const policyType = (item.policy_type || "").toUpperCase();
  const title = `${item.citation_label || ""} ${item.title || ""}`.toUpperCase();
  if (policyType === "INTERNAL_RULE" || title.includes("NỘI QUY") || title.includes("NOI QUY") || title.includes("QUY ĐỊNH")) return 0;
  if (policyType === "DECREE" || policyType === "CIRCULAR" || title.includes("NGHỊ ĐỊNH") || title.includes("NGHI DINH")) return 1;
  if (policyType === "LAW" || title.includes("BỘ LUẬT") || title.includes("BO LUAT") || title.includes("LUẬT")) return 2;
  return 3;
}

function Signature({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="min-h-28">
      <p className="font-bold">{title}</p>
      <p>{subtitle}</p>
    </div>
  );
}

function dateParts(value: string | null): string {
  if (!value) return "..... tháng ..... năm .....";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return "..... tháng ..... năm .....";
  return `${day} tháng ${month} năm ${year}`;
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
    <section id={id} className="scroll-mt-4 rounded-xl border border-rule bg-white">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-3">
        <h2 className="text-sm font-semibold tracking-wide text-ink">{title}</h2>
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="text-ink">{value}</dd>
    </div>
  );
}
