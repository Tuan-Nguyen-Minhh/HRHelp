import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { useMe } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { clearIdempotency, idempotencyKey } from "@/lib/idempotency";
import { HOLD_LABEL, TICKET_LABEL } from "@/lib/labels";
import { api, errorMessage } from "@/services/api";
import type { TicketRequest } from "@/types/api";

const schema = z.object({
  legal_code: z.string().trim().email("Chọn email pháp chế.").max(255),
});

export function LegalTicketCard({ canSend, waitForMinutes = false }: { canSend: boolean; waitForMinutes?: boolean }) {
  const { caseId, caseView, answer, sendTicket, sendingTicket } = useWorkspace();
  const me = useMe();
  const queryClient = useQueryClient();
  const role = me.data?.role ?? "";
  const allowSend = canSend && (role === "HR" || role === "MANAGER");
  const ticket = answer?.ticket ?? null;
  const sent = caseView.status === "PENDING_LEGAL" || ticket?.disposition === "SUBMIT";
  const [error, setError] = useState<string | null>(null);
  const [pendingCode, setPendingCode] = useState<string | null>(null);
  const [confirmDirect, setConfirmDirect] = useState(false);
  const officers = useQuery({ queryKey: ["legal-officers"], queryFn: () => api.legalOfficers() });
  const choices = officers.data?.users ?? [];
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { legal_code: "" } });
  useEffect(() => {
    const rows = officers.data?.users ?? [];
    if (rows.length === 1 && !form.getValues("legal_code")) form.setValue("legal_code", rows[0].email);
  }, [officers.data, form]);
  const escalate = useMutation({
    mutationFn: () => api.escalate(caseId, idempotencyKey(`escalate:${caseId}`)),
    onSuccess: (stored) => {
      clearIdempotency(`escalate:${caseId}`);
      setConfirmDirect(false);
      queryClient.setQueryData(["answer", caseId], stored);
      queryClient.setQueryData(["case", caseId], (current: { status?: string } | undefined) =>
        current ? { ...current, status: stored.case_status } : current,
      );
      void queryClient.invalidateQueries({ queryKey: ["assessment", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["timeline", caseId] });
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["manager-queue"] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  return (
    <section id="legal-ticket" className="scroll-mt-4 rounded-xl border border-rule bg-white px-4 py-4">
      <p className="text-xs font-semibold tracking-[0.14em] text-son-dark">PHIẾU PHÁP CHẾ</p>
      <h2 className="mt-1 text-lg font-semibold text-ink">Xác nhận phiếu và chọn email pháp chế</h2>
      <ol className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
        <Step done={!waitForMinutes} label="1. Xác nhận biên bản" />
        <Step done={sent} label="2. Chọn email pháp chế" />
        <Step done={sent} label="3. Gửi cho pháp chế" />
      </ol>
      {ticket ? (
        <p className="mt-3 text-sm text-ink">
          {TICKET_LABEL[ticket.disposition] ?? ticket.disposition}. {ticket.reason}
          {ticket.hold_code ? ` ${HOLD_LABEL[ticket.hold_code] ?? ticket.hold_code}.` : ""}
        </p>
      ) : (
        <p className="mt-3 text-sm text-ink-3">Chưa có phiếu xem trước. Sub-agent soạn phiếu khi báo cáo đã đủ căn cứ.</p>
      )}
      {sent ? (
        <p className="mt-3 text-sm text-ink">
          Phiếu đã gửi pháp chế.{" "}
          <Link className="font-medium text-son-dark underline" to={`/cases/${caseId}/legal-review`}>
            Xem phiếu đã gửi
          </Link>
        </p>
      ) : (
        <form
          className="mt-4 space-y-3"
          onSubmit={form.handleSubmit((values) => {
            setError(null);
            setPendingCode(values.legal_code);
          })}
        >
          <div className="space-y-1.5">
            <Label htmlFor="legal-code">Email pháp chế</Label>
            {choices.length ? (
              <select
                id="legal-code"
                className="flex h-10 w-full rounded-md border border-rule bg-white px-3 text-sm text-ink"
                {...form.register("legal_code")}
              >
                <option value="">Chọn email pháp chế</option>
                {choices.map((officer) => (
                  <option key={officer.email} value={officer.email}>
                    {officer.full_name ? `${officer.full_name} · ${officer.email}` : officer.email}
                  </option>
                ))}
              </select>
            ) : (
              <Input id="legal-code" type="email" maxLength={255} placeholder="legal.demo@vinuni.edu.vn" autoComplete="email" {...form.register("legal_code")} />
            )}
            {form.formState.errors.legal_code ? <p className="text-xs text-son-dark">{form.formState.errors.legal_code.message}</p> : null}
          </div>
          <p className="text-sm text-ink-3">{hint(allowSend, waitForMinutes, caseView.status, ticket)}</p>
          {error ? <p className="text-sm text-son-dark">{error}</p> : null}
          {pendingCode && allowSend ? (
            <div className="rounded-lg border border-son-line bg-son-tint p-3 text-sm text-son-dark">
              <p>Gửi phiếu cho pháp chế {pendingCode}? Hồ sơ sẽ khóa để pháp chế xem xét.</p>
              <div className="mt-2 flex gap-2">
                <Button variant="secondary" onClick={() => setPendingCode(null)}>
                  Hủy
                </Button>
                <Button
                  disabled={sendingTicket}
                  onClick={() => {
                    void sendTicket(pendingCode)
                      .then(() => {
                        setPendingCode(null);
                        form.reset({ legal_code: "" });
                        void queryClient.invalidateQueries({ queryKey: ["assessment", caseId] });
                      })
                      .catch((err: unknown) => setError(errorMessage(err)));
                  }}
                >
                  {sendingTicket ? "Đang gửi…" : "Xác nhận gửi"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={!allowSend}>
                Gửi pháp chế
              </Button>
              {allowSend ? (
                <Button variant="secondary" onClick={() => setConfirmDirect(true)}>
                  HR xử lý luôn
                </Button>
              ) : null}
            </div>
          )}
          {confirmDirect && allowSend ? (
            <div className="rounded-lg border border-rule bg-paper-2 p-3 text-sm text-ink">
              <p>Không gửi pháp chế. Chuyển hồ sơ cho quản lý duyệt lần cuối?</p>
              <div className="mt-2 flex gap-2">
                <Button variant="secondary" onClick={() => setConfirmDirect(false)}>
                  Hủy
                </Button>
                <Button disabled={escalate.isPending} onClick={() => escalate.mutate()}>
                  {escalate.isPending ? "Đang chuyển…" : "Xác nhận chuyển quản lý"}
                </Button>
              </div>
            </div>
          ) : null}
        </form>
      )}
    </section>
  );
}

function Step({ done, label }: { done: boolean; label: string }) {
  return (
    <li className={`rounded-md border px-3 py-2 ${done ? "border-leather bg-paper-2 text-ink" : "border-rule text-ink"}`}>
      {label}
    </li>
  );
}

function hint(allowSend: boolean, waitForMinutes: boolean, status: string, ticket: TicketRequest | null): string {
  if (allowSend && ticket?.disposition === "HOLD") {
    return `Biên bản đã xác nhận. Chọn email rồi gửi phiếu. Báo cáo vẫn ghi: ${ticket.reason}`;
  }
  if (allowSend) return "Chọn email pháp chế, bấm Gửi pháp chế, rồi xác nhận. AI không tự gửi phiếu.";
  if (ticket?.disposition === "HOLD" && waitForMinutes) {
    return "Có thể chọn email ngay. Nút gửi mở sau khi biên bản được xác nhận.";
  }
  if (ticket?.disposition === "HOLD") {
    return `Có thể chọn email ngay. Nút gửi vẫn đóng: ${ticket.reason}`;
  }
  if (waitForMinutes) return "Có thể chọn email ngay. Nút gửi mở sau khi biên bản được xác nhận.";
  if (status === "APPROVED") return "Hồ sơ đang ở trang quản lý để duyệt lần cuối.";
  if (status === "REJECTED") return "Pháp chế yêu cầu xử lý lại. Mở lại hồ sơ rồi gửi phiếu.";
  if (status === "DECIDED" || status === "CLOSED") return "Quản lý đã duyệt lần cuối.";
  return "Có thể chọn email ngay. Nút gửi mở khi phiếu đang ở bản xem trước.";
}
