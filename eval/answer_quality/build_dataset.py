"""Build draft quality labels from existing, source-pinned case fixtures."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'eval/case_assessment'


def build():
    metadata = json.loads((SOURCE / 'source_metadata.json').read_text())
    rows = json.loads((SOURCE / 'ragas_dataset.json').read_text())
    snapshot = json.loads((SOURCE / 'policy_snapshot.json').read_text())
    passages = {p['chunk_id']: p for p in snapshot['passages']}
    answers = [
        'Ghi nhận 5 ngày vắng mặt trong 30 ngày. Chưa đủ căn cứ chốt sa thải: lý do việc gia đình cần được xác minh, không tự coi là lý do chính đáng hoặc không chính đáng.',
        'Ghi nhận 4 lần đi muộn, tổng 90 phút. Snapshot quy định ngưỡng quá 3 lần; chưa xác định lần đầu vi phạm và lý do đi muộn nên chưa đủ căn cứ chốt mức xử lý.',
        'Báo cáo có hạn 17 giờ ngày 09/10/2026, được gửi lúc 10 giờ ngày 13/10/2026. Chậm nộp chưa chứng minh lỗi chủ quan; cần xác minh nguyên nhân và hồ sơ trước khi chọn mức xử lý.',
        'Ghi nhận rời vị trí 70 phút, vượt ngưỡng 60 phút trong snapshot. Cần xác minh lịch nghỉ và lịch sử vi phạm, chưa đủ căn cứ chốt mức xử lý.',
        'Có nghĩa vụ tuân thủ PPE nhưng chưa có căn cứ ánh xạ hành vi này sang mức kỷ luật cụ thể. Việc khắc phục không xóa sự việc đã xảy ra; cần kiểm tra hồ sơ đào tạo và quy định áp dụng.',
    ]
    cases = []
    for meta, row in zip(metadata['cases'], rows, strict=True):
        evidence = []
        for key in meta['reference_evidence_ids']:
            p = passages[key]
            evidence.append({k: p[k] for k in ('chunk_id', 'policy_version_id', 'content', 'article', 'clause', 'point', 'policy_type', 'policy_code', 'policy_name')})
            evidence[-1].update(score=1.0, origin='golden_fixture', section_title=p.get('chunk_metadata', {}).get('section_title') or '')
        base = {
            'case_id': meta['case_id'], 'group': 'source_case', 'review_status': 'draft',
            'source': {'path': 'golden_dataset/' + Path(meta['source_file']).name, 'sha256': meta['source_sha256']},
            'input': {'query': row['user_input'], 'description': meta['model_description'],
                      'family': meta['family'], 'incident_date': meta['incident_date'],
                      'facts': meta['source_known_facts'], 'passages': evidence},
            'expected': {'assessment_status': meta['expected_assessment_status_with_reference_contexts'],
                         'sanction_type': meta['expected_sanction_type'],
                         'unknown_facts': meta['unknown_facts'], 'checks': meta['expected_checks']},
            'reference_report': row['reference'],
            'reference_answer': answers[meta['row_index']] + ' Cần bổ sung các tình tiết chưa xác định và để HR rà soát trước khi ra quyết định.',
        }
        cases.append(base)
        empty = json.loads(json.dumps(base))
        empty.update(case_id=meta['case_id'] + '-EMPTY', group='empty_evidence')
        empty['input']['passages'] = []
        empty['expected'] = {'assessment_status': None, 'sanction_type': None, 'unknown_facts': [],
                             'checks': ['Không chọn mức kỷ luật khi không có chứng cứ truy xuất.']}
        empty['reference_answer'] = 'Chưa có đủ căn cứ để đưa ra mức xử lý vì không truy xuất được dữ liệu cho vụ việc.'
        empty['reference_report'] = empty['reference_answer']
        cases.append(empty)
    return {'schema_version': 1, 'review_status': 'draft',
            'scope': 'fixed_evidence_component; not retrieval or end-to-end chat',
            'provenance': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [SOURCE / 'source_metadata.json', SOURCE / 'ragas_dataset.json', SOURCE / 'policy_snapshot.json']},
            'cases': cases}


if __name__ == '__main__':
    (HERE / 'golden.json').write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
