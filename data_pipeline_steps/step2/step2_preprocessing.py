"""
Step 2: Preprocessing pipeline for Vietnamese Legal Documents
Follows the finalized specifications in data_pipeline_steps/step2/preprocessing_plan.md
"""

import os
import sys
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def pre_clean_text(raw_text: str) -> str:
    """
    Bước 1: Làm sạch sơ bộ
    - Xóa các ký tự escape sai do MarkItDown (_ -> _)
    - Xóa BOM và zero-width space
    - Chuẩn hóa khoảng trắng nội dòng
    - Bảo toàn ngắt dòng của các Structural Markers
    """
    text = raw_text.replace("\ufeff", "")
    text = text.replace(r"\_", "_")

    # Chuẩn hóa khoảng trắng ngang (spaces, tabs) nhưng giữ ngắt dòng
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        cleaned_line = re.sub(r"[ \t]+", " ", line).rstrip()
        cleaned_lines.append(cleaned_line)

    joined = "\n".join(cleaned_lines)
    # Sua loi MarkItDown mat space sau marker Khoan/Diem + footnote dinh
    # (BLLD D7/D61, ND145 D32/D107, footnote BLLD 5 vi tri; quet deu ND283).
    joined = fix_markitdown_spacing(joined)
    return joined


def extract_metadata(text: str, filename: str) -> Dict[str, Any]:
    """
    Bước 2: Trích xuất Metadata đa chiều
    - Số hiệu văn bản
    - Hình thức văn bản (document_form)
    - Loại văn bản (document_type)
    - Tên văn bản (document_title)
    """
    metadata: Dict[str, Any] = {
        "filename": filename,
        "document_number": None,
        "document_form": "VĂN BẢN GỐC",
        "document_type": None,
        "document_title": None,
    }

    # 1. Số hiệu văn bản (hỗ trợ ký tự tiếng Việt Đ/đ và bỏ khoảng trắng thừa)
    num_match = re.search(r"^Số:\s*([0-9A-Za-zĐđ/_\-\s]+?)(?=\s{2,}|\n|\*|\||$)", text, re.MULTILINE)
    if num_match:
        raw_num = num_match.group(1).strip()
        metadata["document_number"] = re.sub(r"\s*/\s*", "/", raw_num)
    else:
        # Fallback từ tên file nếu tên file chứa số hiệu
        alt_match = re.search(r"(\d+[_\-]\d+[_\-][A-Za-z0-9_\-]+)", filename)
        if alt_match:
            metadata["document_number"] = alt_match.group(1)

    # 2. Hình thức văn bản (document_form)
    # P-029 FIX 2026-10-01 (NQCT): giu 'VAN BAN NOI BO' thay vi roi ve default GOC.
    # CHI doc dong nhan 'Hinh thuc:' (hoac header 15 dong dau), KHONG quet ca
    # body: tu 'noi bo' xuat hien trong than nghi dinh (VD 'quy che noi bo')
    # se gay nhan nham ND145/ND283 thanh van ban noi bo.
    if "VBHN" in filename or "VĂN BẢN HỢP NHẤT" in text.upper():
        metadata["document_form"] = "VĂN BẢN HỢP NHẤT"
    else:
        m_form = re.search(r"^Hình thức:\s*(.+?)\s*$", text,
                           re.MULTILINE | re.IGNORECASE)
        if m_form:
            form_val = re.sub(r"[\*\_#]", "", m_form.group(1)).strip().upper()
            if "NỘI BỘ" in form_val:
                metadata["document_form"] = "VĂN BẢN NỘI BỘ"
            elif "HỢP NHẤT" in form_val:
                metadata["document_form"] = "VĂN BẢN HỢP NHẤT"

    # 3. Loại văn bản (document_type)
    doc_types = [
        "BỘ LUẬT",
        "LUẬT",
        "NGHỊ ĐỊNH",
        "QUYẾT ĐỊNH",
        "THÔNG TƯ",
        "CHỈ THỊ",
        "NGHỊ QUYẾT",
        "NỘI QUY",
    ]
    lines = text.splitlines()
    type_line_idx = -1

    for idx, line in enumerate(lines[:80]):
        clean_upper = re.sub(r"[\*\_#]", "", line).strip().upper()
        for dt in doc_types:
            if clean_upper == dt or clean_upper.startswith(dt + " "):
                metadata["document_type"] = dt
                type_line_idx = idx
                break
        if metadata["document_type"]:
            break

    # P-029 FIX 2026-10-01 (NQCT): fallback dong nhan de 'Loai van ban: NOI QUY'
    # neu H1 khong mo dau bang loai (tranh an may nho H1 'NOI QUY LAO DONG').
    if not metadata["document_type"]:
        m_labeled = re.search(r"^Loại văn bản:\s*(.+?)\s*$", text,
                              re.MULTILINE | re.IGNORECASE)
        if m_labeled:
            labeled_val = re.sub(r"[\*\_#]", "", m_labeled.group(1)).strip().upper()
            for dt in doc_types:
                if labeled_val == dt or labeled_val.startswith(dt + " "):
                    metadata["document_type"] = dt
                    break

    # 4. Tên văn bản (document_title) với Stop Condition
    if type_line_idx != -1:
        title_parts = []
        first_line = re.sub(r"[\*\_#]", "", lines[type_line_idx]).strip()
        if len(first_line) > len(metadata["document_type"]):
            title_parts.append(first_line)

        blank_count = 0
        for line in lines[type_line_idx + 1 : type_line_idx + 40]:
            clean_l = re.sub(r"[\*\_#]", "", line).strip()
            if not clean_l:
                blank_count += 1
                if blank_count >= 2:
                    break
                continue
            blank_count = 0

            # Stop conditions
            if re.match(r"^(Số|Số hiệu):", clean_l, re.IGNORECASE):
                break
            if clean_l.startswith("Căn cứ") or clean_l.startswith("*Căn cứ"):
                break
            if re.match(r"^(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+([IVXLCDM\d]+|[0-9]+)", clean_l, re.IGNORECASE):
                break
            if re.search(r"ngày\s+\d+\s+tháng\s+\d+\s+năm", clean_l, re.IGNORECASE):
                break
            if re.match(r"^\d+\.\s+Luật\s+", clean_l, re.IGNORECASE):
                break
            if re.match(r"^(Bộ luật|Luật|Nghị định)\s+[A-Za-zÀ-ỹ\s]+số\s+\d+", clean_l, re.IGNORECASE):
                break

            title_parts.append(clean_l)

        if title_parts:
            # Nếu dòng đầu là BỘ LUẬT và dòng sau là LAO ĐỘNG
            metadata["document_title"] = " ".join(title_parts).strip()
            # Làm sạch nếu có trùng lặp
            metadata["document_title"] = re.sub(r"\s+", " ", metadata["document_title"])

    # Fallback title nếu chưa bóc được
    if not metadata["document_title"]:
        metadata["document_title"] = Path(filename).stem.replace("_", " ")

    return metadata


