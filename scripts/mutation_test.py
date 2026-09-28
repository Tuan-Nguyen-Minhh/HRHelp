"""Negative control for scripts/verify_db.py — proves the checks are not vacuous.

Each mutation deliberately breaks ONE thing in the seeded database (or in a
frozen source file), then runs the full verify and requires the matching check
to FAIL. State is restored afterwards by re-running the seed.

    python scripts/mutation_test.py

WARNING: this writes to the database and briefly edits a source JSON file.
It restores everything (byte-exact for the source file) and asserts the
pinned manifest still matches when it finishes. Do not run against a database
you care about.
"""
from __future__ import annotations

import json
import logging
import random
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import sqlalchemy as sa

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("mutation_test")

CHUNK_DIR = PROJECT_ROOT / "data" / "chunk"
CHUNK_FILES = [
    "chunks_BLLD.json",
    "chunks_ND145_2020.json",
    "chunks_ND283_2026.json",
]
SAMPLE_FILE = CHUNK_DIR / "chunks_BLLD.json"

_engine = sa.create_engine(settings.SYNC_DATABASE_URI)


def run_verify() -> tuple[int, list[str]]:
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "verify_db.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    failed = sorted(
        {
            line.split("[FAIL] ", 1)[1].split(":", 1)[0]
            for line in out.splitlines()
            if "[FAIL]" in line
        }
    )
    return proc.returncode, failed


def reseed() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "seed_legal.py")],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )


def sql(query: str, params: dict | None = None) -> None:
    with _engine.begin() as conn:
        conn.execute(sa.text(query), params or {})


def scalar(query: str):
    with _engine.connect() as conn:
        return conn.execute(sa.text(query)).scalar()


def one(query: str) -> str:
    with _engine.connect() as conn:
        return conn.execute(sa.text(query)).scalar()


def sampled_ids() -> list[str]:
    """Reproduce the seed=42 / 30-id sample used by V3-bis."""
    ids: list[str] = []
    for f in CHUNK_FILES:
        ids += [c["chunk_id"] for c in load_json(CHUNK_DIR / f)]
    return random.Random(42).sample(sorted(ids), 30)


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --- pick legal_chunks that make each mutation meaningful ------------------------
SAMPLE = sampled_ids()
SAMPLED = SAMPLE[0]
# Revision stamped in the database at startup. Captured, NOT hard-coded: this
# used to restore the literal '0001_legal_schema', which was correct while
# 0001 was the head but silently rewound alembic_version once B6 added
# 0003_legal_embeddings — leaving verify_db.py's V1 permanently red and this
# script unable to even reach its own baseline. Capture-and-restore survives
# every future migration without editing this file.
ALEMBIC_REVISION = one("SELECT version_num FROM alembic_version")
# every non-null parent in this dataset dangles, so to move the V3-ter count we
# must attach a dangling parent to a chunk that currently has NULL
NULL_PARENT = one(
    "SELECT chunk_id FROM legal_chunks WHERE parent_chunk_id IS NULL "
    "AND document_id='18/VBHN-VPQH' ORDER BY chunk_id LIMIT 1"
)
DANGLING_PARENT = one(
    "SELECT chunk_id FROM legal_chunks WHERE parent_chunk_id IS NOT NULL "
    "AND document_id='18/VBHN-VPQH' ORDER BY chunk_id LIMIT 1"
)

