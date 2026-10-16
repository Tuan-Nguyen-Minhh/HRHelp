import { BookOpen, ClipboardCheck, FilePenLine, MessagesSquare } from "lucide-react";

import { MessageBubble } from "@/features/conversation/MessageBubble";
import type { ChatMessage } from "@/types/api";

const CAPABILITIES = [
  { icon: MessagesSquare, title: "Làm rõ vụ việc", description: "Hỏi, ghi nhận và giúp bạn xác nhận các tình tiết còn thiếu." },
  { icon: BookOpen, title: "Thông tin nội bộ và bên ngoài", description: "Tra cứu hồ sơ, nội quy, văn bản pháp luật và nguồn công khai bên ngoài theo yêu cầu." },
  { icon: ClipboardCheck, title: "Đánh giá căn cứ và rủi ro", description: "Đối chiếu tình tiết, nêu rủi ro và đề xuất để HR xem xét." },
  { icon: FilePenLine, title: "Biên bản và phiếu pháp chế", description: "Soạn bản nháp để bạn sửa, xuất Word và chuẩn bị phiếu pháp chế khi đủ điều kiện." },
];

export function MessageList({ messages, revealing = false }: { messages: ChatMessage[]; revealing?: boolean }) {
  const visibleMessages = messages.filter((message) => message.role !== "system");

  if (!visibleMessages.length) {
    return (
      <div className="px-1">
        <div className="rounded-2xl border border-rule bg-paper p-5 text-left shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-end justify-center overflow-hidden rounded-2xl border border-rule bg-paper-2 shadow-sm">
              <img className="h-full w-full object-cover object-top" src="/legal-agent-avatar.png" alt="Agent pháp chế" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">Agent pháp chế đã sẵn sàng</h2>
              <p className="mt-1 text-sm leading-6 text-ink-3">Tôi sẽ hỗ trợ bạn xử lý từng bước trong hồ sơ này.</p>
            </div>
          </div>
          <div className="mt-4 rounded-xl bg-paper-2 px-4 py-3">
            <h3 className="text-sm font-semibold text-ink">Bắt đầu lập biên bản vụ việc</h3>
            <p className="mt-1 text-xs leading-5 text-ink-3">Nhập vào ô chat bên dưới:</p>
            <blockquote className="mt-1 text-sm font-medium leading-6 text-son-dark">“Hãy lập biên bản vụ việc này cho tôi.”</blockquote>
            <p className="mt-1 text-xs leading-5 text-ink-3">Tôi sẽ hỏi phần còn thiếu và lên bản nháp chi tiết khi thông tin cần thiết đã được xác nhận.</p>
          </div>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2">
            {CAPABILITIES.map(({ icon: Icon, title, description }) => (
              <div key={title} className="flex items-start gap-2.5">
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-son" aria-hidden="true" />
                <div>
                  <dt className="text-sm font-medium leading-5 text-ink">{title}</dt>
                  <dd className="mt-1 text-xs leading-5 text-ink-3">{description}</dd>
                </div>
              </div>
            ))}
          </dl>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" aria-live="polite" aria-busy={revealing}>
      {visibleMessages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  );
}