def _is_body_line(raw_line: str) -> bool:
    """Phân biệt body thật vs title/dòng trang trí.

    Title thường: toàn HOA, ngắn, không kết thúc bằng . ; : và không có chữ thường.
    Body thật: dòng khoản (1. / a)) hoặc câu dài có chữ thường.
    """
    clean_l = re.sub(r"[\*\_#\|]", "", raw_line).strip()
    if not clean_l:
        return False
    if re.match(r"^\s*(\d+\.|[a-z]\))\s+", clean_l):
        return True
    has_lower = any(c.islower() for c in clean_l)
    if len(clean_l) >= 10 and has_lower:
        # Câu thường có chữ thường (kể cả body test ngắn) -> coi là body.
        # Title thật trong luật đều VIẾT HOA toàn bộ nên không dính.
        # Ngoại lệ title-wrap mixed-case chỉ xuất hiện sau marker thật,
        # walk-back vẫn về đúng Chương nên an toàn.
        return True
    if len(clean_l) >= 20 and clean_l.endswith((".", ";", ":")) and has_lower:
        return True
    return False


def _find_unified_start(lines: List[str], search_from: int) -> Optional[int]:
    """Logic chung cho cả 2 trường hợp có/không heading MỤC LỤC.

    Quét các body thật theo thứ tự, chọn body đầu tiên có Chương/Phần
    bao quanh phía trước (walk-back), trả về marker Chương đó.
    Cụm marker dày đặc ở đầu file (TOC ngầm, không có chữ MỤC LỤC)
    tự động bị bỏ qua vì body đầu tiên thuộc về Chương thật.
    """
    marker_pattern = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+([IVXLCDM\d]+|[0-9]+[a-z]?[\.:]?)",
        re.IGNORECASE,
    )
    chap_pat = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG)\s+[IVXLCDM\d]+",
        re.IGNORECASE,
    )
    limit = min(search_from + 150, len(lines))
    for b in range(search_from, limit):
        clean_l = re.sub(r"[\*\_#]", "", lines[b]).strip()
        if not clean_l:
            continue
        if re.search(r"\.{4,}", lines[b]):
            continue
        if marker_pattern.match(lines[b]):
            if re.search(r"\s+\d+$", lines[b]):
                continue
            continue
        if not _is_body_line(lines[b]):
            continue
        # Body ứng viên: walk-back tối đa 30 dòng tìm Chương/Phần gần nhất
        fallback = None
        for j in range(b - 1, max(search_from - 1, b - 31), -1):
            if chap_pat.match(lines[j]):
                return j
            if fallback is None and marker_pattern.match(lines[j]):
                fallback = j
        if fallback is not None:
            # Chỉ nhận fallback Mục/Điều khi không có Chương nào trước đó
            # trong toàn vùng search (tránh nhận nhầm Điều trong TOC).
            # Kiểm tra: có Chương nào từ search_from đến b không?
            has_chap_before = any(
                chap_pat.match(lines[k]) for k in range(search_from, b)
            )
            if not has_chap_before:
                return fallback
            # Nếu đã có Chương trước đó mà walk-back gần không thấy Chương,
            # body này thuộc Chương xa hơn -> tiếp tục quét body tiếp theo
            # thay vì chốt sai vào Điều TOC. Fall through để tìm body sau.
            continue
    return None


