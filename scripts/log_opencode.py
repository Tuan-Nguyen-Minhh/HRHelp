#!/usr/bin/env python3
"""
OpenCode log scanner - extracts the exact user-typed prompts from OpenCode's
local session database.

Source of truth:
    ~/.local/share/opencode/opencode.db   (SQLite; + -wal / -shm while running)
    or $XDG_DATA_HOME/opencode/opencode.db

Why this one is different from every other logger in this repo: OpenCode is the
only supported tool that stores sessions in SQLite rather than JSONL. Two
consequences drive the whole design.

**Only ``type='user'`` is a human prompt.** The table also holds ``assistant``
(4294 rows on a busy machine), ``synthetic`` (shell output, subagent results),
``system``, ``idle`` and ``model-switched``. Antigravity needed a hand-written
filter for the same reason and ended up with a fragile one; here the type column
does the work.

**Subagent sessions also store their instructions as ``type='user'``.** A
spawned subagent's single user message is the harness prompt "You are a
subagent spawned by another session. Explore the repository at ..." - text this
script must never log, because it was not typed by a student. Sessions spawned
that way carry a non-NULL ``session_v2.parent_id``, so parent_id IS NULL is the
gate. Verified: 244 user messages across all top-level P-029 sessions, none
matching harness markers, none carrying ``metadata.source``.

Schema actually read
-------------------
session_v2       id, slug, directory, parent_id, model, agent, time_created
session_message  id, session_id, type, seq, time_created, data (JSON)

``data`` for a user message: {metadata:{displayText,agent,model,comments,
attachments}, time:{created}, text, files, agents}. ``text`` is the full prompt
and is what we log; ``metadata.displayText`` differs on 8 of 429 rows and is the
rendered variant, so it is only a fallback.

Safety
------
The database is read-only (``mode=ro``) and never written, copied, or vacuumed -
OpenCode owns it and is usually running. Everything is best-effort: any failure
is swallowed, because a missing log line is a much smaller problem than a
broken editor.

Two ways in
-----------
--hook  OpenCode V2 plugin fires this from ``.opencode/plugins/ai-log`` on the
        ``session.hook("prompt")`` admission hook and hands us the payload on
        stdin. That hook is documented not to run for synthetic or shell
        messages, so the type filter is already applied upstream.
--auto  Pre-push sweep, and the path that backfills anything the hook missed.
        Scans the database itself.

Both modes mint the same ``entry_id`` (``opencode-<message id>``) so running
both, in any order, never double-logs a prompt.

Usage:
  python scripts/log_opencode.py --hook            # payload on stdin
  python scripts/log_opencode.py --auto            # default: last 24h
  python scripts/log_opencode.py --hours 72
  python scripts/log_opencode.py --all             # every session, no cutoff
  python scripts/log_opencode.py --session-id <id> # one session
  python scripts/log_opencode.py --dry-run         # preview only

Env overrides:
  OPENCODE_DB_PATH   point at a different opencode.db
  AI_LOG_DIR         where session.jsonl is written (default: .ai-log)
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VN_TZ = timezone(timedelta(hours=7))

# Message types that are NOT a human typing into a prompt box.
_NON_USER_TYPES = ("assistant", "synthetic", "system", "idle",
                   "model-switched", "location-switched")


def default_db() -> Path:
    env = os.environ.get("OPENCODE_DB_PATH")
    if env:
        return Path(env)
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "opencode" / "opencode.db"


def git(cmd: str, cwd: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            cmd.split(), shell=False, text=True, stderr=subprocess.DEVNULL,
            cwd=cwd,
        ).strip()
    except Exception:
        return ""


def repo_context(cwd: Path | None = None) -> tuple[str, str, str, str]:
    """(repo, branch, commit, student) read from the git tree at `cwd`."""
    root = cwd or Path.cwd()
    repo = git("git remote get-url origin", cwd).rstrip("/").split("/")[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return (
        repo or root.name,
        git("git rev-parse --abbrev-ref HEAD", cwd),
        git("git rev-parse --short HEAD", cwd),
        git("git config user.email", cwd)
        or os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
    )


def _normalize(p: str) -> str:
    """Lower-case, forward slashes, no trailing separator.

    The database stores Windows directories as ``C:/Users/...`` while
    ``Path.cwd()`` yields backslashes, so a raw comparison never matches.
    """
    if not p:
        return ""
    return p.strip().replace("\\", "/").rstrip("/").lower()


def _model_name(raw: str | None) -> str:
    """session_v2.model is a JSON blob like {"id":..,"variant":..}."""
    if not raw:
        return "opencode"
    try:
        j = json.loads(raw)
        if isinstance(j, dict):
            return str(j.get("id") or "opencode")
    except (json.JSONDecodeError, TypeError):
        pass
    return str(raw)


def connect(db: Path) -> sqlite3.Connection | None:
    """Read-only handle, or None if the database is absent or locked."""
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def get_logged_entry_ids(log_file: Path) -> set[str]:
    logged: set[str] = set()
    if not log_file.exists():
        return logged
    try:
        with open(log_file, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                eid = entry.get("entry_id", "")
                if eid:
                    logged.add(eid)
    except OSError:
        pass
    return logged


def build_entry(*, message_id: str, session_id: str, ts_ms: int, text: str,
                repo: str, branch: str, commit: str, student: str,
                model: str) -> dict:
    try:
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=VN_TZ).isoformat()
    except (ValueError, OSError, OverflowError):
        ts = datetime.now(VN_TZ).isoformat()

    return {
        "ts": ts,
        "tool": "opencode",
        "event": "UserPrompt",
        # Same id from --hook and --auto, so the two never double-log.
        "entry_id": f"opencode-{message_id}",
        "session_id": session_id,
        "model": model,
        "repo": repo,
        "branch": branch,
        "commit": commit,
        "student": student,
        "prompt": text,
        "response_summary": "",
    }


def iter_user_prompts(db: Path, cutoff_ms: int | None,
                      only_session: str | None, repo_dir: str | None,
                      no_repo_filter: bool):
    """Yield user prompts from top-level sessions, newest layout first.

    parent_id IS NULL is the load-bearing filter: it is what separates a student
    typing from a harness spawning a subagent.
    """
    conn = connect(db)
    if conn is None:
        return

    where = ["s.parent_id IS NULL"]
    params: dict = {}
    if only_session:
        where.append("s.id = :sid")
        params["sid"] = only_session
    if repo_dir and not no_repo_filter:
        where.append("s.directory = :dir")
        params["dir"] = repo_dir

    sql = f"""
        SELECT s.id AS session_id, s.model AS model,
               m.id AS message_id, m.time_created, m.data
        FROM session_v2 s
        JOIN session_message m ON m.session_id = s.id
        WHERE {" AND ".join(where)} AND m.type = 'user'
        ORDER BY m.time_created
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        rows = []

    for row in rows:
        if cutoff_ms is not None and row["time_created"] < cutoff_ms:
            continue
        try:
            data = json.loads(row["data"])
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue

        meta = data.get("metadata") or {}
        # Defence in depth: a user row carrying an explicit source is machine
        # authored. None of the 429 real rows do.
        if meta.get("source"):
            continue

        text = data.get("text") or meta.get("displayText") or ""
        if not isinstance(text, str) or len(text.strip()) < 2:
            continue

        ts_ms = ((data.get("time") or {}).get("created")
                 or row["time_created"] or 0)

        yield {
            "message_id": row["message_id"],
            "session_id": row["session_id"],
            "timestamp_ms": ts_ms,
            "text": text.strip(),
            "model": _model_name(row["model"]),
        }

    conn.close()