MUTATIONS: list[tuple[str, str, Callable[[], None], Callable[[], None] | None]] = [
    (
        "V1.alembic_current_eq_head",
        "alembic_version -> fake old revision",
        lambda: sql("UPDATE alembic_version SET version_num='0000_bogus'"),
        lambda: sql(
            "UPDATE alembic_version SET version_num=:r", {"r": ALEMBIC_REVISION}
        ),
    ),
    (
        "V2.BLLD.chunk_count_cross",
        "legal_documents.chunk_count lies about the real row count",
        lambda: sql(
            "UPDATE legal_documents SET chunk_count=999 WHERE document_id='18/VBHN-VPQH'"
        ),
        None,
    ),
    (
        "V2.amended_by_is_object_or_null",
        "replace SQL NULL amended_by with a JSON 'null' (JSONB none_as_null trap)",
        lambda: sql(
            "UPDATE legal_documents SET amended_by='null'::jsonb "
            "WHERE document_id='145/2020/NĐ-CP'"
        ),
        None,
    ),
    (
        "V2.ND283_2026.amended_by_sql_null",
        "store an empty object where amended_by should be SQL NULL",
        lambda: sql(
            "UPDATE legal_documents SET amended_by='{}'::jsonb "
            "WHERE document_id='283/2026/NĐ-CP'"
        ),
        None,
    ),
    (
        "V3.BLLD.count",
        "delete 1 BLLD chunk",
        lambda: sql("DELETE FROM legal_chunks WHERE chunk_id='BLLD:CI:M00:A001'"),
        None,
    ),
    (
        "V3-bis.special_columns",
        f"tamper meta.has_chapeau on a SAMPLED chunk ({SAMPLED})",
        lambda: sql(
            "UPDATE legal_chunks SET meta=jsonb_set(meta,'{has_chapeau}','true') "
            f"WHERE chunk_id='{SAMPLED}'"
        ),
        None,
    ),
    (
        "V3-bis.quoted_external_count",
        "clear is_quoted_external_text everywhere (expect exactly 20 True)",
        lambda: sql(
            "UPDATE legal_chunks SET meta=jsonb_set(meta,'{is_quoted_external_text}','false')"
        ),
        None,
    ),
    (
        "V3-ter.dangling_parent",
        f"attach a dangling parent to a NULL-parent chunk ({NULL_PARENT})",
        lambda: sql(
            f"UPDATE legal_chunks SET parent_chunk_id='NOPE:X' WHERE chunk_id='{NULL_PARENT}'"
        ),
        None,
    ),
    (
        "V3-ter.dangling_parent",
        f"null out an existing dangling parent ({DANGLING_PARENT})",
        lambda: sql(
            f"UPDATE legal_chunks SET parent_chunk_id=NULL WHERE chunk_id='{DANGLING_PARENT}'"
        ),
        None,
    ),
    (
        "V4.BLLD.count",
        "delete 1 legal_chunk_references row",
        lambda: sql(
            "DELETE FROM legal_chunk_references "
            "WHERE ref_id=(SELECT min(ref_id) FROM legal_chunk_references)"
        ),
        None,
    ),
    (
        "V4.internal_article_exists",
        "point a ref at a non-existent internal article",
        lambda: sql(
            "UPDATE legal_chunk_references SET target_doc='18/VBHN-VPQH', article=9999, "
            "target_chunk_id=NULL "
            "WHERE ref_id=(SELECT min(ref_id) FROM legal_chunk_references)"
        ),
        None,
    ),
    (
        "V4.needs_review_consistent",
        "break needs_review <-> needs_reason agreement",
        lambda: sql(
            "UPDATE legal_chunk_references SET needs_review=false WHERE needs_reason='BOUNDARY'"
        ),
        None,
    ),
    (
        "V4-bis.unresolved",
        "flag 1 ref as UNRESOLVED",
        lambda: sql(
            "UPDATE legal_chunk_references SET needs_reason='UNRESOLVED', needs_review=true "
            "WHERE ref_id=(SELECT min(ref_id) FROM legal_chunk_references)"
        ),
        None,
    ),
    (
        "V4-ter.boundary",
        "clear every BOUNDARY flag",
        lambda: sql(
            "UPDATE legal_chunk_references SET needs_reason=NULL, needs_review=false "
            "WHERE needs_reason='BOUNDARY'"
        ),
        None,
    ),
    (
        "V5.1_ND283_A044C01_to_BHXH_D28",
        "give an EXTERNAL ref a non-null target_chunk_id",
        lambda: sql(
            "UPDATE legal_chunk_references SET target_chunk_id='ND283_2026:CI:M00:A001' "
            "WHERE source_chunk_id='ND283_2026:CIII:M00:A044:C01'"
        ),
        None,
    ),
    (
        "V5.2_BLLD_D169_inbound_from_ND145",
        "delete one inbound-to-D169 ref",
        lambda: sql(
            "DELETE FROM legal_chunk_references "
            "WHERE source_chunk_id='ND145_2020:CX:M00:A089:C01:P-d1'"
        ),
        None,
    ),
    (
        "V5.5_ND283_A066_LIST_self_D7_D14",
        "delete A066's LIST_EXPANSION ref to article 14",
        lambda: sql(
            "DELETE FROM legal_chunk_references "
            "WHERE source_chunk_id='ND283_2026:CVI:M00:A066' "
            "AND rule='LIST_EXPANSION' AND article=14"
        ),
        None,
    ),
    (
        "V7.matches_pinned_manifest",
        "corrupt a frozen source JSON (damage predating this run)",
        lambda: SAMPLE_FILE.write_bytes(_ORIGINAL_BYTES + b"\n"),
        # write_bytes, NOT write_text: on Windows write_text translates \n to
        # \r\n, which would silently rewrite every line of the file.
        lambda: SAMPLE_FILE.write_bytes(_ORIGINAL_BYTES),
    ),
]