def _find_explicit_toc_start(lines: List[str], toc_heading_idx: int) -> Optional[int]:
    """Ưu tiên heading MỤC LỤC: tìm body đầu tiên sau TOC, đi ngược về Chương/Phần gần nhất."""
    marker_pattern = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+([IVXLCDM\d]+|[0-9]+[a-z]?[\.:]?)",
        re.IGNORECASE,
    )
    chap_pat = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG)\s+[IVXLCDM\d]+",
        re.IGNORECASE,
    )
    first_body = -1
    for i in range(toc_heading_idx + 1, min(toc_heading_idx + 100, len(lines))):
        clean_l = re.sub(r"[\*\_#]", "", lines[i]).strip()
        if not clean_l:
            continue
        # Dot leader là tín hiệu TOC chắc chắn; số trang đơn lẻ (VD "text 1")
        # rất dễ nhầm với body nên chỉ skip khi dòng là marker + số trang
        if re.search(r"\.{4,}", lines[i]):
            continue
        if marker_pattern.match(lines[i]):
            # Marker TOC dạng "Chương I ... 5" (số trang cuối) -> bỏ qua
            if re.search(r"\s+\d+$", lines[i]):
                continue
            continue
        if _is_body_line(lines[i]):
            first_body = i
            break
    if first_body == -1:
        return None
    # Đi ngược từ body về marker Chương/Phần gần nhất (fallback Mục/Điều)
    fallback = None
    for j in range(first_body - 1, toc_heading_idx, -1):
        if chap_pat.match(lines[j]):
            return j
        if fallback is None and marker_pattern.match(lines[j]):
            fallback = j
    return fallback


def _is_real_content_after(lines: List[str], idx: int, max_consecutive_markers: int = 3) -> bool:
    marker_count = 0
    marker_pattern = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+([IVXLCDM\d]+|[0-9]+[a-z]?[\.:]?)",
        re.IGNORECASE,
    )
    for i in range(idx + 1, min(idx + 20, len(lines))):
        clean_l = re.sub(r"[\*\_#]", "", lines[i]).strip()
        if not clean_l:
            continue
        if marker_pattern.match(lines[i]):
            marker_count += 1
            if marker_count >= max_consecutive_markers:
                return False
        elif _is_body_line(lines[i]):
            return True
        else:
            # Dòng title trang trí (VD: **NHỮNG QUY ĐỊNH CHUNG**): bỏ qua, không kết luận vội
            continue
    return True