# ---------------------------------------------------------------------------
# Hook mode
# ---------------------------------------------------------------------------

def hook_mode() -> None:
    """Called by the OpenCode plugin with one JSON object on stdin.

    Contract: read stdin, do the work, never raise. A prompt admission hook
    that throws would surface inside the editor, which is far worse than a
    missing log line.
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            data = {}

        text = (data.get("text") or "").strip()
        message_id = data.get("messageID") or data.get("message_id") or ""
        session_id = data.get("sessionID") or data.get("session_id") or ""
        if not text or not message_id:
            print("{}", file=sys.stdout)
            return

        directory = data.get("directory") or ""
        root = Path(directory) if directory else Path.cwd()

        log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
        if not log_dir.is_absolute():
            log_dir = root / log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "session.jsonl"

        if f"opencode-{message_id}" in get_logged_entry_ids(log_file):
            print("{}", file=sys.stdout)
            return

        repo, branch, commit, student = repo_context(root)
        entry = build_entry(
            message_id=message_id,
            session_id=session_id,
            ts_ms=int(data.get("timestamp") or 0) or 0,
            text=text,
            repo=repo, branch=branch, commit=commit, student=student,
            model=data.get("model") or "opencode",
        )
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print("[opencode-log] Logged 1 prompt.", file=sys.stderr)
    except Exception:
        pass
    print("{}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract user prompts from OpenCode's session database "
                    "into .ai-log/session.jsonl."
    )
    parser.add_argument("--hook", action="store_true",
                        help="OpenCode plugin hook: read the payload from stdin.")
    parser.add_argument("--auto", action="store_true",
                        help="Default mode: scan the database.")
    parser.add_argument("--hours", type=int, default=24,
                        help="Window in hours when scanning (default: 24).")
    parser.add_argument("--all", action="store_true",
                        help="Ignore the time window; scan everything.")
    parser.add_argument("--session-id",
                        help="Limit to a single session id.")
    parser.add_argument("--no-repo-filter", action="store_true",
                        help="Don't filter sessions by current directory.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be logged, don't write.")
    args = parser.parse_args()

    if args.hook:
        hook_mode()
        return

    db = default_db()
    if not db.is_file():
        print(f"[opencode-log] No database at {db}.", file=sys.stderr)
        sys.exit(0)

    cutoff_ms = None
    if not args.all:
        cutoff_ms = int(
            (datetime.now(tz=VN_TZ) - timedelta(hours=args.hours)).timestamp()
            * 1000
        )

    # The database stores the directory as it was recorded at session creation,
    # so match on that exact string rather than a normalised form.
    repo_dir = None if args.no_repo_filter else str(Path.cwd())
    if repo_dir:
        conn = connect(db)
        if conn is not None:
            try:
                row = conn.execute(
                    "SELECT DISTINCT directory FROM session_v2 WHERE parent_id IS NULL"
                ).fetchall()
                stored = {r["directory"] for r in row}
                if repo_dir not in stored:
                    repo_dir = next(
                        (d for d in stored if _normalize(d) == _normalize(repo_dir)),
                        repo_dir,
                    )
            except sqlite3.Error:
                pass
            conn.close()

    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "session.jsonl"
    logged_ids = get_logged_entry_ids(log_file)

    repo, branch, commit, student = repo_context()

    new_entries: list[dict] = []
    for msg in iter_user_prompts(db, cutoff_ms, args.session_id, repo_dir,
                                 args.no_repo_filter):
        entry = build_entry(
            message_id=msg["message_id"],
            session_id=msg["session_id"],
            ts_ms=msg["timestamp_ms"],
            text=msg["text"],
            repo=repo, branch=branch, commit=commit, student=student,
            model=msg["model"],
        )
        if entry["entry_id"] in logged_ids:
            continue
        logged_ids.add(entry["entry_id"])
        new_entries.append(entry)

    if not new_entries:
        scope = "all" if args.all else f"{args.hours}h"
        repo_note = "any repo" if (args.no_repo_filter or not repo_dir) else f"repo={repo_dir}"
        print(f"[opencode-log] No new prompts ({repo_note}, window={scope}).",
              file=sys.stderr)
        sys.exit(0)

    if args.dry_run:
        print(f"\n[opencode-log] DRY RUN - would log {len(new_entries)} entries:\n")
        for e in new_entries:
            preview = e["prompt"].replace("\n", " ")[:120]
            print(f"  [{e['ts'][:19]}] {preview}")
        sys.exit(0)

    with open(log_file, "a", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"[opencode-log] Logged {len(new_entries)} prompt(s) from OpenCode.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
