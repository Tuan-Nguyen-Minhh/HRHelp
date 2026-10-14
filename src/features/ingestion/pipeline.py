"""Run step2 and step3 over one uploaded document, in memory.

Mirrors ``data_pipeline_steps/step3/run_step3.py::process_document`` but takes the
identity from the caller and never touches the filesystem. The chunk text and
metadata it produces are what the writer stores, so retrieval quality matches the
committed corpus.
"""

from dataclasses import dataclass

from data_pipeline_steps.step2 import step2_preprocessing as step2
from data_pipeline_steps.step3.chunking_engine import ChunkingEngine
from data_pipeline_steps.step3.cross_reference_resolver import DocScope, resolve_cross_references
from data_pipeline_steps.step3.hierarchy_parser import parse_document
from data_pipeline_steps.step3.schema import Chunk, DocumentTree

_EMBEDDED_CHAPEAU = "[EMBEDDED_CHAPEAU]"


@dataclass
class Preprocessed:
    content: str
    metadata: dict
    validation: dict


@dataclass
class Ingested:
    doc_info: dict
    tree: DocumentTree
    chunks: list[Chunk]


def preprocess(markdown: str, filename: str) -> Preprocessed:
    """Step2: clean, anchor metadata, cut boundaries, rebuild hierarchy."""
    result = step2.process_text(markdown, filename)
    return Preprocessed(
        content=result["content"],
        metadata=result["metadata"],
        validation=result["validation"],
    )


def _is_scoped_to_blld(chapeau: str | None, body_head: str) -> bool:
    probe = ((chapeau or "") + " " + (body_head or "")).lower()
    return "bộ luật lao động" in probe or "blld" in probe


def chunk(cleaned_text: str, stem: str, doc_info: dict, *, max_tokens: int | None = None) -> Ingested:
    """Step3: parse the tree, chunk it, and attach cross-references."""
    engine = ChunkingEngine() if max_tokens is None else ChunkingEngine(max_tokens=max_tokens)
    tree = parse_document(cleaned_text, stem, doc_info)
    chunks = engine.chunk_document(tree)

    tree_max = max((art.number for _, _, art in tree.all_articles()), default=0)
    eff_max = tree_max or int(doc_info.get("max_article") or 0)

    scoped_articles: set[int] = set()
    for _chapter, _section, art in tree.all_articles():
        if art.number != 1:
            continue
        chapeau = ""
        body = art.raw_body
        if body.startswith(_EMBEDDED_CHAPEAU):
            chapeau, _, body = body[len(_EMBEDDED_CHAPEAU):].partition("\n")
        if _is_scoped_to_blld(chapeau or None, body[:600]):
            scoped_articles.add(art.number)

    for item in chunks:
        scope = DocScope(
            document_id=tree.document_id,
            max_article=eff_max,
            scoped_to_blld=item.metadata.article_number in scoped_articles,
        )
        item.references = resolve_cross_references(
            item.header_context + "\n" + item.text,
            scope,
            header_len=len(item.header_context) + 1,
        )
    return Ingested(doc_info=doc_info, tree=tree, chunks=chunks)