def detect_boundaries(lines: List[str]) -> Tuple[int, int]:
    """
    Bước 3: Xác định Biên giới Nội dung
    - Top boundary: Marker cấu trúc đầu tiên (PHẦN/CHƯƠNG/MỤC/ĐIỀU) ở đầu dòng, bypass TOC.
    - Tail boundary: Quét ngược từ EOF, nhận diện chữ ký, Nơi nhận, Phụ lục.
    """
    start_idx = 0
    end_idx = len(lines)

    # 1. Top Boundary & TOC Bypass
    marker_pattern = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+([IVXLCDM\d]+|[0-9]+[a-z]?[\.:]?)",
        re.IGNORECASE,
    )

    # 1a. Logic chung: bất kể có/không chữ MỤC LỤC, quét từ sau heading
    # (nếu có) hoặc từ đầu file, tìm body thật đầu tiên rồi đi ngược về Chương.
    toc_heading_idx = -1
    for i, line in enumerate(lines[:300]):
        clean_l = re.sub(r"[\*\_#]", "", line).strip()
        if "MỤC LỤC" in clean_l.upper():
            toc_heading_idx = i
            break
    search_from = toc_heading_idx + 1 if toc_heading_idx != -1 else 0
    unified_start = _find_unified_start(lines, search_from)
    if unified_start is not None:
        start_idx = unified_start
    else:
        # Fallback an toàn: marker đầu tiên trong 300 dòng đầu
        for i, line in enumerate(lines[:300]):
            if toc_heading_idx != -1 and i <= toc_heading_idx:
                continue
            if marker_pattern.match(line):
                start_idx = i
                break

    # 2. Tail Boundary (Quét ngược từ cuối lên)
    # Các pattern nhận diện phần kết thúc văn bản
    tail_patterns = [
        re.compile(r"^\s*\|?\s*\*{0,3}Nơi nhận:", re.IGNORECASE),
        re.compile(r"^\s*(\*{0,2}|#{0,4})\s*PHỤ LỤC\s+[IVXLCDM\d]+", re.IGNORECASE),
        re.compile(r"^\s*\|\s*\*\*VĂN PHÒNG QUỐC HỘI\*\*", re.IGNORECASE),
        re.compile(r"^\s*(\*{0,2})\s*(TM\.|KT\.|Q\.)\s+[A-ZÀ-Ỹ]", re.IGNORECASE),
        re.compile(r"^\s*\|\s*---\s*\|\s*---\s*\|\s*$", re.IGNORECASE), # Bảng chữ ký ở cuối
    ]

    # Quét trong phạm vi 2000 dòng cuối
    search_start = max(start_idx + 1, len(lines) - 2000)
    struct_pat = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+"
        r"([IVXLCDM\d]+|[0-9]+[a-z]?[\.:]?)",
        re.IGNORECASE,
    )

    def _has_content_after(idx: int) -> bool:
        """True nếu sau ứng viên tail còn heading cấu trúc thật
        (Chương/Mục/Điều) -> ứng viên này là dương tính giả, phải bỏ qua."""
        for k in range(idx + 1, min(idx + 151, len(lines))):
            if struct_pat.match(lines[k]):
                return True
        return False

    for i in range(search_start, len(lines)):
        line = lines[i]
        matched = False
        clean_l = re.sub(r"[\*\_#\|]", "", line).strip()

        for pat in tail_patterns:
            if pat.search(line):
                # Kiểm tra thêm nếu là chữ ký thì phải không có dấu chấm phẩy kết thúc câu
                if not (clean_l.endswith(".") or clean_l.endswith(";")):
                    if not _has_content_after(i):
                        end_idx = i
                        matched = True
                    break

        # Check tổ hợp: dòng nằm trong 30 dòng cuối + chữ hoa toàn bộ + không kết thúc bằng . hoặc ,
        if not matched and (len(lines) - i) <= 30:
            if clean_l and clean_l.isupper() and not clean_l.endswith((".", ",")):
                if not _has_content_after(i):
                    end_idx = i
                    matched = True

        if matched:
            break

    # Hotfix Bước 3/M1: giữ định nghĩa footnote sửa đổi của VBHN.
    # Bảng xác thực VĂN PHÒNG QUỐC HỘI nằm TRƯỚC khối footnote (dòng có
    # backlink [↑](#footnote-ref-N)); cắt ở đó sẽ làm mất vĩnh viễn 6
    # định nghĩa sửa đổi. Nếu còn footnote sau điểm cắt -> giữ tới EOF.
    if end_idx < len(lines):
        tail_probe = "\n".join(lines[end_idx:])
        if "#footnote-ref-" in tail_probe:
            end_idx = len(lines)

    return start_idx, end_idx


def _is_chapeau_line(clean_l: str) -> bool:
    """Nhan dien dong dan nhap (chapeau) de KHONG gop vao tieu de Dieu/Chuong.

    Can cu: chapeau luat VN thuong ket thuc bang ':' va chua cum dan nhu
    'nhu sau', 'bao gom', 'duoc hieu/quy dinh/xac dinh...'.
    Tieu de that khong bao gio ket thuc bang ':'.
    """
    low = clean_l.lower()
    triggers = [
        "như sau", "bao gồm:", "bao gồm", "gồm các", "cụ thể như sau",
        "được hiểu", "được quy định", "được xác định",
        "quy định như sau", "được quy định như sau",
    ]
    if any(t in low for t in triggers):
        return True
    if clean_l.strip().endswith(":"):
        return True
    return False


