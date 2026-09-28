"""Throttled Mistral embeddings client — the only place that calls the API.

DECISION 2026-09-26: one embedding model for the whole database,
``mistral-embed`` (1024-dim). Team quota: **20M TPM / 1 RPS**. This module
exists so that quota is a *provable* property instead of a hopeful one:

* :class:`RateLimiter` enforces the 1 RPS budget against wall-clock timestamps
  and takes its baseline from the persisted audit log, so a brand new process
  cannot fire two requests 50 ms apart just because the previous process exited.
* :class:`EmbeddingClient` appends **one line per HTTP request** to
  ``data/chunk/embed_api_calls.jsonl`` — before/after the call, with the token
  usage the API reported. ``scripts/verify_embeddings.py`` V7 reads that file to
  check the token spend and the request spacing instead of trusting this
  module's own arithmetic.

The client sets ``max_retries=0`` deliberately: an SDK-internal retry is an HTTP
request that this module would never log, which would make the audit log a lie.
A failed call raises; the callers (embed_legal / hybrid_search / eval) are
crash-safe and resume.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mistralai import Mistral
from mistralai.utils.retries import BackoffStrategy, RetryConfig

from src.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Disable the SDK's own retry loop. ``mistralai.utils.retries.retry`` returns
#: the request function unchanged unless the strategy is literally "backoff",
#: so "none" means exactly one HTTP request per :meth:`EmbeddingClient.embed`.
#: An unlogged internal retry would make the audit log understate both the
#: request count and the token spend.
NO_SDK_RETRIES = RetryConfig(
    strategy="none",
    backoff=BackoffStrategy(0, 0, 1.0, 0),
    retry_connection_errors=False,
)

#: Append-only audit log. Tracked in git: it is the evidence for V3 and V7.
API_CALL_LOG = PROJECT_ROOT / "data" / "chunk" / "embed_api_calls.jsonl"

#: Team quota, hard floor between two consecutive requests (plan 1: 1 RPS).
MIN_REQUEST_INTERVAL_S = 1.0

#: `purpose` values written to the log. V7's quota check counts only
#: ``corpus``: calls that populate or repopulate stored vectors.
PURPOSE_CORPUS = "corpus"
PURPOSE_QUERY = "query"
PURPOSE_PROBE = "probe"


class QuotaError(RuntimeError):
    """Raised when the API refuses the call because of rate limiting."""


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(ts: float) -> str:
    return (
        dt.datetime.fromtimestamp(ts, dt.UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def read_last_call_ts(log_path: Path = API_CALL_LOG) -> float | None:
    """Epoch seconds of the most recent logged API call, or None.

    A resumed or repeated process must inherit the previous process's spacing,
    otherwise "1 RPS" would only hold *within* a process.
    """
    if not log_path.exists():
        return None
    last: float | None = None
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # A crash can leave a partial last line; ignore it rather than
                # inventing a timestamp that is not in the log.
                continue
            if "epoch" in rec:
                last = float(rec["epoch"])
    return last


def read_call_log(log_path: Path = API_CALL_LOG) -> list[dict[str, Any]]:
    """All well-formed records of the audit log, oldest first."""
    if not log_path.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


@dataclass
class RateLimiter:
    """Sleep until at least ``min_interval`` has passed since the last call.

    ``sleep`` and ``clock`` are injectable so the pacing logic is unit-testable
    without burning a minute of wall clock.

    The wait loops instead of sleeping once. ``time.sleep()`` may return early
    (Windows timer granularity is ~15 ms), and a single-shot sleep booked from
    the pre-sleep reading is what produced a 0.987 s gap between two logged
    requests on the first full run — 1.013 RPS, over the team budget. V7 reads
    the timestamps this class is responsible for producing, so the guarantee has
    to be real, not approximately real.
    """

    min_interval: float = MIN_REQUEST_INTERVAL_S
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last_monotonic: float | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def reserve(self) -> float:
        """Block until the next call may go out; return seconds slept."""
        with self._lock:
            now = self.clock()
            if self._last_monotonic is None:
                self._last_monotonic = now
                return 0.0
            deadline = self._last_monotonic + self.min_interval
            slept = 0.0
            while True:
                remaining = deadline - self.clock()
                if remaining <= 0:
                    break
                self.sleep(remaining)
                slept += remaining
            # Book the slot *before* the request so the interval is measured
            # between request starts even if the call itself is slow.
            self._last_monotonic = self.clock()
            return slept

    def adopt(self, wall_clock_epoch: float) -> None:
        """Seed the limiter from a previous process's last request.

        ``wall_clock_epoch`` is a real timestamp from the audit log. The process
        clock is read at the same moment so the two are comparable.
        """
        elapsed = time.time() - wall_clock_epoch
        with self._lock:
            self._last_monotonic = self.clock() - max(elapsed, 0.0)


class EmbeddingClient:
    """mistral-embed wrapper: 1 RPS, audited, no hidden retries."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        log_path: Path = API_CALL_LOG,
        limiter: RateLimiter | None = None,
        client: Mistral | None = None,
    ) -> None:
        self.model = model or settings.EMBEDDING_MODEL
        self.log_path = log_path
        self._api_key = api_key if api_key is not None else settings.MISTRAL_API_KEY
        if not self._api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY is empty. B6 cannot run without it "
                "(see data_pipeline_steps/step6_7_plan.md, section 1)."
            )
        self.limiter = limiter or RateLimiter()
        self._client = client or Mistral(
            api_key=self._api_key,
            # No SDK-internal retries: every HTTP request must be loggable.
            retry_config=NO_SDK_RETRIES,
        )
        self._log_lock = threading.Lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # Continue the previous process's 1 RPS window.
        last = read_last_call_ts(self.log_path)
        self._last_logged_epoch: float | None = last
        if last is not None:
            self.limiter.adopt(last)

    # -- audit log -------------------------------------------------------
    def _append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._log_lock, open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()

    # -- public API ------------------------------------------------------
    def embed(
        self,
        inputs: list[str],
        *,
        purpose: str,
        run_id: str,
        chunk_ids: list[str] | None = None,
    ) -> list[list[float]]:
        """Embed ``inputs`` in ONE request. Returns vectors in input order."""
        if not inputs:
            return []
        if chunk_ids is not None and len(chunk_ids) != len(inputs):
            raise ValueError("chunk_ids must align with inputs")

        self.limiter.reserve()
        started = time.time()
        # Second, wall-clock guard. V7 measures the *logged* timestamps, so the
        # 1 RPS floor has to hold on that clock too — monotonic and realtime
        # can drift against each other, and only the log is evidence.
        last = self._last_logged_epoch
        if last is not None:
            while True:
                gap = MIN_REQUEST_INTERVAL_S - (started - last)
                if gap <= 0:
                    break
                time.sleep(gap)
                started = time.time()
        self._last_logged_epoch = started
        call_started = _iso(started)
        try:
            response = self._client.embeddings.create(
                model=self.model, inputs=inputs, output_dtype="float"
            )
        except Exception as exc:
            # Log the failure too: a request that consumed quota must be
            # visible in the audit even though it produced no vector.
            self._append(
                {
                    "ts": call_started,
                    "epoch": round(started, 6),
                    "run_id": run_id,
                    "purpose": purpose,
                    "model": self.model,
                    "n_inputs": len(inputs),
                    "chunk_ids": chunk_ids or [],
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                    "prompt_tokens": None,
                }
            )
            raise

        vectors = [list(item.embedding) for item in response.data]
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        self._append(
            {
                "ts": call_started,
                "epoch": round(started, 6),
                "run_id": run_id,
                "purpose": purpose,
                "model": self.model,
                "n_inputs": len(inputs),
                "chunk_ids": chunk_ids or [],
                "status": "ok",
                "prompt_tokens": prompt_tokens,
                "n_returned": len(vectors),
            }
        )
        if len(vectors) != len(inputs):
            raise RuntimeError(
                f"Mistral returned {len(vectors)} vectors for {len(inputs)} inputs"
            )
        if chunk_ids is not None:
            for cid, vec in zip(chunk_ids, vectors, strict=True):
                if len(vec) != settings.EMBEDDING_DIMENSIONS:
                    raise RuntimeError(
                        f"{self.model} returned {len(vec)} dims for {cid}, "
                        f"expected {settings.EMBEDDING_DIMENSIONS}"
                    )
        return vectors


def new_run_id(prefix: str) -> str:
    """Sortable, collision-free run id: ``corpus-20260928T101500-1a2b``."""
    stamp = _utc_now().strftime("%Y%m%dT%H%M%S")
    suffix = f"{time.monotonic_ns() % 0xFFFF:04x}"
    return f"{prefix}-{stamp}-{suffix}"
