import { zodResolver } from "@hookform/resolvers/zod";
import { SendHorizontal } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/features/case-management/CaseWorkspace";
import { MUTABLE_CASE_STATUS } from "@/lib/workflow";
import { errorMessage } from "@/services/api";

const schema = z.object({
  content: z.string().trim().min(1, "Nhập nội dung.").max(8000, "Nội dung dài quá 8000 ký tự."),
});

export function MessageInput() {
  const workspace = useWorkspace();
  const open = MUTABLE_CASE_STATUS.has(workspace.caseView.status);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { content: "" } });
  const field = form.register("content");

  useEffect(() => {
    if (workspace.failedDraft) form.setValue("content", workspace.failedDraft);
  }, [workspace.failedDraft, form]);

  if (!open) {
    return (
      <p className="border-t border-[#d8e9ee] bg-white px-4 py-3 text-sm text-[#4d7380]">
        Hồ sơ đang ở trạng thái {workspace.caseView.status} nên không nhận thêm tình tiết.
      </p>
    );
  }

  return (
    <form
      className="border-t border-[#d8e9ee] bg-white p-3 md:p-4"
      onSubmit={form.handleSubmit(async (values) => {
        try {
          await workspace.send(values.content);
          form.reset({ content: "" });
        } catch (error) {
          form.setError("content", { message: errorMessage(error) });
        }
      })}
    >
      <label className="sr-only" htmlFor="chat-content">
        Nội dung trả lời
      </label>
      <textarea
        id="chat-content"
        rows={3}
        placeholder="Nhập tình tiết hoặc câu trả lời…"
        disabled={workspace.sending}
        className="w-full resize-none rounded-2xl border border-[#cfe5ec] bg-[#f8fbfd] px-4 py-3 text-sm leading-6 text-[#073642] shadow-inner shadow-slate-200/40 placeholder:text-[#7b96a0] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009ec1]/30 disabled:bg-neutral-100"
        {...field}
        ref={(node) => {
          field.ref(node);
          workspace.registerChat(node);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void form.handleSubmit(async (values) => {
              try {
                await workspace.send(values.content);
                form.reset({ content: "" });
              } catch (error) {
                form.setError("content", { message: errorMessage(error) });
              }
            })();
          }
        }}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-xs text-[#607d88]">{form.formState.errors.content?.message || "Enter để gửi. Shift+Enter để xuống dòng."}</p>
        <div className="flex gap-2">
          {workspace.failedDraft ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={workspace.sending}
              onClick={() => void workspace.retry().catch(() => undefined)}
            >
              Gửi lại
            </Button>
          ) : null}
          <Button className="gap-2" type="submit" size="sm" disabled={workspace.sending}>
            <SendHorizontal className="h-4 w-4" aria-hidden="true" />
            {workspace.sending ? "Đang gửi…" : "Gửi"}
          </Button>
        </div>
      </div>
    </form>
  );
}
