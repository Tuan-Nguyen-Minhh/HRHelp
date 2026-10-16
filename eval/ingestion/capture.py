"""Replay local ingestion stages; never write to PostgreSQL or call model APIs."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from .build_dataset import HERE, ROOT, SOURCES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "upload"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--use-saved-markdown",
        action="store_true",
        help="Upload replay starts from saved Markdown instead of converting original DOCX",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.use_saved_markdown and args.mode != "upload":
        parser.error("--use-saved-markdown applies only to --mode upload")
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.resolve() == (ROOT / "data/chunk").resolve():
        parser.error("Choose a capture directory; canonical data/chunk must not be overwritten")
    if args.output_dir.exists() and any(args.output_dir.iterdir()) and not args.overwrite:
        parser.error("Capture directory is not empty; choose another or explicitly --overwrite")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Mistral's bundled tokenizer is local. Never download a fallback tokenizer.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    scope = {
        "offline": "chunking/reference replay from existing cleaned Markdown; conversion/cleaning not replayed",
        "upload": "conversion, preprocessing, chunking and logical references; no database storage or embeddings",
    }[args.mode]
    if args.use_saved_markdown:
        scope = "upload preprocessing/chunking from saved Markdown; original-file conversion not replayed"
    manifest = {
        "mode": args.mode,
        "scope": scope,
        "documents": {},
        "errors": {},
        "golden_labels": str(HERE / "golden.json"),
    }
    for code, _, _, source, _ in SOURCES:
        original = ROOT / source
        output = args.output_dir / f"chunks_{code}.json"
        previous_dir = Path.cwd()
        try:
            # Optional converter/tokenizer packages may create local cache or
            # session files. Confine those side effects to the capture directory.
            os.chdir(args.output_dir)
            if args.mode == "offline":
                from data_pipeline_steps.step3.chunking_engine import ChunkingEngine
                from data_pipeline_steps.step3.run_step3 import process_document

                input_path = ROOT / "data/cleaned_markdown" / (original.stem + ".md")
                stats = process_document(original.stem, args.output_dir, ChunkingEngine(), verbose=False)
            else:
                from src.features.ingestion import converter, metadata, pipeline

                input_path = ROOT / "data/markdown" / (original.stem + ".md") if args.use_saved_markdown else original
                markdown = converter.to_markdown(input_path.name, input_path.read_bytes())
                prep = pipeline.preprocess(markdown, original.name)
                info = metadata.build_doc_info(prep.metadata, original.stem, set())
                result = pipeline.chunk(prep.content, original.stem, info)
                rows = [c.to_dict() for c in result.chunks]
                output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
                stats = {"chunks": len(rows), "extracted_metadata": prep.metadata, "validation": prep.validation}
            manifest["documents"][code] = {
                "input_path": str(input_path.relative_to(ROOT)),
                "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                "stats": stats,
            }
            print(f"{code}: {stats.get('chunks')} chunks")
        except Exception as exc:
            manifest["errors"][code] = f"{type(exc).__name__}: {str(exc)[:500]}"
            output.write_text("[]\n")  # Prevent an earlier capture from masquerading as a successful replay.
            print(f"{code}: FAILED ({type(exc).__name__})")
        finally:
            os.chdir(previous_dir)
        (args.output_dir / "capture.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 1 if manifest["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