def fix_markitdown_spacing(text: str) -> str:
    """Sua loi MarkItDown lam mat khoang trang sau marker Khoan/Diem + footnote dinh.

    Ap dung DONG DEU cho ca 3 van ban (BLLD, ND145, ND283):
    - '2.Nguoi...' -> '2. Nguoi...' (khoan dinh)
    - 'd)Tham gia...' / 'đ)Tham gia...' -> 'd) Tham gia...' (diem dinh)
    - 'a)2[[2]](#footnote-2)Thanh...' -> 'a) [[2]](#footnote-2) Thanh...'
    - '3.3[[3]](#footnote-3)' -> '3. [[3]](#footnote-3)'
    - '**DIEU KHOAN THI HANH****6**[[6]]' -> '**DIEU KHOAN THI HANH** [[6]]'
    Doi chieu .docx goc: moi khoan la 1 paragraph rieng biet.
    """
    lines = text.splitlines()
    out: List[str] = []
    for line in lines:
        s = line
        # 1. footnote bold number truoc anchor (VD chuong XVII): '**6**[[6]]' -> ' [[6]]'
        s = re.sub(r"\*\*(\d+)\*\*(\s*)(\[\[\d+\]\]\(#footnote-\d+\))",
                   r" \3", s)
        # 2. so footnote le dan sau marker khoan/diem: 'a)2[[2]]' -> 'a)[[2]]'
        #    (bao ca '3.3[[3]]', '1.4[[4]]', '8a.5[[5]]', 'd)X[[...]]')
        s = re.sub(
            r"^(\s*(?:\d+[a-z]?\.\s*|[a-zđ]\)\s*))(\d+)\s*(\[\[\d+\]\]\(#footnote-\d+\))",
            r"\1\3", s, flags=re.IGNORECASE)
        # 3. dam bao khoang trang truoc anchor footnote: 'HANH[[6]]' -> 'HANH [[6]]'
        s = re.sub(r"(\S)(\[\[\d+\]\]\(#footnote-\d+\))", r"\1 \2", s)
        # 4. dam bao khoang trang sau anchor: ')Thanh...' -> ') Thanh...'
        s = re.sub(r"(\]\(#footnote-\d+\))([^\s])", r"\1 \2", s)
        # 5. khoan dinh dau dong thieu space: '2.Nguoi' / '2.Định kỳ' -> '2. Nguoi'
        s = re.sub(r"^(\s*\d+[a-z]?\.)([A-ZÀ-ỸÂĂĐÊÔƠƯa-zà-ỹ\[\(])",
                   r"\1 \2", s)
        # 6. diem dinh dau dong thieu space: 'đ)Tham gia' -> 'đ) Tham gia'
        s = re.sub(r"^(\s*[a-zđ]\))([^\s])", r"\1 \2", s,
                   flags=re.IGNORECASE)
        out.append(s)
    return "\n".join(out)


def _collect_wrapped_title(lines: List[str], start_j: int, is_continuation: bool = False) -> Tuple[List[str], int]:
    title_parts = []
    j = start_j
    total = len(lines)
    
    marker_pattern = re.compile(
        r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN|CHƯƠNG|MỤC|ĐIỀU)\s+([IVXLCDM\d]+|[0-9]+[a-z]?[\.:]?)",
        re.IGNORECASE,
    )
    # Nhan ca marker thieu space ('2.X', 'đ)X') de khong gop nham vao title.
    clause_start_pat = re.compile(r"^\s*(\d+[a-z]?\.\s*|[a-zđ]\)\s*)",
                                  re.IGNORECASE)

    while j < total:
        clean_l = re.sub(r"[\*\_]", "", lines[j]).strip()
        if not clean_l:
            j += 1
            continue
            
        if marker_pattern.match(lines[j]) or clause_start_pat.match(clean_l):
            break
            
        if len(title_parts) == 0 and not is_continuation:
            # Dong dau tien sau marker: neu la chapeau (ket thuc ':' / chua
            # trigger) thi KHONG gop vao title, de lai lam body.
            if _is_chapeau_line(clean_l):
                break
            title_parts.append(clean_l)
            j += 1
        else:
            # Guard chapeau: khong bao gio gop dong dan nhap vao tieu de.
            # Sua heading-merge bug (BLLD D3/D99/D120, ND145 D69/D75, quet deu ND283).
            if _is_chapeau_line(clean_l):
                break
            if len(clean_l) < 80 and not clean_l.endswith(".") \
                    and not clean_l.endswith(":"):
                title_parts.append(clean_l)
                j += 1
            else:
                break
                
    return title_parts, j


