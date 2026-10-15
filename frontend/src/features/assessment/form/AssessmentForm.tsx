import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { LegalTicketCard } from "@/features/decision/LegalTicketCard";
import { DocumentSections, EvidenceDetail, sectionLinks, type EditKey } from "@/features/assessment/form/Sections";
import { formatDate } from "@/lib/utils";
import { api, errorMessage } from "@/services/api";
import type {
  AssessmentForm as AssessmentFormView,
  AssessmentPatch,
  AssessmentSections,
  CaseInformation,
  ConfirmedFact,
  EmployeeInformation,
  EvidenceCard,
  FormStatus,
  IncidentSummary,
} from "@/types/assessment";

const FORM_STATUS: Record<FormStatus, string> = {
  AI_DRAFT: "Bản nháp AI",
  HR_EDITING: "HR đang sửa",
  READY_FOR_CONFIRM: "Sẵn sàng xác nhận",
  CONFIRMED: "HR đã xác nhận",
  SUPERSEDED: "Đã được thay bằng bản sau",
};

interface DraftState {
  case_information?: CaseInformation;
  employee_information?: EmployeeInformation;
  incident_summary?: IncidentSummary;
  confirmed_facts?: ConfirmedFact[];
  handling_rationale?: string;
}

export function AssessmentEntry() {
  const { caseId } = useWorkspace();
  const query = useQuery({ queryKey: ["assessment", caseId], queryFn: () => api.getAssessment(caseId) });
  const form = query.data;
  return (
    <section className="rounded-xl border border-rule bg-white px-4 py-4">
      <p className="text-xs font-semibold tracking-[0.14em] text-son-dark">BIÊN BẢN ĐÁNH GIÁ</p>
      <p className="mt-1 text-sm text-ink">
        {form ? `Phiên bản ${form.version}. ${FORM_STATUS[form.form_status]}.` : "Chưa có biên bản dạng biểu mẫu."}
      </p>
      <p className="mt-1 text-sm text-ink-3">AI soạn bản nháp. HR xem, sửa và xác nhận trước khi gửi phiếu.</p>
      <Button asChild className="mt-3">
        <Link to={`/cases/${caseId}/assessment`}>Mở biên bản</Link>
      </Button>
    </section>
  );
}

