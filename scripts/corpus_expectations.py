"""Single source of truth for corpus counts, derived from `data/chunk/*.json`.

P-029 (2026-10-03): the counts used to be four hand-maintained literals spread
across `verify_db.py`, `embed_legal.py` and `verify_embeddings.py`. Enriching
the internal regulation (NQCT 18 -> 82 Điều) silently broke all three, because
regenerating a chunk file does not touch a Python constant. That is the worst
shape for an invariant: it fails only after a legitimate data change, and the
failure message points at the wrong file.

These counts are now computed from the chunk JSONs themselves. That keeps the
tripwire intact — `verify_db.py` V7 still compares every source file against the
sha256 pins in `source_manifest.json`, so an accidental edit to a chunk file is
still caught — while removing the possibility that the *expectation* rots
silently. A count only changes when a source file changes, and a source file
change must be re-pinned deliberately with `--write-manifest`.

Derived values are independent of the database on purpose: recomputing them from
the DB would make every comparison trivially true.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHUNK_DIR = PROJECT_ROOT / "data" / "chunk"

#: Canonical corpus order (law first, then internal documents).
DOC_ORDER = ["BLLD", "ND145_2020", "ND283_2026", "NQCT"]


@dataclass(frozen=True)
class DocExpectation:
    """What one document's chunks must add up to, per its source JSON."""

    doc_code: str
    document_id: str
    document_type: str
    chunk_count: int
    article_count: int
    ref_count: int

    @property
    def chunk_file(self) -> str:
        return f"chunks_{self.doc_code}.json"

    @property
    def tree_file(self) -> str:
        return f"document_tree_{self.doc_code}.json"


def _ordered(codes: set[str]) -> list[str]:
    known = [c for c in DOC_ORDER if c in codes]
    return known + sorted(codes - set(known))


def load_expectations(chunk_dir: Path | None = None) -> dict[str, DocExpectation]:
    """Read every `chunks_*.json` and tally counts per document."""
    cdir = chunk_dir or CHUNK_DIR
    files = sorted(cdir.glob("chunks_*.json"))
    if not files:
        raise FileNotFoundError(f"khong tim thay chunks_*.json trong {cdir}")

    found: dict[str, DocExpectation] = {}
    for path in files:
        code = path.stem.removeprefix("chunks_")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload:
            raise ValueError(f"{path.name}: rong, khong co chunk nao")
        documents = {c["metadata"]["document_id"] for c in payload}
        if len(documents) != 1:
            raise ValueError(f"{path.name}: nhieu document_id {sorted(documents)}")
        document_id = documents.pop()
        found[code] = DocExpectation(
            doc_code=code,
            document_id=document_id,
            document_type=payload[0]["metadata"]["document_type"],
            chunk_count=len(payload),
            article_count=len(
                {c["metadata"]["article_number"] for c in payload}
            ),
            ref_count=sum(len(c.get("references", [])) for c in payload),
        )

    missing = [c for c in DOC_ORDER if c not in found]
    if missing:
        raise FileNotFoundError(
            f"thieu chunk file cho {missing} trong {cdir}; "
            f"co: {sorted(found)}"
        )
    return {code: found[code] for code in _ordered(set(found))}


# Module-level convenience, built once on import. Scripts import these names so
# the derivation lives in exactly one place.
EXPECTATIONS = load_expectations()
DOC_ID_TO_CODE = {e.document_id: e.doc_code for e in EXPECTATIONS.values()}
EXPECTED_CHUNK_COUNTS = {
    e.document_id: e.chunk_count for e in EXPECTATIONS.values()
}
EXPECTED_ARTICLE_COUNTS = {
    e.document_id: e.article_count for e in EXPECTATIONS.values()
}
EXPECTED_REF_COUNTS = {e.document_id: e.ref_count for e in EXPECTATIONS.values()}
TOTAL_CHUNKS = sum(EXPECTED_CHUNK_COUNTS.values())
TOTAL_REFS = sum(EXPECTED_REF_COUNTS.values())
TOTAL_DOCS = len(EXPECTATIONS)
CHUNK_FILES = [e.chunk_file for e in EXPECTATIONS.values()]
TREE_FILES = [e.tree_file for e in EXPECTATIONS.values()]

#: BOUNDARY refs are an explicit budget, not a derived number: they mean a
#: mention of "Điều N" beyond the document's own max article was resolved by
#: inference. They stay hand-pinned and reviewed, because a change here is a
#: deliberate change to cross-reference policy, not a side effect of data.
EXPECTED_BOUNDARY = 3
EXPECTED_UNRESOLVED = 0


def summary() -> str:
    rows = [
        f"  {e.doc_code:10s} {e.document_id:18s} chunks={e.chunk_count:4d} "
        f"articles={e.article_count:4d} refs={e.ref_count:4d}"
        for e in EXPECTATIONS.values()
    ]
    return "\n".join(
        [
            f"Corpus (derived from {CHUNK_DIR}):",
            *rows,
            f"  {'TOTAL':10s} {'':18s} chunks={TOTAL_CHUNKS:4d} refs={TOTAL_REFS:4d}"
            f"  docs={TOTAL_DOCS}",
        ]
    )


if __name__ == "__main__":
    print(summary())