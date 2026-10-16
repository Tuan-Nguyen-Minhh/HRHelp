/** Reveal a completed reply for display; this does not stream model tokens. */
export function revealReply(
  text: string,
  onText: (text: string) => void,
  onDone: () => void,
  frames: {
    request: (callback: FrameRequestCallback) => number;
    cancel: (id: number) => void;
    isVisible?: () => boolean;
    onVisibilityChange?: (callback: () => void) => () => void;
  },
): () => void {
  const characters = Array.from(text);
  const duration = Math.min(6000, Math.max(240, characters.length * 8));
  let previous: number | undefined;
  let elapsed = 0;
  let visible = 0;
  let cancelled = false;
  let frame: number | null = null;

  function schedule() {
    if (!cancelled && frame === null && frames.isVisible?.() !== false) frame = frames.request(advance);
  }

  // Count time spent displaying the reply, not time spent in another tab.
  // Replies received in the background begin revealing when the user returns.
  const unsubscribe = frames.onVisibilityChange?.(() => {
    previous = undefined;
    if (frames.isVisible?.() === false && frame !== null) {
      frames.cancel(frame);
      frame = null;
    }
    schedule();
  });

  function advance(now: number) {
    frame = null;
    if (cancelled) return;
    if (frames.isVisible?.() === false) {
      previous = undefined;
      return;
    }
    if (previous !== undefined) elapsed += now - previous;
    previous = now;
    const count = Math.min(characters.length, Math.max(1, Math.floor(characters.length * elapsed / duration)));
    if (count !== visible) {
      visible = count;
      onText(characters.slice(0, count).join(""));
    }
    if (cancelled) return;
    if (count === characters.length) {
      cancelled = true;
      unsubscribe?.();
      onDone();
    } else schedule();
  }

  schedule();
  return () => {
    cancelled = true;
    if (frame !== null) frames.cancel(frame);
    frame = null;
    unsubscribe?.();
  };
}
