"""Validation Buoc 3 (M6/M7) — UPDATED 2026-09-27 (P-029).

- So lieu tach rieng theo tung van ban (BLLD/ND145/ND283) cho flags
  CLAUSE_NUMBER_GAP, OUT_OF_SEQUENCE_CLAUSE_NUMBER.
- Kiem tra target_doc hop le: khong dai >40 (tru KNOWN_LONG allowlist),
  khong chua newline/colon.
- Bao cao cross-ref theo rule/confidence per-doc + toan cuc.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

STEP3_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = STEP3_DIR.parent.parent
OUT_DIR = WORKSPACE_ROOT / "data" / "chunk"
CODES = ["BLLD", "ND283_2026", "ND145_2020"]
EXPECTED_ARTICLES = {"BLLD": 220, "ND283_2026": 68, "ND145_2020": 115}
KNOWN_LONG_ALLOW = {
    "Luật Người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng",
}


def load(code: str):
    return json.loads((OUT_DIR / f"chunks_{code}.json").read_text(encoding="utf-8"))


def is_valid_target(doc: str) -> bool:
    if "\n" in doc or ":" in doc:
        return False
    if doc in KNOWN_LONG_ALLOW:
        return True
    return len(doc) <= 40 and len(doc) > 0


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tokens", type=int, default=1000)
    args = ap.parse_args()
    limit = args.max_tokens
    rep: list[str] = ["# Validation Report — Bước 3 Semantic Chunking", ""]
    rep.append("_Regenerate 2026-09-27 (P-029 fix): target_doc greedy + quoted external + "
               "footnote/heading/stuck-clause. So lieu tach rieng per-doc._")
    rep.append("")
    all_ids: set[str] = set()
    dupes: list[str] = []
    total_refs = Counter()
    total_conf = Counter()
    low_review: list[dict] = []
    anomaly_counter = Counter()
    anomaly_samples: dict[str, list[str]] = {}
    per_doc_anomaly: dict[str, Counter] = {c: Counter() for c in CODES}
    per_doc_refs: dict[str, Counter] = {c: Counter() for c in CODES}
    per_doc_conf: dict[str, Counter] = {c: Counter() for c in CODES}
    invalid_targets: list[dict] = []
    empty_chunks: list[str] = []
    quoted_counts: dict[str, int] = {}

    for code in CODES:
        chunks = load(code)
        quoted_counts[code] = sum(
            1 for c in chunks if c["metadata"].get("is_quoted_external_text"))
        for c in chunks:
            if not (c.get("text") or "").strip():
                empty_chunks.append(c["chunk_id"])
            if c["chunk_id"] in all_ids:
                dupes.append(c["chunk_id"])
            all_ids.add(c["chunk_id"])
            for f in c["metadata"]["anomaly_flags"]:
                anomaly_counter[f] += 1
                per_doc_anomaly[code][f] += 1
                anomaly_samples.setdefault(f, []).append(c["chunk_id"])
            for r in c.get("references", []):
                total_refs[r["rule"]] += 1
                per_doc_refs[code][r["rule"]] += 1
                total_conf[r["confidence"]] += 1
                per_doc_conf[code][r["confidence"]] += 1
                if not is_valid_target(r["target_doc"]):
                    invalid_targets.append({"chunk": c["chunk_id"], **r})
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
        rep.append(f"- refs theo rule: {dict(per_doc_refs[code])}")
        rep.append(f"- refs theo confidence: {dict(per_doc_conf[code])}")
        rep.append(f"- anomaly per-doc: {dict(per_doc_anomaly[code])}")
        rep.append(f"- chunks is_quoted_external_text=true: {quoted_counts[code]}")
        rep.append("")

    rep += [f"## Toàn cục: {len(all_ids)} chunk id duy nhất, "
            f"trùng id: {dupes[:10] or 'không'}",
            f"- chunk rỗng: {empty_chunks[:10] or 'không'} ({len(empty_chunks)})",
            f"- target_doc invalid (>40/colon/newline, tru allowlist): "
            f"{len(invalid_targets)} {invalid_targets[:5] or ''}",
            "",
            "## Anomaly flags (audit, toan cuc):"]
    for flag, n in anomaly_counter.most_common():
        rep.append(f"- {flag}: {n} chunk (vd: "
                   f"{', '.join(anomaly_samples[flag][:3])})")
    rep += ["",
            "## Cross-reference (toan cuc):",
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
    if invalid_targets:
        print("INVALID targets:", invalid_targets[:5])


if __name__ == "__main__":
    main()
