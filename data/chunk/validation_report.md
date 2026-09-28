# Validation Report — Bước 3 Semantic Chunking

_Regenerate 2026-09-27 (P-029 fix): target_doc greedy + quoted external + footnote/heading/stuck-clause. So lieu tach rieng per-doc._

## BLLD: 381 chunks, 220/220 Điều bao phủ, thiếu Điều: không, vượt 1000 token: 0 []
- refs theo rule: {'EXPLICIT_SELF': 105, 'EXPLICIT': 10, 'LIST_EXPANSION': 4, 'QUOTED_EXTERNAL': 3, 'DEFAULT_SELF': 3}
- refs theo confidence: {'HIGH': 125}
- anomaly per-doc: {'OUT_OF_SEQUENCE_CLAUSE_NUMBER': 20, 'REPEATED_POINT_LETTER_C1': 20, 'REPEATED_POINT_LETTER_C4': 20}
- chunks is_quoted_external_text=true: 20

## ND283_2026: 531 chunks, 68/68 Điều bao phủ, thiếu Điều: không, vượt 1000 token: 2 ['ND283_2026:CII:M03:A036:C02:P-d', 'ND283_2026:CII:M03:A036:C03:P-b']
- refs theo rule: {'EXPLICIT': 69, 'EXPLICIT_SELF': 77, 'DEFAULT_SELF': 56, 'LIST_EXPANSION': 4, 'BOUNDARY_CHECK': 1}
- refs theo confidence: {'HIGH': 206, 'LOW': 1}
- anomaly per-doc: {'POINT_BODY_OVER_LIMIT': 2}
- chunks is_quoted_external_text=true: 0

## ND145_2020: 377 chunks, 115/115 Điều bao phủ, thiếu Điều: không, vượt 1000 token: 1 ['ND145_2020:CXI:M03:A107:C04:P-b']
- refs theo rule: {'SCOPED_CHAPEAU': 25, 'EXPLICIT': 112, 'DEFAULT_SELF': 13, 'BOUNDARY_CHECK': 2, 'EXPLICIT_SELF': 71, 'LIST_EXPANSION': 10}
- refs theo confidence: {'HIGH': 231, 'LOW': 2}
- anomaly per-doc: {'MISSING_FORMULA_IMAGE': 1, 'POINT_BODY_OVER_LIMIT': 1, 'DUPLICATE_CHAPTER_NUMBER': 17}
- chunks is_quoted_external_text=true: 0

## Toàn cục: 1289 chunk id duy nhất, trùng id: không
- chunk rỗng: không (0)
- target_doc invalid (>40/colon/newline, tru allowlist): 0 

## Anomaly flags (audit, toan cuc):
- OUT_OF_SEQUENCE_CLAUSE_NUMBER: 20 chunk (vd: BLLD:CXVII:M00:A219:C01, BLLD:CXVII:M00:A219:C02, BLLD:CXVII:M00:A219:C03)
- REPEATED_POINT_LETTER_C1: 20 chunk (vd: BLLD:CXVII:M00:A219:C01, BLLD:CXVII:M00:A219:C02, BLLD:CXVII:M00:A219:C03)
- REPEATED_POINT_LETTER_C4: 20 chunk (vd: BLLD:CXVII:M00:A219:C01, BLLD:CXVII:M00:A219:C02, BLLD:CXVII:M00:A219:C03)
- DUPLICATE_CHAPTER_NUMBER: 17 chunk (vd: ND145_2020:CXII:M00:A114:C01, ND145_2020:CXII:M00:A114:C02:P-a, ND145_2020:CXII:M00:A114:C02:P-b)
- POINT_BODY_OVER_LIMIT: 3 chunk (vd: ND283_2026:CII:M03:A036:C02:P-d, ND283_2026:CII:M03:A036:C03:P-b, ND145_2020:CXI:M03:A107:C04:P-b)
- MISSING_FORMULA_IMAGE: 1 chunk (vd: ND145_2020:CVI:M02:A056)

## Cross-reference (toan cuc):
- Theo rule: {'EXPLICIT_SELF': 253, 'EXPLICIT': 191, 'LIST_EXPANSION': 18, 'QUOTED_EXTERNAL': 3, 'DEFAULT_SELF': 72, 'BOUNDARY_CHECK': 3, 'SCOPED_CHAPEAU': 25}
- Theo confidence: {'HIGH': 562, 'LOW': 3}
- LOW cần review tay: 3 case
