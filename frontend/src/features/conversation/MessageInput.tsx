import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowUp, LoaderCircle } from "lucide-react";
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
      <p className="rounded-2xl border border-rule bg-paper-2 px-4 py-3 text-sm text-ink-3">
        Hồ sơ đang ở trạng thái {workspace.caseView.status} nên không nhận thêm tình tiết.
      </p>
    );
  }

  return (
    <form
      className="rounded-3xl border border-rule bg-white px-4 py-3 shadow-sm focus-within:border-rule-2 focus-within:ring-2 focus-within:ring-son/15"
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
        rows={2}
        placeholder="Nhập tình tiết hoặc câu trả lời…"
        disabled={workspace.sending}
        className="block max-h-40 min-h-14 w-full resize-none border-0 bg-transparent px-1 py-1 text-sm leading-6 text-ink placeholder:text-ink-4 focus-visible:outline-none disabled:opacity-60"
        {...field}
        ref={(node) => {
          field.ref(node);
          workspace.registerChat(node);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
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
        <p className="text-[10px] leading-4 text-ink-3">{form.formState.errors.content?.message || "Enter để gửi · Shift+Enter xuống dòng"}</p>
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
          <Button className="h-9 w-9 shrink-0 rounded-full p-0" type="submit" size="icon" disabled={workspace.sending} title="Gửi tin nhắn">
            {workspace.sending ? <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowUp className="h-4 w-4" aria-hidden="true" />}
            <span className="sr-only">{workspace.sending ? "Đang gửi…" : "Gửi"}</span>
          </Button>
        </div>
      </div>
    </form>
  );
}
