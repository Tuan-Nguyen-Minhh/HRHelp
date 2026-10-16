"""Opt-in live smoke evaluation, using synthetic text and the configured provider.

Run from the repo root: PYTHONPATH=. .venv/bin/python eval/routing/run.py --live
This calls paid model APIs. It does not connect to PostgreSQL or change any case.
"""

import argparse
import asyncio
import json
from pathlib import Path

from src.features.clarify.model.general_chat import answer_general_chat
from src.features.clarify.model.intent import route_turn


async def run(args):
    root = Path(__file__).parent
    cases = json.loads((root / "cases.json").read_text())[: args.limit]
    records = []
    for case in cases:
        state = {
            "semantic": True,
            "latest_user_message": case["message"],
            "turn_context": "Synthetic test case. Stored status: ANALYZED. No real employee information.",
            "case_code": "SYNTHETIC-EVAL",
            "stored": {},
        }
        result = await route_turn(state)
        record = {
            "message": case["message"],
            "expected": case["routes"],
            "initial": result.initial_decision.get("route"),
            "route": result.decision.route.value,
            "recheck": result.recheck_status,
            "rule_ids": [h["rule_id"] for h in result.rule_matches],
            "fallback": result.fallback_kind.value,
            "latency_ms": result.latency_ms,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "pass": result.decision.route.value in case["routes"] and not result.fallback,
        }
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    if args.chat:
        response = await answer_general_chat("Hôm nay ăn gì cho nhanh gọn?", {"actor_id": "synthetic-eval"})
        chat = {
            "safety_action": response.safety_action,
            "text": response.text,
            "pass": response.safety_action == "allow",
        }
    else:
        chat = None
    report = {
        "scope": "synthetic smoke, not a production accuracy estimate",
        "cases": records,
        "chat": chat,
        "passed": sum(row["pass"] for row in records),
        "total": len(records),
    }
    output = root / "results.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "total": len(records), "chat": chat}, ensure_ascii=False))
    return all(row["pass"] for row in records) and (chat is None or chat["pass"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Authorize configured model API calls")
    parser.add_argument(
        "--chat", action="store_true", help="Also test input moderation, generation and output moderation"
    )
    parser.add_argument("--limit", type=int, default=10)
    arguments = parser.parse_args()
    if not arguments.live:
        parser.error("--live is required; this smoke test calls the configured model provider")
    raise SystemExit(0 if asyncio.run(run(arguments)) else 1)
