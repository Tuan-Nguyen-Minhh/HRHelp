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
        <Dialog.Overlay className="fixed inset-0 z-40 bg-dark-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-200/50 bg-white/95 backdrop-blur-md shadow-2xl animate-slide-in-right">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <Dialog.Title className="font-display text-base font-bold text-dark-900">{title}</Dialog.Title>
            <Dialog.Description className="sr-only">Nội dung đoạn căn cứ đã lấy cho hồ sơ.</Dialog.Description>
            <Dialog.Close className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-700">
              <X className="h-4 w-4" aria-hidden="true" />
              Đóng
            </Dialog.Close>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
