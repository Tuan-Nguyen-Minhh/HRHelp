"""Build draft labels from original DOCX paragraphs / authored Markdown.

This deliberately does not import the application's parser, chunker or resolver.
Source extraction is reproducible evidence, not human or legal approval.
"""

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ND145 = "nghi-dinh-145-2020-huong-dan-thi-hanh-dieu-kien-lao-dong-va-quan-he-lao-dong"
SOURCES = [
    ("BLLD", "18/VBHN-VPQH", "BO_LUAT", "data/raw/2026_131_18_VBHN-VPQH.docx", [1, 12, 118, 125]),
    ("ND145_2020", "145/2020/NĐ-CP", "NGHI_DINH", f"data/raw/{ND145}.docx", [3, 69, 70, 84]),
    ("ND283_2026", "283/2026/NĐ-CP", "NGHI_DINH", "data/raw/283_2026_ND-CP_642116.docx", [1, 2, 49, 50]),
    ("NQCT", "NQLD-HRCORP-2026", "NOI_QUY", "data/markdown/noi_quy_mau_cong_ty.md", [4, 8, 10, 13]),
]
# Manually specified positive reference expectations, grounded in quoted source
# paragraphs. No production resolver output is used to manufacture these labels.
REFS = {
    ("ND145_2020", 3): [("khoản 1 Điều 12", "18/VBHN-VPQH", 12, 1)],
    ("ND145_2020", 69): [("Điều 118", "18/VBHN-VPQH", 118, None)],
    ("ND145_2020", 70): [("khoản 6 Điều 122", "18/VBHN-VPQH", 122, 6)],
    ("ND145_2020", 84): [("khoản 9 Điều 3", "18/VBHN-VPQH", 3, 9)],
    ("NQCT", 8): [("Điều 84 Nghị định 145/2020/NĐ-CP", "145/2020/NĐ-CP", 84, None)],
}
ARTICLE = re.compile(r"^Điều\s+(\d+)\.\s*(.*)$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_lines(path):
    if path.suffix.lower() == ".docx":
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with zipfile.ZipFile(path) as archive:
            tree = ET.fromstring(archive.read("word/document.xml"))
        return [
            (i + 1, "".join(t.text or "" for t in p.findall(".//w:t", ns)).strip())
            for i, p in enumerate(tree.findall(".//w:p", ns))
        ]
    return [(i + 1, line.strip()) for i, line in enumerate(path.read_text().splitlines())]


def extract_articles(lines):
    """Independent source outline; stop when annex numbering restarts.

    Paragraph indices include empty paragraphs. Chapter/section material between
    articles is excluded from article bodies. Expected sequence is main body 1..N.
    Discontinuities raise instead of silently certifying a truncated inventory.
    """
    articles = []
    current = None
    in_main_body = False
    for index, raw in lines:
        text = re.sub(r"^#{1,6}\s+", "", raw).strip()
        heading = ARTICLE.match(text)
        if heading:
            number = int(heading[1])
            if not in_main_body:
                if number != 1:
                    continue
                in_main_body = True
            elif number == 1:
                break
            elif number != len(articles) + 1:
                raise ValueError(f"Source article sequence requires review: {number}")
            current = {"article": number, "title": heading[2].strip(), "source_index": index, "paragraphs": []}
            articles.append(current)
        elif re.match(r"^(?:Chương\s+[IVXLCDM]+|Mục\s+\d+|Phần\s+[IVXLCDM]+)\b", text, re.I):
            current = None
        elif current is not None and text:
            current["paragraphs"].append({"source_index": index, "text": raw})
    if not articles:
        raise ValueError("No independent source articles extracted")
    return articles


def build():
    documents, cases = [], []
    for code, document_id, document_type, source, selected in SOURCES:
        path = ROOT / source
        articles = extract_articles(source_lines(path))
        digest = sha256(path)
        documents.append(
            {
                "code": code,
                "document_id": document_id,
                "document_type": document_type,
                "document_form": "VAN_BAN_HOP_NHAT"
                if code == "BLLD"
                else "VAN_BAN_NOI_BO"
                if code == "NQCT"
                else "VAN_BAN_GOC",
                "source_path": source,
                "source_sha256": digest,
                "source_kind": "original_docx" if path.suffix == ".docx" else "authored_markdown",
                "chunk_file": f"chunks_{code}.json",
                "review_status": "draft",
                "reviewer": None,
                "reviewed_source_sha256": None,
                "expected_articles": [{k: a[k] for k in ("article", "title", "source_index")} for a in articles],
                "inventory_scope": "main numbered articles; annexes, tables/images and signatures are not certified",
            }
        )
        for article in articles:
            if article["article"] not in selected:
                continue
            clause, point = None, None
            spans = []
            for paragraph in article["paragraphs"]:
                text = paragraph["text"]
                cm = re.match(r"^(\d+)\.\s*(.*)", text)
                pm = re.match(r"^([a-zđ])\)\s*", text, re.I)
                if cm:
                    clause, point = int(cm[1]), None
                elif pm:
                    point = pm[1].lower()
                spans.append({**paragraph, "clause": clause, "point": point})
            references = []
            for quote, target, number, cl in REFS.get((code, article["article"]), []):
                assert any(quote in s["text"] for s in spans), (code, quote)
                references.append(
                    {"source_quote": quote, "target_doc": target, "article": number, "clause": cl, "point": None}
                )
            case = {
                "case_id": f"{code}-A{article['article']:03}",
                "document_code": code,
                "article": article["article"],
                "title": article["title"],
                "source_heading_index": article["source_index"],
                "review_status": "draft",
                "reviewer": None,
                "reviewed_source_sha256": None,
                "spans": spans,
                "references": references,
                "reference_scope": "complete_empty" if code == "BLLD" and article["article"] == 1 else "positive_only",
                "context_requirements": [],
            }
            # A short source-grounded monetary lead must be available alongside
            # the points it qualifies, even when they become separate chunks.
            if code == "ND283_2026" and article["article"] == 49:
                lead = spans[0]["text"]
                assert "10.000.000" in lead and "15.000.000" in lead
                case["context_requirements"] = [{"clause": 1, "points_only": True, "text": lead}]
            cases.append(case)
    return {
        "schema_version": 1,
        "label_status": "draft_source_derived",
        "description": "Independent source paragraphs, not copied chunk output. Human review is pending.",
        "normalization": "NFC, Markdown presentation removal, whitespace removal; numbers and accents retained",
        "documents": documents,
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "golden.json")
    parser.add_argument("--overwrite", action="store_true", help="Replace labels; discard any manual review edits")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("Dataset exists; choose another --output or explicitly --overwrite")
    data = build()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(
        f"Wrote {len(data['documents'])} documents, {len(data['cases'])} draft cases, "
        f"{sum(len(c['spans']) for c in data['cases'])} source spans to {args.output}"
    )


if __name__ == "__main__":
    main()
