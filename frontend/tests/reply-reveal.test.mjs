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

function tabClock(initiallyVisible = true) {
  const frames = clock();
  const listeners = new Set();
  let visible = initiallyVisible;
  return {
    ...frames,
    get pending() { return frames.pending; },
    isVisible: () => visible,
    onVisibilityChange(callback) {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    setVisible(value) {
      visible = value;
      [...listeners].forEach((callback) => callback());
    },
    get listeners() { return listeners.size; },
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

test("a reply received in another tab starts progressively when returning", () => {
  const frames = tabClock(false);
  const text = "Mình có thể hỗ trợ xem hồ sơ, tra căn cứ và chuẩn bị biên bản.";
  const updates = [];
  let done = 0;
  revealReply(text, (part) => updates.push(part), () => done++, frames);
  frames.tick(60000);
  assert.equal(frames.pending, 0);
  assert.equal(updates.length, 0);
  frames.setVisible(true);
  frames.tick(60010);
  assert.ok(updates.at(-1).length < text.length);
  assert.equal(done, 0);
  frames.tick(70000);
  assert.equal(updates.at(-1), text);
  assert.equal(done, 1);
  assert.equal(frames.listeners, 0);
});

test("switching tabs pauses a partial reply and excludes hidden time", () => {
  const frames = tabClock();
  const text = "Nội dung trả lời tiếp tục hiển thị khi bạn quay lại hội thoại. ".repeat(10);
  let visible = "";
  let done = 0;
  revealReply(text, (part) => { visible = part; }, () => done++, frames);
  frames.tick(0);
  frames.tick(100);
  const beforeSwitch = visible;
  frames.setVisible(false);
  frames.tick(60000);
  assert.equal(visible, beforeSwitch);
  assert.equal(done, 0);
  frames.setVisible(true);
  frames.tick(60010);
  assert.equal(visible, beforeSwitch);
  frames.tick(60110);
  assert.ok(visible.length > beforeSwitch.length && visible.length < text.length);
  frames.tick(70000);
  assert.equal(visible, text);
  assert.equal(done, 1);
});

test("skip or unmount while hidden cannot resume stale text on return", () => {
  const frames = tabClock(false);
  let updates = 0;
  let done = 0;
  const cancel = revealReply("Câu trả lời của hồ sơ trước.", () => updates++, () => done++, frames);
  cancel();
  frames.setVisible(true);
  frames.tick(100);
  assert.equal(updates, 0);
  assert.equal(done, 0);
  assert.equal(frames.pending, 0);
  assert.equal(frames.listeners, 0);
});