def transform_structure(content_lines: List[str]) -> List[str]:
    """
    Bước 4: Tái thiết lập Hệ thống Phân cấp
    - Gộp dòng tiêu đề đồng bộ cho cả 4 cấp (Phần, Chương, Mục, Điều)
    - Chuyển đổi thành thẻ chuẩn Markdown:
      # Phần, ## Chương, ### Mục, #### Điều
    """
    output_lines: List[str] = []
    i = 0
    total = len(content_lines)

    phan_pat = re.compile(r"^\s*(\*{0,2}|#{0,4})\s*(PHẦN\s+[IVXLCDM\d]+[\.:]?)\s*(.*?)\s*(\*{0,2})$", re.IGNORECASE)
    chuong_pat = re.compile(r"^\s*(\*{0,2}|#{0,4})\s*(CHƯƠNG\s+[IVXLCDM\d]+[\.:]?)\s*(.*?)\s*(\*{0,2})$", re.IGNORECASE)
    muc_pat = re.compile(r"^\s*(\*{0,2}|#{0,4})\s*(MỤC\s+\d+[\.:]?)\s*(.*?)\s*(\*{0,2})$", re.IGNORECASE)
    dieu_pat = re.compile(r"^\s*(\*{0,2}|#{0,4})\s*(ĐIỀU\s+\d+[a-z]?[\.:]?)\s*(.*?)\s*(\*{0,2})$", re.IGNORECASE)

    while i < total:
        line = content_lines[i]

        # 1. PHẦN (#)
        m_phan = phan_pat.match(line)
        if m_phan:
            header_prefix = m_phan.group(2).strip().rstrip(".:")
            existing_title = m_phan.group(3).strip()
            
            title_parts = [existing_title] if existing_title else []
            parts, next_i = _collect_wrapped_title(content_lines, i + 1, is_continuation=bool(existing_title))
            title_parts.extend(parts)
            
            title = f"{header_prefix}. {' '.join(title_parts).strip()}" if title_parts else header_prefix
            output_lines.append(f"\n# {title}\n")
            i = next_i
            continue

        # 2. CHƯƠNG (##)
        m_chuong = chuong_pat.match(line)
        if m_chuong:
            header_prefix = m_chuong.group(2).strip().rstrip(".:")
            existing_title = m_chuong.group(3).strip()
            
            title_parts = [existing_title] if existing_title else []
            parts, next_i = _collect_wrapped_title(content_lines, i + 1, is_continuation=bool(existing_title))
            title_parts.extend(parts)
            
            title = f"{header_prefix}. {' '.join(title_parts).strip()}" if title_parts else header_prefix
            output_lines.append(f"\n## {title}\n")
            i = next_i
            continue

        # 3. MỤC (###)
        m_muc = muc_pat.match(line)
        if m_muc:
            header_prefix = m_muc.group(2).strip().rstrip(".:")
            existing_title = m_muc.group(3).strip()
            
            title_parts = [existing_title] if existing_title else []
            parts, next_i = _collect_wrapped_title(content_lines, i + 1, is_continuation=bool(existing_title))
            title_parts.extend(parts)
            
            title = f"{header_prefix}. {' '.join(title_parts).strip()}" if title_parts else header_prefix
            output_lines.append(f"\n### {title}\n")
            i = next_i
            continue

        # 4. ĐIỀU (####)
        m_dieu = dieu_pat.match(line)
        if m_dieu:
            dieu_marker = m_dieu.group(2).strip().rstrip(".:")
            existing_title = m_dieu.group(3).strip()
            
            title_parts = [existing_title] if existing_title else []
            parts, next_i = _collect_wrapped_title(content_lines, i + 1, is_continuation=bool(existing_title))
            title_parts.extend(parts)
            
            title = f"{dieu_marker}. {' '.join(title_parts).strip()}" if title_parts else dieu_marker
            output_lines.append(f"\n#### {title}\n")
            i = next_i
            continue

        # Dòng nội dung bình thường
        output_lines.append(line)
        i += 1

    return output_lines


