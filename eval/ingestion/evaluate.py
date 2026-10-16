"""Evaluate source preservation across changing chunk boundaries, without APIs.

Inputs are the saved step-3 chunk format, also emitted by capture.py. This does
not measure legal validity, retrieval relevance, embeddings, or live DB storage.
"""

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def canonical(text):
    text = unicodedata.normalize("NFC", text or "")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\\([_*\[\]()])", r"\1", text)
    return re.sub(r"\s+", "", text)


def span_content(text):
    """List markers may move to structured metadata; actual values stay intact."""
    return re.sub(r"^(?:\d+\.|[a-zđ]\))\s*", "", text, count=1, flags=re.I)


def body_content(text):
    # The chunker writes "Điểm a)" where the source says "a)"; structural
    # identity is checked separately rather than treated as invented content.
    return canonical(
        "\n".join(
            re.sub(r"^(?:Điểm\s+)?(?:\d+\.|[a-zđ]\d*\))\s*", "", line.strip(), count=1, flags=re.I)
            for line in text.splitlines()
        )
    )


def metadata(row):
    return row.get("metadata") or {}


def assemble(rows):
    """Ordered body stream with character ownership; tolerate overlapping chunks.

    Only exact suffix/prefix overlap >=24 normalized characters is folded. Owners
    still overlap, so inherited/repeated text is attributed to all carrying rows.
    """
    result, owners = "", []
    for i, row in enumerate(rows):
        body = canonical(row.get("text", ""))
        overlap = 0
        for size in range(min(len(result), len(body), 4096), 23, -1):
            if result.endswith(body[:size]):
                overlap = size
                break
        start = len(result) - overlap
        result += body[overlap:]
        owners.append((start, start + len(body), i))
    return result, owners


def find_span(text, rows, stream, owners, article, previous=0):
    needle = canonical(span_content(text))
    if not needle:
        raise ValueError("An empty source span cannot be scored")
    options = []
    start = stream.find(needle)
    while start >= 0:
        indices = [i for left, right, i in owners if left < start + len(needle) and right > start]
        correct = sum(str(metadata(rows[i]).get("article_number")) == str(article) for i in indices)
        rank = (correct > 0, correct / max(len(indices), 1), 3, start >= previous, -abs(start - previous))
        options.append((rank, indices, start + len(needle), "body"))
        start = stream.find(needle, start + 1)
    # Chunkers can retain introductory conditions in header_context rather than
    # in body text. Count that preservation, with its actual owner and location.
    for i, row in enumerate(rows):
        blob = canonical(row.get("header_context", "") + "\n" + row.get("text", ""))
        correct = str(metadata(row).get("article_number")) == str(article)
        if needle in blob:
            options.append(((correct, int(correct), 2, False, -i), [i], previous, "context"))
        if needle in canonical(metadata(row).get("chapeau_text", "")):
            options.append(((correct, int(correct), 1, False, -i), [i], previous, "metadata_only"))
    if not options:
        return None
    _, indices, position, location = max(options, key=lambda item: item[0])
    return {"indices": indices, "position": position, "location": location}


def metadata_errors(row, document, case, span):
    md = metadata(row)
    errors = []
    for key, expected in (
        ("document_id", document["document_id"]),
        ("document_type", document["document_type"]),
        ("article_number", case["article"]),
    ):
        if str(md.get(key)) != str(expected):
            errors.append(f"{key}: expected {expected!r}, got {md.get(key)!r}")
    if document.get("document_form") and md.get("document_form") != document["document_form"]:
        errors.append(f"document_form: expected {document['document_form']!r}, got {md.get('document_form')!r}")
    if case.get("title") and canonical(md.get("article_title", "")) != canonical(case["title"]):
        errors.append("article_title differs from original heading")
    level = md.get("chunk_level")
    if level not in {"ARTICLE", "CLAUSE", "POINT"}:
        errors.append(f"invalid chunk_level: {level!r}")
    if level == "ARTICLE" and (md.get("clause_number") is not None or md.get("point_letter") is not None):
        errors.append("ARTICLE chunk must not claim a single clause/point")
    if level == "CLAUSE" and (md.get("clause_number") is None or md.get("point_letter") is not None):
        errors.append("CLAUSE chunk requires a clause and no point")
    if level == "POINT" and md.get("point_letter") is None:
        errors.append("POINT chunk requires a point")
    if level in {"CLAUSE", "POINT"} and span.get("clause") is not None:
        if str(md.get("clause_number")) != str(span["clause"]):
            errors.append(f"source clause {span['clause']} mislabeled as {md.get('clause_number')!r}")
    if level == "POINT" and span.get("point") is not None and md.get("point_letter") != span["point"]:
        errors.append(f"source point {span['point']} mislabeled as {md.get('point_letter')!r}")
    return errors


