import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowUp, LoaderCircle } from "lucide-react";
import { useEffect, useId, useRef } from "react";
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

  if (!open) {
    return (
      <p className="rounded-2xl border border-rule bg-paper-2 px-4 py-3 text-sm text-ink-3">
        Hồ sơ đang ở trạng thái {workspace.caseView.status} nên không nhận thêm tình tiết.
      </p>
    );
  }

  return <ChatComposer sending={workspace.sending} send={workspace.send} failedDraft={workspace.failedDraft} retry={workspace.retry} registerChat={workspace.registerChat} />;
}

interface ChatComposerProps {
  sending: boolean;
  send: (content: string) => Promise<void>;
  failedDraft?: string | null;
  retry?: () => Promise<void>;
  registerChat?: (node: HTMLTextAreaElement | null) => void;
  placeholder?: string;
}

export function ChatComposer({ sending, send, failedDraft, retry, registerChat, placeholder = "Nhập tình tiết hoặc câu trả lời…" }: ChatComposerProps) {
  const contentId = useId();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { content: "" } });
  const field = form.register("content");
  const submitting = useRef(false);

  useEffect(() => {
    if (failedDraft) form.setValue("content", failedDraft);
  }, [failedDraft, form]);

  const submit = form.handleSubmit(async (values) => {
    if (sending || submitting.current) return;
    submitting.current = true;
    try {
      await send(values.content);
      form.reset({ content: "" });
    } catch (error) {
      form.setError("content", { message: errorMessage(error) });
    } finally {
      submitting.current = false;
    }
  });

  return (
    <form
      className="rounded-3xl border border-rule bg-white px-4 py-3 shadow-sm focus-within:border-rule-2 focus-within:ring-2 focus-within:ring-son/15"
      onSubmit={submit}
    >
      <label className="sr-only" htmlFor={contentId}>
        Nội dung trả lời
      </label>
      <textarea
        id={contentId}
        data-chat-content
        rows={2}
        placeholder={placeholder}
        disabled={sending}
        className="block max-h-40 min-h-14 w-full resize-none border-0 bg-transparent px-1 py-1 text-sm leading-6 text-ink placeholder:text-ink-4 focus-visible:outline-none disabled:opacity-60"
        {...field}
        ref={(node) => {
          field.ref(node);
          registerChat?.(node);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            void submit();
          }
        }}
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <p className="text-[10px] leading-4 text-ink-3">{form.formState.errors.content?.message || "Enter để gửi · Shift+Enter xuống dòng"}</p>
        <div className="flex gap-2">
          {failedDraft && retry ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={sending}
              onClick={() => void retry().catch(() => undefined)}
            >
              Gửi lại
            </Button>
          ) : null}
          <Button className="h-9 w-9 shrink-0 rounded-full p-0" type="submit" size="icon" disabled={sending} title="Gửi tin nhắn">
            {sending ? <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowUp className="h-4 w-4" aria-hidden="true" />}
            <span className="sr-only">{sending ? "Đang gửi…" : "Gửi"}</span>
          </Button>
        </div>
      </div>
    </form>
  );
}
