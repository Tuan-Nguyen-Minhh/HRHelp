import { useEffect, useRef, useState } from "react";

import { revealReply } from "@/features/conversation/reply-reveal";
import { readableAssistantText } from "@/lib/report";
import type { ChatMessage } from "@/types/api";

/** Keep the complete reply in history; only its current display is shortened. */
export function useReplyReveal(caseId: string) {
  const [reply, setReply] = useState<{ caseId: string; id: string; text: string } | null>(null);
  const cancel = useRef<(() => void) | null>(null);

  function finish() {
    cancel.current?.();
    cancel.current = null;
    setReply(null);
  }

  useEffect(() => {
    setReply(null);
    return () => {
      cancel.current?.();
      cancel.current = null;
    };
  }, [caseId]);

  function start(message: ChatMessage) {
    finish();
    // Incremental text is the requested chat behavior, independent of decorative
    // motion preferences. The user can still choose “Hiện toàn bộ” explicitly.
    const text = readableAssistantText(message.text);
    if (!text) return;
    setReply({ caseId, id: message.id, text: "" });
    cancel.current = revealReply(text, (part) => setReply({ caseId, id: message.id, text: part }), finish, {
      request: (callback) => requestAnimationFrame(callback),
      cancel: (id) => cancelAnimationFrame(id),
      isVisible: () => !document.hidden,
      onVisibilityChange: (callback) => {
        document.addEventListener("visibilitychange", callback);
        return () => document.removeEventListener("visibilitychange", callback);
      },
    });
  }

  return { reply: reply?.caseId === caseId ? reply : null, start, finish };
}
