import { formatTime, cn } from "@/lib/utils";
import { readableAssistantText } from "@/lib/report";
import type { ChatMessage } from "@/types/api";

const ROLE_LABEL = { user: "Bạn", assistant: "Agent pháp chế" };

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "system") return null;
  const mine = message.role === "user";
  const text = mine ? message.text : readableAssistantText(message.text);
  return (
    <div className={cn("flex py-2", mine ? "justify-end" : "justify-start")}>
      <article className={cn("min-w-0 text-[15px]", mine ? "max-w-[90%] rounded-3xl bg-paper-2 px-5 py-3.5 text-ink md:max-w-[80%]" : "w-full py-3 text-ink")}>
        <header className="mb-2 flex items-center gap-2 text-[11px] text-ink-3">
          {!mine ? <img className="h-6 w-6 rounded-full border border-rule object-cover object-top" src="/legal-agent-avatar.png" alt="" aria-hidden="true" /> : null}
          <span className="font-medium">{ROLE_LABEL[message.role]}</span>
          <time dateTime={message.at} className="ml-auto text-[10px]">{formatTime(message.at)}</time>
        </header>
        <p className="whitespace-pre-wrap break-words leading-7">{text}</p>
      </article>
    </div>
  );
}
