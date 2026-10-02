import { zodResolver } from "@hookform/resolvers/zod";
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
      <p className="border-t border-neutral-200 px-4 py-3 text-sm text-neutral-600">
        Hồ sơ đang ở trạng thái {workspace.caseView.status} nên không nhận thêm tình tiết.
      </p>
    );
  }

  return (
    <form
      className="border-t border-neutral-200 p-3"
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
        className="w-full resize-none rounded-md border border-neutral-300 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-400 disabled:bg-neutral-100"
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
        <p className="text-xs text-neutral-500">{form.formState.errors.content?.message || "Enter để gửi. Shift+Enter để xuống dòng."}</p>
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
          <Button type="submit" size="sm" disabled={workspace.sending}>
            {workspace.sending ? "Đang gửi…" : "Gửi"}
          </Button>
        </div>
      </div>
    </form>
  );
}