def reference_key(ref):
    return tuple(None if ref.get(k) is None else str(ref[k]) for k in ("target_doc", "article", "clause", "point"))


def evaluate_case(case, document, rows, stream, owners):
    spans, contributing, previous = [], set(), 0
    for span in case["spans"]:
        match = find_span(span["text"], rows, stream, owners, case["article"], previous)
        record = {
            "source_index": span["source_index"],
            "expected_text": span["text"],
            "preserved": match is not None,
            "chunk_ids": [],
            "metadata_errors": [],
            "context_errors": [],
        }
        if match:
            out_of_order = match["location"] == "body" and match["position"] < previous
            previous = max(previous, match["position"])
            record["found_in"] = match["location"]
            if out_of_order:
                record["context_errors"].append("source spans appear out of order in chunk bodies")
            for i in match["indices"]:
                contributing.add(i)
                row = rows[i]
                chunk_id = row["chunk_id"]
                record["chunk_ids"].append(chunk_id)
                record["metadata_errors"].extend(
                    f"{chunk_id}: {err}" for err in metadata_errors(row, document, case, span)
                )
                level = metadata(row).get("chunk_level")
                needs_marker = level == "ARTICLE" or (level == "CLAUSE" and span.get("point") is not None)
                if needs_marker and canonical(span["text"]) != canonical(span_content(span["text"])):
                    if canonical(span["text"]) not in stream and canonical(span["text"]) not in canonical(
                        row.get("header_context", "") + row.get("text", "")
                    ):
                        record["metadata_errors"].append(
                            f"{chunk_id}: list marker lost without equivalent clause/point metadata"
                        )
                if match["location"] == "metadata_only":
                    record["context_errors"].append(
                        f"{chunk_id}: source text retained only in metadata, absent from body/header"
                    )
                header = canonical(row.get("header_context", "")).casefold()
                if canonical(document["document_id"]).casefold() not in header:
                    record["context_errors"].append(f"{chunk_id}: source document missing from header")
                if canonical(f"Điều {case['article']}:").casefold() not in header:
                    record["context_errors"].append(f"{chunk_id}: source article missing from header")
                for rule in case.get("context_requirements", []):
                    applies = span.get("clause") == rule["clause"] and (
                        not rule.get("points_only") or span.get("point") is not None
                    )
                    blob = canonical(row.get("header_context", "") + "\n" + row.get("text", ""))
                    if applies and canonical(span_content(rule["text"])) not in blob:
                        record["context_errors"].append(f"{chunk_id}: required parent condition missing")
        spans.append(record)
    # Match content across the entire input document, not just article metadata:
    # a mislabeled Article 3 passage remains findable and fails metadata checks.
    article_indices = contributing | {
        i for i, row in enumerate(rows) if str(metadata(row).get("article_number")) == str(case["article"])
    }
    actual_refs = {reference_key(r) for i in article_indices for r in rows[i].get("references", [])}
    expected_refs = {reference_key(r) for r in case.get("references", [])}
    missing_refs = sorted(expected_refs - actual_refs, key=str)
    unexpected_refs = sorted(actual_refs, key=str) if case.get("reference_scope") == "complete_empty" else []
    expected_body = body_content("\n".join(s["text"] for s in case["spans"]))
    unexpected_body = []
    for i in sorted(article_indices):
        body = body_content(rows[i]["text"])
        if body and body not in expected_body:
            fragments = [
                body[b0:b1]
                for tag, _, _, b0, b1 in SequenceMatcher(None, expected_body, body, autojunk=False).get_opcodes()
                if tag in {"insert", "replace"} and b1 > b0
            ]
            if fragments:
                unexpected_body.append({"chunk_id": rows[i]["chunk_id"], "normalized_fragments": fragments})
    # Extra edges are not scored as false positives under positive-only labeling.
    passed = all(s["preserved"] and not s["metadata_errors"] and not s["context_errors"] for s in spans)
    passed = passed and not missing_refs and not unexpected_refs and not unexpected_body
    return {
        "case_id": case["case_id"],
        "review_status": case["review_status"],
        "passed": passed,
        "spans": spans,
        "contributing_chunk_ids": [rows[i]["chunk_id"] for i in sorted(contributing)],
        "expected_reference_count": len(expected_refs),
        "matched_reference_count": len(expected_refs & actual_refs),
        "missing_references": missing_refs,
        "unexpected_references": unexpected_refs,
        "unexpected_body_fragments": unexpected_body,
        "reference_scope": case.get("reference_scope"),
    }


