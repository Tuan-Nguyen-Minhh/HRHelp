import { spawn } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { Plugin } from "@opencode/plugin"

/**
 * AI log hook for OpenCode.
 *
 * Fires on the `prompt` admission hook and forwards the text to
 * `scripts/log_opencode.py`, which owns the `.ai-log/session.jsonl` schema
 * shared with the Claude / Cursor / Codex / Gemini / Grok / Antigravity
 * loggers in this repo.
 *
 * Why this hook is worth wiring: OpenCode documents that `prompt` hooks do NOT
 * run for synthetic messages, shell messages, compaction controls, or move
 * controls. So by the time this fires, the text is something a human typed -
 * no filtering needed on this side. The Python side still applies its own
 * filters because `--auto` runs independently and must agree.
 *
 * Two things are load-bearing and easy to get wrong:
 *
 * 1. Nothing here may throw. This runs inside prompt admission; an exception
 *    surfaces in the editor. Every call is wrapped and failures are logged to
 *    stderr only.
 * 2. The hook is not an exactly-once boundary. Concurrent submissions can run
 *    hooks more than once, and a retry of an already-admitted message returns
 *    the original without re-running the hook. So the Python side dedupes on
 *    the message id, which is also what `--auto` uses.
 */

const here = dirname(fileURLToPath(import.meta.url))
// .opencode/plugins/ai-log -> repository root
const repoRoot = resolve(here, "..", "..", "..")
const script = resolve(repoRoot, "scripts", "log_opencode.py")

export default Plugin.define({
  id: "p029-ai-log",
  setup(ctx) {
    const directory = ctx.location?.directory ?? process.cwd()

    await ctx.session.hook("prompt", (event: any) => {
      const text: string = event?.prompt?.text ?? ""
      const messageID: string = event?.messageID ?? event?.messageId ?? ""
      if (!text.trim() || !messageID) return

      const payload = JSON.stringify({
        text,
        messageID,
        sessionID: event?.sessionID ?? "",
        directory,
        model: event?.model?.id ?? "opencode",
        timestamp: Date.now(),
      })

      try {
        const child = spawn("python", [script, "--hook"], {
          cwd: repoRoot,
          stdio: ["pipe", "ignore", "pipe"],
          shell: process.platform === "win32",
          env: { ...process.env, PYTHONIOENCODING: "utf-8" },
        })
        child.on("error", () => {})
        child.stderr?.on("data", (d: Buffer) => {
          const line = d.toString().trim()
          if (line) process.stderr.write(`[opencode-log] ${line}\n`)
        })
        child.stdin.end(payload)
      } catch {
        /* never break prompt admission over a logging failure */
      }
    })

    return () => {}
  },
})