export function AssessmentForm() {
  const { caseId } = useWorkspace();
  const me = useMe();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["assessment", caseId], queryFn: () => api.getAssessment(caseId) });
  const [draft, setDraft] = useState<DraftState>({});
  const [editing, setEditing] = useState<EditKey | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [askConfirm, setAskConfirm] = useState(false);
  const [askRedo, setAskRedo] = useState(false);
  const [exportNote, setExportNote] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [selected, setSelected] = useState<EvidenceCard | null>(null);
  const view = query.data ?? null;
  const versionKey = view ? `${view.assessment_id}:${view.version}:${view.status}` : "";

  useEffect(() => {
    setDraft({});
    setEditing(null);
    setAskConfirm(false);
  }, [versionKey]);

  function store(next: AssessmentFormView, refreshCase: boolean) {
    queryClient.setQueryData(["assessment", caseId], next);
    if (refreshCase) {
      void queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["facts", caseId] });
    }
  }

  const generate = useMutation({
    mutationFn: () => api.generateAssessment(caseId),
    onSuccess: (next) => {
      setNotice(null);
      store(next, false);
    },
  });
  const redo = useMutation({
    mutationFn: () => api.reanalyzeAssessment(caseId),
    onSuccess: (next) => {
      setAskRedo(false);
      setNotice(null);
      store(next, false);
    },
  });
  const save = useMutation({
    mutationFn: (body: AssessmentPatch) => api.saveAssessment(caseId, body),
    onSuccess: (next) => {
      setNotice(null);
      store(next, true);
    },
  });
  const confirm = useMutation({
    mutationFn: () => api.confirmAssessment(caseId),
    onSuccess: (next) => {
      setAskConfirm(false);
      setNotice(null);
      store(next, false);
      requestAnimationFrame(() => document.getElementById("legal-ticket")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    },
  });

  const busy = generate.isPending || redo.isPending || save.isPending || confirm.isPending;
  const failure = generate.error || redo.error || save.error || confirm.error;
  const role = me.data?.role ?? "";
  const canStart = role === "HR" || role === "MANAGER";

  async function persist(nextDraft: DraftState) {
    const patch = toPatch(nextDraft);
    if (!patch) {
      setNotice("Chưa có chỉnh sửa để lưu.");
      setEditing(null);
      return;
    }
    await save.mutateAsync(patch);
  }

  async function exportWord() {
    if (toPatch(draft)) {
      setNotice("Hãy lưu phần đang sửa trước khi xuất Word.");
      return;
    }
    setExporting(true);
    setExportNote(null);
    try {
      const payload = await api.exportCase(caseId, "assessment", "docx");
      const content = typeof payload.content === "object" && payload.content !== null ? payload.content : {};
      const fileName = "file_name" in content && typeof content.file_name === "string" ? content.file_name : "biên bản Word";
      const path = "path" in content && typeof content.path === "string" ? content.path : "";
      setExportNote(path ? `Đã tạo ${fileName}: ${path}` : `Đã tạo ${fileName}.`);
    } catch (error) {
      setExportNote(errorMessage(error));
    } finally {
      setExporting(false);
    }
  }

  if (query.isLoading) {
    return <p className="rounded-xl border border-rule bg-white px-4 py-6 text-sm text-ink-3">Đang tải biên bản…</p>;
  }
  if (query.isError) {
    return <p className="rounded-xl border border-son-line bg-son-tint px-4 py-4 text-sm text-son-dark">{errorMessage(query.error)}</p>;
  }
  if (!view) {
    return (
      <section className="rounded-xl border border-rule bg-white px-4 py-6">
        <p className="text-xs font-semibold tracking-[0.14em] text-son-dark">BIÊN BẢN ĐÁNH GIÁ VÀ ĐỀ XUẤT XỬ LÝ</p>
        <h2 className="mt-2 text-xl font-semibold text-ink">Chưa có biên bản dạng biểu mẫu</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-3">
          AI lập bản nháp từ tình tiết đã xác nhận và căn cứ đã truy xuất. Sau khi HR xác nhận biên bản, chọn email pháp chế để gửi phiếu. AI không tự gửi.
        </p>
        {failure ? <p className="mt-3 text-sm text-son-dark">{errorMessage(failure)}</p> : null}
        {canStart ? (
          <Button className="mt-4" disabled={busy} onClick={() => generate.mutate()}>
            {generate.isPending ? "Đang lập biên bản…" : "Lập biên bản"}
          </Button>
        ) : (
          <p className="mt-4 text-sm text-ink-3">Chỉ HR lập và xác nhận biên bản.</p>
        )}
      </section>
    );
  }

  const sections = shown(view, draft);
  const blocking = view.validation.blocking_errors;

  return (
    <div className="space-y-4">
      <header className="rounded-xl border border-rule bg-white px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-son-dark">HỒ SƠ {sections.case_information.case_code}</p>
            <h2 className="mt-1 text-xl font-semibold text-ink">Biên bản xử lý vi phạm kỷ luật</h2>
            <p className="mt-1 text-sm text-ink-3">
              {view.metadata.source === "HR" ? "HR đã sửa bản này." : "AI đề xuất bản nháp."} Lập ngày {formatDate(view.metadata.case_created_date ?? null)}. Phiên bản {view.version}.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" disabled={busy || exporting} onClick={() => void exportWord()}>
              {exporting ? "Đang xuất…" : "Xuất Word"}
            </Button>
            <p className="rounded-md border border-rule bg-paper-2 px-3 py-1.5 text-sm font-medium text-ink">
              {FORM_STATUS[view.form_status]}
            </p>
          </div>
        </div>
        {exportNote ? <p className="mt-3 rounded-md border border-rule bg-paper-2 px-3 py-2 text-xs text-ink-2">{exportNote}</p> : null}
      </header>

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
          view={view}
          sections={sections}
          editing={editing}
          saving={save.isPending}
          onBegin={(key) => {
            setNotice(null);
            setEditing(key);
            setDraft((current) => seed(current, key, view.sections));
          }}
          onCancel={() => {
            if (editing) setDraft((current) => drop(current, editing));
            setEditing(null);
          }}
          onSave={() => {
            void persist(draft).catch(() => undefined);
          }}
          onCase={(value) => setDraft((current) => ({ ...current, case_information: value }))}
          onEmployee={(value) => setDraft((current) => ({ ...current, employee_information: value }))}
          onIncident={(value) => setDraft((current) => ({ ...current, incident_summary: value }))}
          onFacts={(value) => setDraft((current) => ({ ...current, confirmed_facts: value }))}
          onRationale={(value) => setDraft((current) => ({ ...current, handling_rationale: value }))}
          onOpen={setSelected}
        />
      </div>

      {blocking.length ? (
        <section className="rounded-xl border border-son-line bg-son-tint px-4 py-4 text-sm text-son-dark">
          <h2 className="font-semibold">Không thể xác nhận biên bản</h2>
          <p className="mt-1">Còn {blocking.length} thông tin bắt buộc cần bổ sung:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {blocking.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link to={`/cases/${caseId}/conversation`}>Quay lại cuộc hội thoại</Link>
            </Button>
            {view.permissions.can_reanalyze ? (
              <Button variant="secondary" disabled={busy} onClick={() => setAskRedo(true)}>
                Lập lại biên bản
              </Button>
            ) : null}
          </div>
        </section>
      ) : null}

      {view.validation.warnings.length ? (
        <section className="rounded-xl border border-rule bg-white px-4 py-3 text-sm text-ink">
          <h2 className="font-medium">Lưu ý không chặn xác nhận</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {view.validation.warnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {view.status === "CONFIRMED" ? (
        <p className="rounded-xl border border-rule bg-paper-2 px-4 py-3 text-sm text-ink">
          {view.permissions.can_create_ticket
            ? "Biên bản đã được HR xác nhận. Chọn email pháp chế bên dưới rồi gửi phiếu. AI không tự gửi."
            : "Biên bản đã được HR xác nhận. Phiếu này không mở để gửi."}
        </p>
      ) : null}

      <div className="rounded-xl border border-rule bg-white px-4 py-3">
        {!view.permissions.can_confirm && view.status !== "CONFIRMED" && blocking.length === 0 ? (
          <p className="mb-2 text-sm text-ink-3">Xác nhận chỉ mở khi hồ sơ còn ở bước HR và biên bản không còn lỗi bắt buộc.</p>
        ) : null}
        {notice ? <p className="mb-2 text-sm text-ink-3">{notice}</p> : null}
        {failure ? <p className="mb-2 text-sm text-son-dark">{errorMessage(failure)}</p> : null}
        {askConfirm ? (
          <div className="mb-3 rounded-md border border-son-line bg-son-tint px-3 py-3 text-sm text-son-dark">
            <p>Xác nhận biên bản này? AI không gửi phiếu. HR vẫn xác nhận phiếu ở bước sau.</p>
            <div className="mt-2 flex gap-2">
              <Button variant="secondary" onClick={() => setAskConfirm(false)}>
                Hủy
              </Button>
              <Button disabled={busy} onClick={() => confirm.mutate()}>
                {confirm.isPending ? "Đang xác nhận…" : "Xác nhận biên bản"}
              </Button>
            </div>
          </div>
        ) : null}
        {askRedo ? (
          <div className="mb-3 rounded-md border border-rule bg-paper-2 px-3 py-3 text-sm text-ink">
            <p>Lập lại tạo một phiên bản mới từ tình tiết và căn cứ đã lưu. Bản cũ được giữ. Phiếu không được gửi.</p>
            <div className="mt-2 flex gap-2">
              <Button variant="secondary" onClick={() => setAskRedo(false)}>
                Hủy
              </Button>
              <Button disabled={busy} onClick={() => redo.mutate()}>
                {redo.isPending ? "Đang lập lại…" : "Lập lại"}
              </Button>
            </div>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {view.permissions.can_edit ? (
            <Button variant="secondary" disabled={busy} onClick={() => void persist(draft).catch(() => undefined)}>
              {save.isPending ? "Đang lưu…" : "Lưu nháp"}
            </Button>
          ) : null}
          {view.permissions.can_reanalyze ? (
            <Button variant="secondary" disabled={busy} onClick={() => setAskRedo(true)}>
              Lập lại phân tích
            </Button>
          ) : null}
          <Button
            disabled={!view.permissions.can_confirm || busy}
            onClick={() => {
              if (toPatch(draft)) {
                setNotice("Hãy lưu phần đang sửa trước khi xác nhận.");
                return;
              }
              setAskConfirm(true);
            }}
          >
            {view.status === "CONFIRMED" ? "Đã xác nhận" : "Xác nhận biên bản"}
          </Button>
        </div>
      </div>
      <LegalTicketCard canSend={view.permissions.can_create_ticket} waitForMinutes={view.status !== "CONFIRMED"} />

      <Sheet open={selected !== null} onOpenChange={(open) => { if (!open) setSelected(null); }} title="Đoạn căn cứ">
        {selected ? <EvidenceDetail card={selected} /> : null}
      </Sheet>
    </div>
  );
}

function shown(view: AssessmentFormView, draft: DraftState): AssessmentSections {
  const handling = view.sections.handling_proposal;
  return {
    ...view.sections,
    case_information: draft.case_information ?? view.sections.case_information,
    employee_information: draft.employee_information ?? view.sections.employee_information,
    incident_summary: draft.incident_summary ?? view.sections.incident_summary,
    confirmed_facts: draft.confirmed_facts ?? view.sections.confirmed_facts,
    handling_proposal:
      draft.handling_rationale === undefined ? handling : { ...handling, rationale: draft.handling_rationale },
  };
}

function seed(current: DraftState, key: EditKey, sections: AssessmentSections): DraftState {
  if (key === "case" && !current.case_information) return { ...current, case_information: sections.case_information };
  if (key === "employee" && !current.employee_information) return { ...current, employee_information: sections.employee_information };
  if (key === "incident" && !current.incident_summary) return { ...current, incident_summary: sections.incident_summary };
  if (key === "facts" && !current.confirmed_facts) return { ...current, confirmed_facts: sections.confirmed_facts };
  if (key === "rationale" && current.handling_rationale === undefined) {
    return { ...current, handling_rationale: sections.handling_proposal.rationale };
  }
  return current;
}

function drop(current: DraftState, key: EditKey): DraftState {
  const next = { ...current };
  if (key === "case") delete next.case_information;
  if (key === "employee") delete next.employee_information;
  if (key === "incident") delete next.incident_summary;
  if (key === "facts") delete next.confirmed_facts;
  if (key === "rationale") delete next.handling_rationale;
  return next;
}

function toPatch(draft: DraftState): AssessmentPatch | null {
  const patch: AssessmentPatch = {};
  if (draft.case_information) patch.case_information = draft.case_information;
  if (draft.employee_information) patch.employee_information = draft.employee_information;
  if (draft.incident_summary) patch.incident_summary = draft.incident_summary;
  if (draft.confirmed_facts) patch.confirmed_facts = draft.confirmed_facts;
  if (draft.handling_rationale !== undefined) patch.handling_rationale = draft.handling_rationale;
  return Object.keys(patch).length ? patch : null;
}
