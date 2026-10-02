import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

export function Sheet({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-neutral-950/30" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-neutral-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
            <Dialog.Title className="text-sm font-semibold text-neutral-900">{title}</Dialog.Title>
            <Dialog.Description className="sr-only">Nội dung đoạn căn cứ đã lấy cho hồ sơ.</Dialog.Description>
            <Dialog.Close className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-sm text-neutral-600 hover:bg-neutral-100">
              <X className="h-4 w-4" aria-hidden="true" />
              Đóng
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