def validate_articles(cleaned_text: str, metadata: Dict[str, Any], raw_text: str = "",
                      full_raw_text: str = "") -> Dict[str, Any]:
    """
    Bước 5: Đánh giá tính toàn vẹn (Validation & Sanity Check)
    - Đếm số lượng #### Điều
    - So khớp số lớn nhất
    - Nhận diện các Điều bị khuyết và gán WARNING nếu không có placeholder
    - Cross-check tập số Điều trong raw ĐẦY ĐỦ (trước cắt boundary) vs final
      để bắt mất mát do tail-cut (VD NĐ283 mất Điều 66-68 mà max/total nội bộ
      vẫn khớp 65/65). Chỉ so tập số (TOC trùng không gây báo giả).
    """
    article_matches = re.findall(r"^####\s*Điều\s+(\d+)([a-z]?)", cleaned_text, re.MULTILINE | re.IGNORECASE)

    parsed_articles = []
    for num_str, suffix in article_matches:
        parsed_articles.append((int(num_str), suffix.lower()))

    total_articles = len(parsed_articles)
    max_article_num = max([num for num, _ in parsed_articles]) if parsed_articles else 0

    unique_nums = set([num for num, _ in parsed_articles])
    missing_nums = [n for n in range(1, max_article_num + 1) if n not in unique_nums]

    warnings = []
    if missing_nums:
        # Kiểm tra xem có ghi chú bãi bỏ trong văn bản không
        for missing in missing_nums:
            if not re.search(rf"Điều\s+{missing}\b[^\n]*(bãi bỏ|hết hiệu lực|lược bỏ)", cleaned_text, re.IGNORECASE):
                warnings.append(f"Điều {missing} bị khuyết mà không có placeholder bãi bỏ rõ ràng.")

    status = "SUCCESS"
    if warnings:
        status = "WARNING"


    structure_counts = {}
    if raw_text:
        raw_chuong = len(re.findall(r"^\s*(?:\*{0,2}|#{0,4})\s*CHƯƠNG\s+[IVXLCDM\d]+", raw_text, re.MULTILINE | re.IGNORECASE))
        final_chuong = len(re.findall(r"^##\s+CHƯƠNG\s+[IVXLCDM\d]+", cleaned_text, re.MULTILINE | re.IGNORECASE))
        
        raw_muc = len(re.findall(r"^\s*(?:\*{0,2}|#{0,4})\s*MỤC\s+\d+", raw_text, re.MULTILINE | re.IGNORECASE))
        final_muc = len(re.findall(r"^###\s+MỤC\s+\d+", cleaned_text, re.MULTILINE | re.IGNORECASE))
        
        raw_phan = len(re.findall(r"^\s*(?:\*{0,2}|#{0,4})\s*PHẦN\s+[IVXLCDM\d]+", raw_text, re.MULTILINE | re.IGNORECASE))
        final_phan = len(re.findall(r"^#\s+PHẦN\s+[IVXLCDM\d]+", cleaned_text, re.MULTILINE | re.IGNORECASE))

        if raw_chuong > 0 and final_chuong < raw_chuong:
            warnings.append(f"Có thể mất cấu trúc Chương: Raw={raw_chuong}, Final={final_chuong}")
            status = "WARNING"

        if raw_muc > 0 and final_muc < raw_muc:
            warnings.append(f"Có thể mất cấu trúc Mục: Raw={raw_muc}, Final={final_muc}")
            status = "WARNING"

        if raw_phan > 0 and final_phan < raw_phan:
            warnings.append(f"Có thể mất cấu trúc Phần: Raw={raw_phan}, Final={final_phan}")
            status = "WARNING"
            
        structure_counts = {
            "chuong": {"raw": raw_chuong, "final": final_chuong},
            "muc": {"raw": raw_muc, "final": final_muc},
            "phan": {"raw": raw_phan, "final": final_phan},
        }

    validation_result = {
        "structure_counts": structure_counts,
        "status": status,
        "total_parsed_articles": total_articles,
        "max_article_number": max_article_num,
        "missing_article_numbers": missing_nums,
        "warnings": warnings,
    }

    if full_raw_text:
        raw_nums = set(
            int(n) for n in re.findall(
                r"^\s*(?:\*{0,2}|#{0,4})\s*Điều\s+(\d+)",
                full_raw_text, re.MULTILINE | re.IGNORECASE)
        )
        lost = sorted(raw_nums - unique_nums)
        if lost:
            validation_result["status"] = "WARNING"
            validation_result["warnings"].append(
                f"Mất Điều sau cắt boundary (có trong raw, mất trong cleaned): {lost}"
            )
            validation_result["articles_lost_to_boundary"] = lost

    return validation_result