def main() -> int:
    global _ORIGINAL_BYTES
    _ORIGINAL_BYTES = SAMPLE_FILE.read_bytes()

    log.info(f"sampled chunk used by V3-bis mutation : {SAMPLED}")
    log.info(f"alembic revision captured for restore     : {ALEMBIC_REVISION}")
    log.info(f"null-parent chunk used by V3-ter       : {NULL_PARENT}")
    log.info(f"dangling-parent chunk used by V3-ter   : {DANGLING_PARENT}")
    log.info(f"resolvable parents in this dataset      : "
             f"{scalar('SELECT count(*) FROM legal_chunks c JOIN legal_chunks p ON p.chunk_id=c.parent_chunk_id')}")
    log.info("")

    code, failed = run_verify()
    log.info(f"baseline: exit={code} fails={len(failed)}")
    if code != 0 or failed:
        log.error(f"baseline must be clean before mutation testing, got {failed}")
        return 2
    log.info("")

    all_caught = True
    for expected, description, apply_mutation, undo in MUTATIONS:
        apply_mutation()
        try:
            code, failed = run_verify()
            caught = code != 0 and expected in failed
            mark = "CAUGHT" if caught else "MISSED"
            log.info(f"[{mark}] {description}")
            log.info(f"         expect '{expected}' -> fails={failed[:6]}")
            if not caught:
                all_caught = False
        finally:
            if undo is not None:
                undo()
            reseed()

    code, failed = run_verify()
    log.info("")
    log.info(f"after restore: exit={code} fails={len(failed)}")
    restored = SAMPLE_FILE.read_bytes() == _ORIGINAL_BYTES
    log.info(f"source file restored byte-exact: {restored}")

    # Post-B6 check: mutation V3.BLLD.count DELETEs a legal_chunks row and the
    # embeddings FK is ON DELETE CASCADE, while reseed() only restores
    # legal_chunks / references — the missing vector does NOT come back by
    # itself. Without this warning, running this script silently leaves V2 red
    # until someone runs embed_legal.py.
    has_emb = scalar(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='legal_chunk_embeddings')"
    )
    if has_emb:
        n_chunks = scalar("SELECT count(*) FROM legal_chunks")
        n_emb = scalar("SELECT count(*) FROM legal_chunk_embeddings")
        log.info(f"legal_chunk_embeddings rows: {n_emb} for {n_chunks} chunks")
        if n_emb != n_chunks:
            log.warning(
                f"embeddings table is short by {n_chunks - n_emb} row(s) "
                "(cascade-deleted, reseed does not restore vectors) — run "
                "python scripts/embed_legal.py before verify_embeddings.py V2"
            )
    else:
        log.info("legal_chunk_embeddings absent (pre-B6 database) — nothing to check")

    ok = all_caught and code == 0 and restored
    log.info("")
    log.info(f"MUTATION TEST: {'ALL CAUGHT' if ok else 'SOME MISSED'}")
    return 0 if ok else 1


_ORIGINAL_BYTES = b""

if __name__ == "__main__":
    sys.exit(main())
