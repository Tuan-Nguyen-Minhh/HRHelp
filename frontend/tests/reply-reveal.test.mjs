import assert from "node:assert/strict";
import test from "node:test";

import { revealReply } from "../src/features/conversation/reply-reveal.ts";

function clock() {
  let next = 0;
  const callbacks = new Map();
  return {
    request(callback) { callbacks.set(++next, callback); return next; },
    cancel(id) { callbacks.delete(id); },
    tick(now) {
      const pending = [...callbacks.values()];
      callbacks.clear();
      pending.forEach((callback) => callback(now));
    },
    get pending() { return callbacks.size; },
  };
}

test("a new reply is partial across frames, then completes exactly once", () => {
  const frames = clock();
  const updates = [];
  let done = 0;
  const text = "Đã nhận tình tiết. HR có thể sửa biên bản trước khi gửi pháp chế. 🧑‍💼";
  revealReply(text, (part) => updates.push(part), () => done++, frames);
  assert.equal(updates.length, 0);
  frames.tick(100);
  frames.tick(300);
  assert.ok(updates.length > 1);
  assert.ok(updates.at(-1).length < text.length);
  assert.ok(updates.every((part) => text.startsWith(part)));
  frames.tick(7000);
  frames.tick(8000);
  assert.equal(updates.at(-1), text);
  assert.equal(done, 1);
  assert.equal(frames.pending, 0);
});

test("cancelling on skip, case change or unmount stops all later updates", () => {
  const frames = clock();
  const updates = [];
  let done = false;
  const cancel = revealReply("Câu trả lời mới được hiển thị dần.", (part) => updates.push(part), () => { done = true; }, frames);
  frames.tick(0);
  cancel();
  const count = updates.length;
  frames.tick(7000);
  assert.equal(updates.length, count);
  assert.equal(done, false);
  assert.equal(frames.pending, 0);
});

test("long replies finish within six seconds without losing any text", () => {
  const frames = clock();
  const text = "Nội dung biên bản đầy đủ. ".repeat(500);
  let visible = "";
  let done = false;
  revealReply(text, (part) => { visible = part; }, () => { done = true; }, frames);
  frames.tick(0);
  frames.tick(5999);
  assert.ok(visible.length < text.length);
  frames.tick(6000);
  assert.equal(visible, text);
  assert.equal(done, true);
});

test("Unicode code points are not split during display", () => {
  const frames = clock();
  const updates = [];
  revealReply("😀😀😀😀", (part) => updates.push(part), () => {}, frames);
  frames.tick(0);
  frames.tick(120);
  frames.tick(240);
  assert.deepEqual(updates, ["😀", "😀😀", "😀😀😀😀"]);
});
