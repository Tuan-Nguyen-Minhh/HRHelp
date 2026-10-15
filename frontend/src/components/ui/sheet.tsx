import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Sheet({
  open,
  onOpenChange,
  title,
  description = "Nội dung đoạn căn cứ đã lấy cho hồ sơ.",
  className,
  onCloseAutoFocus,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  className?: string;
  onCloseAutoFocus?: (event: Event) => void;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/40" />
        <Dialog.Content onCloseAutoFocus={onCloseAutoFocus} className={cn("fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-rule bg-paper shadow-2xl animate-slide-in-right", className)}>
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-rule px-5 py-4">
            <Dialog.Title className="font-ui text-base font-semibold text-ink">{title}</Dialog.Title>
            <Dialog.Description className="sr-only">{description}</Dialog.Description>
            <Dialog.Close className="inline-flex h-9 shrink-0 cursor-pointer items-center gap-1 rounded-md px-2 text-sm text-ink-3 hover:bg-paper-2 hover:text-ink">
              <X className="h-4 w-4" aria-hidden="true" />
              Đóng
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