def validate_dataset(dataset):
    if dataset.get("schema_version") != 1:
        raise ValueError("Unsupported dataset schema")
    docs = dataset.get("documents", [])
    cases = dataset.get("cases", [])
    if not docs or not cases:
        raise ValueError("Dataset must contain documents and cases")
    codes = [d["code"] for d in docs]
    ids = [c["case_id"] for c in cases]
    if len(codes) != len(set(codes)) or len(ids) != len(set(ids)):
        raise ValueError("Duplicate document code or case_id")
    for doc in docs:
        if not doc["expected_articles"] or len(doc["source_sha256"]) != 64:
            raise ValueError("Missing source inventory/hash")
    for case in cases:
        if case["document_code"] not in codes or not case.get("spans"):
            raise ValueError("Case needs a known document and nonempty source spans")
        if case.get("reference_scope") not in {"positive_only", "complete_empty"}:
            raise ValueError("Unknown reference scope")
        for span in case["spans"]:
            if not canonical(span["text"]):
                raise ValueError("Empty source span")


def evaluate(dataset, chunks_by_code, root=ROOT, capture_errors=None):
    validate_dataset(dataset)
    documents, cases, provenance_errors = [], [], []
    capture_errors = capture_errors or {}
    for document in dataset["documents"]:
        code = document["code"]
        path = root / document["source_path"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != document["source_sha256"]:
            provenance_errors.append(f"{code}: original source missing or differs from pinned SHA-256")
        rows = chunks_by_code.get(code, [])
        if not isinstance(rows, list):
            raise ValueError(f"{code}: chunks must be an array")
        for row in rows:
            if (
                not isinstance(row.get("text"), str)
                or not row.get("chunk_id")
                or not isinstance(row.get("metadata"), dict)
            ):
                raise ValueError(f"{code}: invalid chunk format; expected chunk_id/text/metadata")
        counts = Counter(r["chunk_id"] for r in rows)
        actual_articles = {str(metadata(r).get("article_number")) for r in rows}
        expected = {str(a["article"]) for a in document["expected_articles"]}
        empty = [r["chunk_id"] for r in rows if not canonical(r["text"])]
        doc = {
            "code": code,
            "chunk_count": len(rows),
            "expected_article_count": len(expected),
            "represented_article_count": len(expected & actual_articles),
            "missing_articles": sorted(expected - actual_articles, key=int),
            "unexpected_article_labels": sorted(actual_articles - expected),
            "duplicate_chunk_ids": [k for k, v in counts.items() if v > 1],
            "empty_chunks": empty,
            "capture_error": capture_errors.get(code),
            "review_status": document["review_status"],
        }
        doc["passed"] = bool(rows) and not any(
            doc[k]
            for k in (
                "missing_articles",
                "unexpected_article_labels",
                "duplicate_chunk_ids",
                "empty_chunks",
                "capture_error",
            )
        )
        documents.append(doc)
        stream, owners = assemble(rows)
        for case in dataset["cases"]:
            if case["document_code"] == code:
                cases.append(evaluate_case(case, document, rows, stream, owners))
    spans = [s for case in cases for s in case["spans"]]
    found = [s for s in spans if s["preserved"]]
    expected_refs = sum(c["expected_reference_count"] for c in cases)
    reviewed = all(
        d["review_status"] == "reviewed" and d.get("reviewer") and d.get("reviewed_source_sha256") == d["source_sha256"]
        for d in dataset["documents"]
    )
    doc_map = {d["code"]: d for d in dataset["documents"]}
    reviewed = reviewed and all(
        c["review_status"] == "reviewed"
        and c.get("reviewer")
        and c.get("reviewed_source_sha256") == doc_map[c["document_code"]]["source_sha256"]
        for c in dataset["cases"]
    )
    metrics = {
        "source_spans_total": len(spans),
        "source_spans_preserved": len(found),
        "span_preservation_rate": len(found) / len(spans),
        "retrieval_visible_span_rate": sum(s.get("found_in") in {"body", "context"} for s in spans) / len(spans),
        "preserved_spans_with_correct_metadata": sum(not s["metadata_errors"] for s in found),
        "metadata_pass_rate_on_preserved_spans": sum(not s["metadata_errors"] for s in found) / len(found)
        if found
        else None,
        "context_pass_rate_on_preserved_spans": sum(not s["context_errors"] for s in found) / len(found)
        if found
        else None,
        "expected_positive_references": expected_refs,
        "positive_reference_recall": sum(c["matched_reference_count"] for c in cases) / expected_refs
        if expected_refs
        else None,
        "cases_passed": sum(c["passed"] for c in cases),
        "cases_total": len(cases),
        "chunks_with_unexpected_body_text": sum(len(c["unexpected_body_fragments"]) for c in cases),
    }
    return {
        "status": "pass"
        if not provenance_errors and all(d["passed"] for d in documents) and all(c["passed"] for c in cases)
        else "fail",
        "label_status": "reviewed" if reviewed else "draft_pending_review",
        "scope": "source-based text/metadata/context/reference checks on chunk artifacts; no live DB or embedding verification",
        "provenance_errors": provenance_errors,
        "metrics": metrics,
        "documents": documents,
        "cases": cases,
        "not_evaluated": [
            "legal/source authority and effective-date correctness",
            "global reference precision",
            "unlabeled article body accuracy",
            "live database storage and embedding integrity",
            "semantic chunk usability beyond explicit context rules",
            "tables/images/annex completeness",
            "unsupported added header/metadata text and unlabeled article body text",
        ],
    }


def report_text_vi(text):
    """Translate presentation text while retaining machine-readable JSON keys."""
    translations = {
        "source-based text/metadata/context/reference checks on chunk artifacts; no live DB or embedding verification": "Đối chiếu nội dung, siêu dữ liệu, ngữ cảnh và dẫn chiếu với nguồn trên các tệp chunk; chưa kiểm tra cơ sở dữ liệu đang chạy hoặc vector.",
        "provided chunk artifacts": "Các tệp chunk được cung cấp.",
        "existing saved chunk artifacts; upstream stages not replayed": "Các tệp chunk đã lưu; chưa chạy lại các bước xử lý trước đó.",
        "chunking/reference replay from existing cleaned Markdown; conversion/cleaning not replayed": "Chạy lại chia đoạn và trích dẫn chiếu từ Markdown đã làm sạch; chưa chạy lại chuyển đổi hoặc làm sạch.",
        "conversion, preprocessing, chunking and logical references; no database storage or embeddings": "Chuyển đổi, tiền xử lý, chia đoạn và trích dẫn chiếu; chưa ghi cơ sở dữ liệu hoặc tạo vector.",
        "upload preprocessing/chunking from saved Markdown; original-file conversion not replayed": "Tiền xử lý và chia đoạn theo luồng tải lên từ Markdown đã lưu; chưa chạy lại chuyển đổi tệp gốc.",
        "legal/source authority and effective-date correctness": "Tính đúng đắn pháp lý, tính chính thống của nguồn và ngày hiệu lực.",
        "global reference precision": "Độ chính xác dẫn chiếu trên toàn kho.",
        "unlabeled article body accuracy": "Độ chính xác nội dung các điều chưa được gán nhãn.",
        "live database storage and embedding integrity": "Độ khớp dữ liệu lưu trong cơ sở dữ liệu đang chạy và tính toàn vẹn của vector.",
        "semantic chunk usability beyond explicit context rules": "Khả năng sử dụng ngữ nghĩa của chunk ngoài những yêu cầu ngữ cảnh cụ thể đã định nghĩa.",
        "tables/images/annex completeness": "Mức đầy đủ của bảng, hình ảnh và phụ lục.",
        "unsupported added header/metadata text and unlabeled article body text": "Nội dung được thêm vào tiêu đề hoặc siêu dữ liệu không có căn cứ, và nội dung các điều chưa được gán nhãn.",
        "source spans appear out of order in chunk bodies": "Các đoạn nguồn xuất hiện sai thứ tự trong nội dung chính của chunk.",
        "source text retained only in metadata, absent from body/header": "Nội dung nguồn chỉ còn trong siêu dữ liệu, không có trong nội dung chính hoặc tiêu đề ngữ cảnh.",
        "source document missing from header": "Tiêu đề ngữ cảnh thiếu thông tin văn bản nguồn.",
        "source article missing from header": "Tiêu đề ngữ cảnh thiếu thông tin điều nguồn.",
        "required parent condition missing": "Thiếu điều kiện hoặc câu dẫn bắt buộc được kế thừa từ cấp cha.",
        "list marker lost without equivalent clause/point metadata": "Mất số hoặc ký hiệu thứ tự nguồn mà không có siêu dữ liệu khoản/điểm tương đương.",
        "ARTICLE chunk must not claim a single clause/point": "Chunk cấp điều không được gán như chỉ chứa một khoản hoặc điểm.",
        "CLAUSE chunk requires a clause and no point": "Chunk cấp khoản phải có số khoản và để trống điểm.",
        "POINT chunk requires a point": "Chunk cấp điểm phải có ký hiệu điểm.",
        "article_title differs from original heading": "Tên điều khác tiêu đề trong nguồn gốc.",
        "original source missing or differs from pinned SHA-256": "Thiếu tệp nguồn gốc hoặc mã SHA-256 không khớp giá trị đã cố định.",
        "--require-reviewed: source/case approval is incomplete": "--require-reviewed: việc rà soát và xác nhận nguồn hoặc ca đánh giá chưa hoàn tất.",
    }
    for original, translated in translations.items():
        text = text.replace(original, translated)
    text = re.sub(r"source clause (\S+) mislabeled as (.+)", r"Khoản nguồn \1 bị gán sai thành \2", text)
    text = re.sub(r"source point (\S+) mislabeled as (.+)", r"Điểm nguồn \1 bị gán sai thành \2", text)
    text = text.replace("invalid chunk_level:", "Cấp chunk không hợp lệ:")
    return text.replace(": expected ", ": mong đợi ").replace(", got ", ", nhận được ")


def reference_text_vi(reference):
    document, article, clause, point = reference
    parts = [f"văn bản {document}", f"Điều {article}"]
    if clause is not None:
        parts.append(f"khoản {clause}")
    if point is not None:
        parts.append(f"điểm {point}")
    return ", ".join(parts)


def write_report(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Đánh giá kho tri thức và quy trình nạp dữ liệu",
        "",
        f"Kết quả: **{'Đạt' if result['status'] == 'pass' else 'Chưa đạt'}**. "
        f"Trạng thái nhãn: **{'Đã rà soát' if result['label_status'] == 'reviewed' else 'Bản nháp chờ rà soát'}**.",
        "",
        report_text_vi(result["scope"]),
        "",
        "Phạm vi thu thập đầu ra: " + report_text_vi(result.get("capture_scope", "provided chunk artifacts")),
        "",
        "Nhãn nháp chưa đủ để xác nhận độ chính xác của kho tri thức đã được chuyên gia kiểm chứng.",
        "",
        "| Chỉ số | Giá trị |",
        "| --- | --- |",
    ]
    metric_labels = {
        "source_spans_total": "Tổng số đoạn nguồn được gán nhãn",
        "source_spans_preserved": "Số đoạn nguồn được bảo toàn",
        "span_preservation_rate": "Tỷ lệ bảo toàn đoạn nguồn",
        "retrieval_visible_span_rate": "Tỷ lệ đoạn nguồn có đầy đủ nội dung trong phần truy xuất có thể đọc",
        "preserved_spans_with_correct_metadata": "Số đoạn được bảo toàn có siêu dữ liệu đúng",
        "metadata_pass_rate_on_preserved_spans": "Tỷ lệ siêu dữ liệu đạt trên các đoạn được bảo toàn",
        "context_pass_rate_on_preserved_spans": "Tỷ lệ ngữ cảnh đạt trên các đoạn được bảo toàn",
        "expected_positive_references": "Số dẫn chiếu mong đợi cần tìm",
        "positive_reference_recall": "Tỷ lệ tìm được các dẫn chiếu mong đợi",
        "cases_passed": "Số ca đạt",
        "cases_total": "Tổng số ca",
        "chunks_with_unexpected_body_text": "Số chunk có nội dung chính phát sinh hoặc bị sửa ngoài nguồn",
    }
    for key, value in result["metrics"].items():
        display = f"{value:.4f}" if isinstance(value, float) else "Không có dữ liệu" if value is None else str(value)
        lines.append(f"| {metric_labels.get(key, key)} (`{key}`) | {display} |")
    lines += ["", "## Đối chiếu nguồn", ""] + (
        [report_text_vi(e) for e in result["provenance_errors"]]
        or ["Mã băm các tệp nguồn gốc khớp với giá trị đã cố định."]
    )
    lines += [
        "",
        "## Danh mục văn bản",
        "",
        "| Văn bản | Số chunk | Số điều xuất hiện / mong đợi | Kết quả |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {d['code']} | {d['chunk_count']} | {d['represented_article_count']}/{d['expected_article_count']} | {'Đạt' if d['passed'] else 'Chưa đạt'} |"
        for d in result["documents"]
    ]
    lines += [
        "",
        "## Kết quả từng ca",
        "",
        "| Ca đánh giá | Số đoạn nguồn được bảo toàn | Kết quả |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {c['case_id']} | {sum(s['preserved'] for s in c['spans'])}/{len(c['spans'])} | {'Đạt' if c['passed'] else 'Chưa đạt'} |"
        for c in result["cases"]
    ]
    lines += ["", "## Chi tiết chưa đạt"]
    for d in result["documents"]:
        if not d["passed"]:
            lines += ["", f"### {d['code']}", ""]
            for key, label in (
                ("missing_articles", "Thiếu các điều"),
                ("unexpected_article_labels", "Nhãn điều không có trong danh mục nguồn"),
                ("duplicate_chunk_ids", "ID chunk bị trùng"),
                ("empty_chunks", "Chunk rỗng"),
            ):
                if d[key]:
                    lines.append(f"- {label}: {', '.join(map(str, d[key]))}.")
            if d["capture_error"]:
                lines.append(f"- Lỗi thu thập đầu ra: {report_text_vi(d['capture_error'])}")
            if not d["chunk_count"]:
                lines.append("- Không có chunk đầu ra để đánh giá.")
    for c in result["cases"]:
        if c["passed"]:
            continue
        lines += ["", f"### {c['case_id']}", ""]
        for s in c["spans"]:
            if not s["preserved"]:
                lines.append(
                    f"- Đoạn nguồn bị thiếu hoặc thay đổi tại vị trí {s['source_index']}: {s['expected_text'][:240]}"
                )
            lines += [f"- {report_text_vi(e)}" for e in sorted(set(s["metadata_errors"] + s["context_errors"]))]
        if c["missing_references"]:
            lines += [f"- Thiếu dẫn chiếu: {reference_text_vi(r)}." for r in c["missing_references"]]
        if c["unexpected_references"]:
            lines += [
                f"- Có dẫn chiếu ngoài mong đợi trong ca không được có dẫn chiếu: {reference_text_vi(r)}."
                for r in c["unexpected_references"]
            ]
        for extra in c["unexpected_body_fragments"]:
            lines.append(
                f"- Nội dung chính phát sinh hoặc bị sửa trong {extra['chunk_id']}: {extra['normalized_fragments']}"
            )
    lines += ["", "## Chưa được đánh giá", ""] + [f"- {report_text_vi(x)}" for x in result["not_evaluated"]]
    (output / "report.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "golden.json")
    parser.add_argument("--chunks-dir", type=Path, default=ROOT / "data/chunk")
    parser.add_argument("--output-dir", type=Path, default=HERE / "results/saved_corpus")
    parser.add_argument(
        "--require-reviewed", action="store_true", help="Fail the run unless sources/cases have been reviewed"
    )
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    validate_dataset(dataset)
    chunks = {
        d["code"]: json.loads((args.chunks_dir / d["chunk_file"]).read_text())
        if (args.chunks_dir / d["chunk_file"]).exists()
        else []
        for d in dataset["documents"]
    }
    manifest_path = args.chunks_dir / "capture.json"
    capture = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    result = evaluate(dataset, chunks, capture_errors=capture.get("errors"))
    result["capture_scope"] = capture.get("scope", "existing saved chunk artifacts; upstream stages not replayed")
    result["dataset_sha256"] = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    result["chunk_artifact_sha256"] = {
        d["code"]: hashlib.sha256((args.chunks_dir / d["chunk_file"]).read_bytes()).hexdigest()
        if (args.chunks_dir / d["chunk_file"]).exists()
        else None
        for d in dataset["documents"]
    }
    if args.require_reviewed and result["label_status"] != "reviewed":
        result["status"] = "fail"
        result["provenance_errors"].append("--require-reviewed: source/case approval is incomplete")
    write_report(result, args.output_dir)
    print(json.dumps({k: result[k] for k in ("status", "label_status", "metrics")}, ensure_ascii=False, indent=2))
    print(f"Report: {args.output_dir / 'report.md'}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
