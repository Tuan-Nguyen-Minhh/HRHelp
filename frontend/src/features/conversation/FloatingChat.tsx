import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { StandaloneChatPanel } from "@/features/conversation/StandaloneChatPanel";

export function FloatingChat() {
  const [open, setOpen] = useState(false);
  const [opened, setOpened] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyTriggerRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!opened) return;
    const frame = requestAnimationFrame(() => {
      if (open) panelRef.current?.querySelector("textarea")?.focus();
      else triggerRef.current?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [open, opened]);

  return (
    <Dialog.Root modal={false} open={open} onOpenChange={(next) => {
      if (next) setOpened(true);
      else setHistoryOpen(false);
      setOpen(next);
    }}>
      <Dialog.Trigger ref={triggerRef} className="fixed bottom-4 right-4 z-40 h-16 w-16 cursor-pointer rounded-full border-2 border-white bg-paper shadow-xl ring-1 ring-rule transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-son/30 md:bottom-6 md:right-6" aria-label={open ? "Thu nhỏ chat với trợ lý" : "Mở chat với trợ lý"} title={open ? "Thu nhỏ chat" : "Chat với trợ lý HR Help"}>
        <img src="/legal-agent-avatar.png" alt="" className="h-full w-full rounded-full object-cover object-top" />
        <span className="absolute -bottom-0.5 -right-0.5 rounded-full border-2 border-white bg-son px-1.5 py-0.5 text-[9px] font-semibold text-white" aria-hidden="true">AI</span>
      </Dialog.Trigger>
      {opened ? (
        <Dialog.Portal forceMount>
          <Dialog.Content forceMount ref={panelRef} aria-describedby="floating-chat-description" style={{ display: open ? undefined : "none" }} className="fixed bottom-24 right-4 z-40 flex h-[min(680px,calc(100dvh-7rem))] w-[calc(100vw-2rem)] max-w-[420px] flex-col overflow-hidden rounded-2xl border border-rule bg-paper shadow-2xl md:bottom-28 md:right-6" onInteractOutside={(event) => event.preventDefault()} onOpenAutoFocus={(event) => event.preventDefault()} onEscapeKeyDown={(event) => {
            if (historyOpen) {
              event.preventDefault();
              setHistoryOpen(false);
              historyTriggerRef.current?.focus();
            }
          }}>
            <div className="flex shrink-0 items-center gap-3 border-b border-rule bg-linen px-4 py-3">
              <img src="/legal-agent-avatar.png" alt="" className="h-10 w-10 rounded-full border border-rule object-cover object-top" />
              <div className="min-w-0 flex-1">
                <Dialog.Title className="text-sm font-semibold text-ink">Trợ lý HR Help</Dialog.Title>
                <Dialog.Description id="floating-chat-description" className="mt-0.5 text-xs text-ink-3">Trao đổi ngay, không cần tạo hồ sơ</Dialog.Description>
              </div>
              <Dialog.Close className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-3 hover:bg-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-son" aria-label="Thu nhỏ khung chat" title="Thu nhỏ khung chat"><X className="h-4 w-4" aria-hidden="true" /></Dialog.Close>
            </div>
            <StandaloneChatPanel open={open} historyOpen={historyOpen} onHistoryOpenChange={setHistoryOpen} historyTriggerRef={historyTriggerRef} />
          </Dialog.Content>
        </Dialog.Portal>
      ) : null}
    </Dialog.Root>
  );
}
