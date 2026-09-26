"""Validation Buoc 3 (M6/M7): audit anomalies, cross-ref confidence, bao cao ban giao."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

STEP3_DIR = Path(__file__).resolve().parent
OUT_DIR = STEP3_DIR / "output"
CODES = ["BLLD", "ND283_2026", "ND145_2020"]
EXPECTED_ARTICLES = {"BLLD": 220, "ND283_2026": 68, "ND145_2020": 115}


def load(code: str):
    return json.loads((OUT_DIR / f"chunks_{code}.json").read_text(encoding="utf-8"))


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tokens", type=int, default=1000)
    args = ap.parse_args()
    limit = args.max_tokens
    rep: list[str] = ["# Validation Report — Bước 3 Semantic Chunking", ""]
    all_ids: set[str] = set()
    dupes: list[str] = []
    total_refs = Counter()
    total_conf = Counter()
    low_review: list[dict] = []
    anomaly_counter = Counter()
    anomaly_samples: dict[str, list[str]] = {}

    for code in CODES:
        chunks = load(code)
        for c in chunks:
            if c["chunk_id"] in all_ids:
                dupes.append(c["chunk_id"])
            all_ids.add(c["chunk_id"])
            for f in c["metadata"]["anomaly_flags"]:
                anomaly_counter[f] += 1
                anomaly_samples.setdefault(f, []).append(c["chunk_id"])
            for r in c.get("references", []):
                total_refs[r["rule"]] += 1
                total_conf[r["confidence"]] += 1
                if r["confidence"] == "LOW":
                    low_review.append({"chunk": c["chunk_id"],
                                       "text": c["text"][:160], **r})
        arts = {c["metadata"]["article_number"] for c in chunks}
        exp = EXPECTED_ARTICLES[code]
        missing = sorted(set(range(1, exp + 1)) - arts)
        over = [c["chunk_id"] for c in chunks
                if c["metadata"]["token_count"] > limit]
        rep.append(f"## {code}: {len(chunks)} chunks, "
                   f"{len(arts)}/{exp} Điều bao phủ, "
                   f"thiếu Điều: {missing or 'không'}, "
                   f"vượt {limit} token: {len(over)} {over[:5]}")

    rep += ["", f"## Toàn cục: {len(all_ids)} chunk id duy nhất, "
                f"trùng id: {dupes[:10] or 'không'}",
            "",
            "## Anomaly flags (audit):"]
    for flag, n in anomaly_counter.most_common():
        rep.append(f"- {flag}: {n} chunk (vd: "
                   f"{', '.join(anomaly_samples[flag][:3])})")
    rep += ["",
            "## Cross-reference:",
            f"- Theo rule: {dict(total_refs)}",
            f"- Theo confidence: {dict(total_conf)}",
            f"- LOW cần review tay: {len(low_review)} case"]

    (OUT_DIR / "low_confidence_refs.json").write_text(
        json.dumps(low_review, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT_DIR / "validation_report.md").write_text(
        "\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))
    print("LOW review samples:",
          [(l["chunk"], l["target_doc"], l["article"]) for l in low_review[:5]])


if __name__ == "__main__":
    main()
