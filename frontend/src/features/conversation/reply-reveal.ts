/** Reveal a completed reply for display; this does not stream model tokens. */
export function revealReply(
  text: string,
  onText: (text: string) => void,
  onDone: () => void,
  frames: {
    request: (callback: FrameRequestCallback) => number;
    cancel: (id: number) => void;
  },
): () => void {
  const characters = Array.from(text);
  const duration = Math.min(6000, Math.max(240, characters.length * 8));
  let started: number | undefined;
  let visible = 0;
  let cancelled = false;
  let frame: number;

  function advance(now: number) {
    if (cancelled) return;
    started ??= now;
    const count = Math.min(characters.length, Math.max(1, Math.floor(characters.length * (now - started) / duration)));
    if (count !== visible) {
      visible = count;
      onText(characters.slice(0, count).join(""));
    }
    if (count === characters.length) onDone();
    else frame = frames.request(advance);
  }

  frame = frames.request(advance);
  return () => {
    cancelled = true;
    frames.cancel(frame);
  };
}
