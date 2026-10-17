"""Quality benchmark rejects stale captures and exposes ungrounded output."""
import asyncio
import copy
import json

from eval.answer_quality.build_dataset import build
from eval.answer_quality.evaluate import capture, digest, score_case, validate


def test_golden_rebuild_and_sources():
    from eval.answer_quality.evaluate import HERE
    dataset = build()
    validate(dataset)
    assert dataset == json.loads((HERE / 'golden.json').read_text())
    assert len(dataset['cases']) == 10
    from src.agents.handoff import CaseHandoff
    from uuid import uuid4
    for case in dataset['cases']:
        CaseHandoff.model_validate({**case['input'], 'agent_run_id': uuid4(),
                                    'missing_internal_rule': False})


def test_production_empty_evidence(tmp_path):
    dataset = build()
    dataset['cases'] = [c for c in dataset['cases'] if c['group'] == 'empty_evidence']
    records = asyncio.run(capture(dataset, tmp_path, 10))
    assert len(records) == 5
    for case, record in zip(dataset['cases'], records, strict=True):
        assert score_case(case, record)['passed'] is True
        stale = copy.deepcopy(record)
        stale['case_digest'] = 'stale'
        assert score_case(case, stale)['passed'] is None
        record['actual']['sanction_type'] = 'DISMISSAL'
        assert score_case(case, record)['passed'] is False


def test_fabricated_quotes_and_missing_facts_fail():
    case = build()['cases'][0]
    record = {'status': 'complete', 'case_digest': digest(case), 'actual': {
        'report': 'report', 'answer': 'answer', 'sanction_type': None,
        'assessment': {'operational_status': 'OK',
            'sanction_assessment': {'status': 'NEED_MORE_FACTS', 'recommended_sanction': None,
                                   'evidence': [{'chunk_id': case['input']['passages'][0]['chunk_id'], 'quote': 'fabricated quote'}]},
            'case_summary': {'facts': {**case['input']['facts'], 'contract_type': 'invented'}, 'missing_facts': []},
            'downstream_handoff': {'hr_decision_required': False, 'can_finalize': True, 'can_create_legal_ticket': True}}}}
    result = score_case(case, record)
    assert result['passed'] is False
    for key in ('citation_integrity', 'unknown_facts_not_invented', 'missing_facts_covered', 'human_review_required', 'no_automatic_legal_ticket'):
        assert result['checks'][key] is False
    record['actual']['assessment']['operational_status'] = 'LLM_FAILED'
    assert score_case(case, record)['passed'] is None