def process_text(raw_text: str, filename: str) -> Dict[str, Any]:
    """Chay 5 buoc tren 1 chuoi Markdown, khong dung filesystem.

    Tach khoi ``process_single_file`` de luong upload cua admin co the xu ly
    trong bo nho ma khong ghi file trung gian.
    """
    # 1. Pre-cleaning
    cleaned_step1 = pre_clean_text(raw_text)

    # 2. Metadata Anchoring
    metadata = extract_metadata(cleaned_step1, filename)

    # 3. Boundary Detection
    lines = cleaned_step1.splitlines()
    start_idx, end_idx = detect_boundaries(lines)
    content_lines = lines[start_idx:end_idx]

    # 4. Structural Transformation
    transformed_lines = transform_structure(content_lines)

    # Tạo nội dung hoàn chỉnh kèm Metadata Header
    header_block = (
        f"# {metadata['document_title']}\n\n"
        f"- **Số hiệu:** {metadata['document_number'] or 'Không có'}\n"
        f"- **Hình thức:** {metadata['document_form']}\n"
        f"- **Loại văn bản:** {metadata['document_type'] or 'Không rõ'}\n\n"
        f"---\n\n"
    )

    final_content = header_block + "\n".join(transformed_lines).strip() + "\n"

    # Don rac cuoi file: dong chi gom khung bang (| ---) sot lai sau cat tail
    # (VD '| | |' cuoi ND283). Cau tieng Viet that luon co chu cai.
    _tail_lines = final_content.splitlines()
    while _tail_lines and re.match(r"^[\s\|\-:]+$", _tail_lines[-1]):
        _tail_lines.pop()
    final_content = "\n".join(_tail_lines).strip() + "\n"

    # 5. Validation
    # So sánh cùng phạm vi: raw scope là content sau khi cắt boundary (tránh đếm trùng TOC)
    raw_scope_text = "\n".join(content_lines)
    validation = validate_articles(final_content, metadata, raw_scope_text,
                                   full_raw_text=cleaned_step1)

    return {
        "metadata": metadata,
        "validation": validation,
        "content": final_content,
    }


def process_single_file(input_path: Path, output_dir: Path) -> Dict[str, Any]:
    """
    Xử lý trọn gói 1 file Markdown qua 5 bước logic, lưu ra đĩa.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    result = process_text(raw_text, input_path.name)

    # Lưu file đã làm sạch
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / input_path.name
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result["content"])

    return {
        "metadata": result["metadata"],
        "validation": result["validation"],
        "output_file": str(output_file),
    }


def main():
    workspace_root = Path(__file__).resolve().parent.parent.parent
    input_dir = workspace_root / "data" / "markdown"
    output_dir = workspace_root / "data" / "cleaned_markdown"

    print(f"=== BẮT ĐẦU PIPELINE TIỀN XỬ LÝ (STEP 2) ===")
    print(f"Thư mục nguồn: {input_dir}")
    print(f"Thư mục đích:   {output_dir}\n")

    if not input_dir.exists():
        print(f"Lỗi: Không tìm thấy thư mục {input_dir}")
        return

    results = {}
    for md_file in sorted(input_dir.glob("*.md")):
        print(f"--> Đang xử lý: {md_file.name}...")
        try:
            res = process_single_file(md_file, output_dir)
            results[md_file.name] = res
            print(f"    [XONG] Trích xuất: {res['metadata']['document_title']}")
            print(f"    Số Điều parse được: {res['validation']['total_parsed_articles']}/{res['validation']['max_article_number']}")
            print(f"    Trạng thái: {res['validation']['status']}")
            if 'structure_counts' in res['validation'] and res['validation']['structure_counts']:
                counts = res['validation']['structure_counts']
                print(f"    Phần: {counts['phan']['final']}/{counts['phan']['raw']}, Chương: {counts['chuong']['final']}/{counts['chuong']['raw']}, Mục: {counts['muc']['final']}/{counts['muc']['raw']}")
            if res['validation']['warnings']:
                for w in res['validation']['warnings']:
                    print(f"    [CẢNH BÁO] {w}")
        except Exception as e:
            print(f"    [LỖI] {e}")

    # Lưu metadata tổng hợp
    metadata_json_path = output_dir / "metadata_summary.json"
    with open(metadata_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n=== HOÀN TẤT TOÀN BỘ TIỀN XỬ LÝ ===")
    print(f"Tổng hợp metadata & validation lưu tại: {metadata_json_path}")


if __name__ == "__main__":
    main()
