import { formatTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";

const ROLE_LABEL = { user: "Nhân sự", assistant: "Trợ lý", system: "Trạng thái" };

export function MessageBubble({ message }: { message: ChatMessage }) {
  const mine = message.role === "user";
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <article
        className={cn(
          "max-w-[85%] rounded-lg px-3 py-2 text-sm",
          mine && "bg-[#009EC1] text-white",
          message.role === "assistant" && "border border-[#d5e8ed] bg-white text-[#073642]",
          message.role === "system" && "border border-[#9fd0db] bg-[#e7f6f9] text-[#073642]",
        )}
      >
        <header className="mb-1 flex items-center justify-between gap-3 text-[11px] opacity-80">
          <span>{ROLE_LABEL[message.role]}</span>
          <time dateTime={message.at}>{formatTime(message.at)}</time>
        </header>
        <p className="whitespace-pre-wrap leading-6">{message.text}</p>
      </article>
    </div>
  );
}
