import { ArrowLeft, ArrowRight, BookOpen, Bot, Check, ClipboardCheck, ClipboardList, Copy, FilePenLine, FolderOpen, MessagesSquare, Route, Scale, ShieldCheck } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth, useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { GUIDE_CAPABILITIES, GUIDE_ROLES, GUIDE_STEPS } from "@/features/guide/guide-content";
import { cn } from "@/lib/utils";

const CAPABILITY_ICONS = { memory: FolderOpen, facts: ClipboardList, sources: BookOpen, assessment: Scale, minutes: FilePenLine, workflow: Route, help: Bot, chat: MessagesSquare };

export function GuidePage() {
  const { auth } = useAuth();
  const me = useMe();
  const role = me.data?.role || auth?.roles?.[0] || "";
  const [selected, setSelected] = useState(0);
  const [copyState, setCopyState] = useState<{ prompt: string; status: "copied" | "failed" } | null>(null);
  const panelId = useId();
  const step = GUIDE_STEPS[selected];

  async function copyPrompt() {
    const prompt = step.prompt;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopyState({ prompt, status: "copied" });
    } catch {
      setCopyState({ prompt, status: "failed" });
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 pb-4">
      <header className="space-y-4 border-b border-rule pb-6">
        <p className="text-xs font-semibold tracking-[0.16em] text-son-dark">GIỚI THIỆU & HƯỚNG DẪN</p>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Từ hồ sơ đến biên bản, từng bước rõ ràng</h1>
            <p className="mt-3 text-sm leading-7 text-ink-2">HR Help là không gian xử lý hồ sơ kỷ luật lao động. Super Agent đồng hành từ làm rõ vụ việc, đối chiếu căn cứ đến chuẩn bị biên bản để người có thẩm quyền xem xét.</p>
          </div>
          {role === "HR" ? <Button asChild><Link to="/cases/new">Tạo hồ sơ mới <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link></Button> : null}
        </div>
        <div className="flex items-start gap-2.5 rounded-lg bg-paper-2 px-4 py-3 text-sm leading-6 text-ink-2">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
          <p><strong className="font-semibold text-ink">AI đề xuất. Người quyết định.</strong> Bạn kiểm tra nội dung; việc gửi, duyệt, ký và ban hành thực hiện theo vai trò và điều kiện của hồ sơ.</p>
        </div>
      </header>

      <section aria-labelledby={`${panelId}-workflow`}>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id={`${panelId}-workflow`} className="text-lg font-semibold text-ink">Tạo hồ sơ và lập biên bản như thế nào?</h2>
            <p className="mt-1 text-sm leading-6 text-ink-3">Chọn từng bước để xem thao tác, vị trí trên web và câu nhắn gợi ý.</p>
          </div>
          <span className="text-xs tabular-nums text-ink-3">{GUIDE_STEPS.length} bước hướng dẫn</span>
        </div>
        <div className="grid items-start gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <nav aria-label="Các bước hướng dẫn" className="min-w-0 rounded-xl border border-rule bg-white p-2">
            <ol className="flex gap-1 overflow-x-auto lg:block lg:space-y-1">
              {GUIDE_STEPS.map((item, index) => (
                <li key={item.title} className="w-60 shrink-0 lg:w-auto">
                  <button type="button" aria-pressed={selected === index} aria-controls={panelId} aria-label={`Xem bước ${index + 1}: ${item.title}`} onClick={() => setSelected(index)} className={cn("flex min-h-16 w-full items-start gap-3 rounded-lg p-3 text-left transition-colors", selected === index ? "bg-son-tint text-son-dark" : "text-ink-2 hover:bg-paper-2")}>
                    <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold tabular-nums", selected === index ? "bg-son text-white" : "bg-paper-2 text-ink-2")}>{index + 1}</span>
                    <span className="min-w-0 pt-0.5"><span className="block text-sm font-semibold">{item.title}</span><span className="mt-1 block text-xs leading-5 text-ink-3">{item.summary}</span></span>
                  </button>
                </li>
              ))}
            </ol>
          </nav>
          <div id={panelId} role="region" aria-labelledby={`${panelId}-step`} className="min-w-0 rounded-xl border border-rule bg-white">
            <div className="border-b border-rule p-5 sm:p-6">
              <p className="text-xs font-medium text-ink-3">BƯỚC {selected + 1} / {GUIDE_STEPS.length} <span className="mx-2" aria-hidden="true">·</span> {step.owner}</p>
              <h3 id={`${panelId}-step`} className="mt-2 text-xl font-semibold text-ink">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-ink-2">{step.description}</p>
              <p className="mt-3 flex items-start gap-2 text-xs leading-5 text-ink-3"><FolderOpen className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span><span className="font-semibold">Thực hiện tại:</span> {step.location}</span></p>
            </div>
            <div className="space-y-5 p-5 sm:p-6">
              <ol className="space-y-4">
                {step.actions.map((action, index) => <li key={action} className="flex gap-3 text-sm leading-6 text-ink-2"><span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-rule text-[10px] font-semibold tabular-nums">{index + 1}</span><span>{action}</span></li>)}
              </ol>
              <div className="flex items-start gap-2.5 rounded-lg bg-paper-2 p-4 text-sm leading-6 text-ink-2"><ClipboardCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><p><strong className="font-semibold text-ink">Sau bước này:</strong> {step.result}</p></div>
              <div className="border-t border-rule pt-4">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-ink-2">CÂU NHẮN GỢI Ý CHO SUPER AGENT</p>
                  <Button size="sm" variant="ghost" onClick={() => void copyPrompt()} aria-label="Sao chép câu nhắn gợi ý">{copyState?.prompt === step.prompt && copyState.status === "copied" ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}Sao chép</Button>
                </div>
                <blockquote className="border-l-2 border-rule pl-3 text-sm leading-6 text-ink-2">“{step.prompt}”</blockquote>
                <p role="status" className="mt-2 text-xs leading-5 text-ink-3">{copyState?.prompt === step.prompt ? copyState.status === "copied" ? "Đã sao chép. Mở hội thoại của hồ sơ và dán để sử dụng." : "Chưa sao chép được. Bạn có thể chọn và sao chép câu nhắn phía trên." : "Dùng trong hội thoại của hồ sơ bạn đang xử lý."}</p>
              </div>
              <div className="flex items-center justify-between gap-3 border-t border-rule pt-4">
                <Button variant="secondary" size="sm" disabled={selected === 0} onClick={() => setSelected((current) => current - 1)}><ArrowLeft className="h-4 w-4" aria-hidden="true" />Bước trước</Button>
                <Button variant="secondary" size="sm" disabled={selected === GUIDE_STEPS.length - 1} onClick={() => setSelected((current) => current + 1)}>Bước tiếp theo<ArrowRight className="h-4 w-4" aria-hidden="true" /></Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby={`${panelId}-capabilities`}>
        <h2 id={`${panelId}-capabilities`} className="text-lg font-semibold text-ink">Super Agent hỗ trợ được những gì?</h2>
        <p className="mt-1 text-sm leading-6 text-ink-3">Bạn nói mục tiêu bằng ngôn ngữ tự nhiên. Khi chưa rõ ý, trợ lý có thể hỏi lại trước khi tiếp tục.</p>
        <div className="mt-4 grid gap-px overflow-hidden rounded-xl border border-rule bg-rule sm:grid-cols-2">
          {GUIDE_CAPABILITIES.map((capability) => {
            const Icon = CAPABILITY_ICONS[capability.icon];
            return <article key={capability.title} className="bg-white p-5"><div className="flex items-start gap-3"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-ink-2" aria-hidden="true" /><div className="min-w-0"><h3 className="text-sm font-semibold text-ink">{capability.title}</h3><p className="mt-2 text-sm leading-6 text-ink-2">{capability.description}</p><p className="mt-3 text-xs leading-5 text-ink-3">Ví dụ: “{capability.example}”</p></div></div></article>;
          })}
        </div>
      </section>

      <section aria-labelledby={`${panelId}-roles`} className="rounded-xl border border-rule bg-white">
        <div className="border-b border-rule px-5 py-4"><h2 id={`${panelId}-roles`} className="text-lg font-semibold text-ink">Ai thực hiện bước nào?</h2><p className="mt-1 text-sm leading-6 text-ink-3">Mỗi tài khoản chỉ thấy và thực hiện các chức năng được phân quyền.</p></div>
        <dl className="divide-y divide-rule px-5">{GUIDE_ROLES.map((item) => <div key={item.role} className="grid gap-1 py-4 text-sm sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4"><dt className="font-semibold text-ink">{item.role}</dt><dd className="leading-6 text-ink-2">{item.description}</dd></div>)}</dl>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-rule bg-paper-2 px-5 py-4">
        <div><h2 className="text-sm font-semibold text-ink">Sẵn sàng bắt đầu?</h2><p className="mt-1 text-sm leading-6 text-ink-2">{role === "HR" ? "Tạo hồ sơ mới hoặc mở hồ sơ đang có để tiếp tục cuộc hội thoại." : "Về bảng điều khiển để xem các hồ sơ và công việc thuộc vai trò của bạn."}</p></div>
        <Button asChild variant="secondary"><Link to={role === "HR" ? "/cases" : "/dashboard"}>{role === "HR" ? "Mở hồ sơ HR" : "Về bảng điều khiển"}<ArrowRight className="h-4 w-4" aria-hidden="true" /></Link></Button>
      </section>
    </div>
  );
}
