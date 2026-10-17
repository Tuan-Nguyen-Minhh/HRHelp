"""Capture the production answer component and score draft golden expectations."""
import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def validate(dataset):
    if dataset.get('schema_version') != 1 or not dataset.get('cases'):
        raise ValueError('Expected a nonempty schema_version=1 dataset')
    ids = [c['case_id'] for c in dataset['cases']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case IDs')
    for path, sha in dataset['provenance'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != sha:
            raise ValueError(f'Source changed: {path}')
    for case in dataset['cases']:
        source = ROOT / case['source']['path']
        if hashlib.sha256(source.read_bytes()).hexdigest() != case['source']['sha256']:
            raise ValueError(f"Source changed: {case['case_id']}")
        for key in ('reference_report', 'reference_answer'):
            if not isinstance(case[key], str) or not case[key].strip():
                raise ValueError(f'Empty {key}')
        if case['group'] not in {'source_case', 'empty_evidence'}:
            raise ValueError('Unknown case group')
        if (case['group'] == 'empty_evidence') != (not case['input']['passages']):
            raise ValueError('Case group and evidence disagree')


def evidence_refs(value):
    if isinstance(value, dict):
        if 'chunk_id' in value and 'quote' in value:
            yield value
        for child in value.values():
            yield from evidence_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from evidence_refs(child)


def score_case(case, record):
    result = {'case_id': case['case_id'], 'group': case['group'], 'passed': None, 'checks': {}}
    if not record or record.get('case_digest') != digest(case) or record.get('status') != 'complete':
        return {**result, 'status': 'missing_or_error'}
    actual = record['actual']
    assessment = actual.get('assessment')
    if assessment and assessment.get('operational_status') != 'OK':
        return {**result, 'status': 'operational_failure'}
    checks = result['checks']
    checks['report_nonempty'] = bool(actual.get('report', '').strip())
    checks['answer_nonempty'] = bool(actual.get('answer', '').strip())
    checks['sanction_correct'] = actual.get('sanction_type') == case['expected']['sanction_type']
    if case['group'] == 'empty_evidence':
        checks['no_assessment_without_evidence'] = assessment is None
        checks['empty_evidence_answer'] = actual.get('answer') == case['reference_answer']
    else:
        checks['assessment_present'] = isinstance(assessment, dict)
        assessment = assessment or {}
        checks['assessment_status'] = assessment.get('sanction_assessment', {}).get('status') == case['expected']['assessment_status']
        checks['assessment_sanction'] = assessment.get('sanction_assessment', {}).get('recommended_sanction') == case['expected']['sanction_type']
        known = assessment.get('case_summary', {}).get('facts', {})
        checks['confirmed_facts_preserved'] = all(known.get(k) == v for k, v in case['input']['facts'].items())
        checks['unknown_facts_not_invented'] = not any(known.get(k) for k in case['expected']['unknown_facts'])
        missing = set(assessment.get('case_summary', {}).get('missing_facts', []))
        checks['missing_facts_covered'] = set(case['expected']['unknown_facts']) <= missing
        handoff = assessment.get('downstream_handoff', {})
        checks['human_review_required'] = handoff.get('hr_decision_required') is True and handoff.get('can_finalize') is False
        checks['no_automatic_legal_ticket'] = handoff.get('can_create_legal_ticket') is False
        passages = {p['chunk_id']: p for p in case['input']['passages']}
        refs = list(evidence_refs(assessment))
        checks['citations_present'] = bool(refs)
        checks['citation_integrity'] = all(
            r['chunk_id'] in passages and bool(r['quote'].strip()) and
            r['quote'] in passages[r['chunk_id']].get('section_title' if r.get('source') == 'HEADING' else 'content', '')
            for r in refs)
    result.update(status='scored', passed=all(checks.values()))
    return result


async def capture(dataset, output, timeout):
    from src.agents.handoff import CaseHandoff
    from src.features.answer.model.agent import build_recommend_agent
    agent = build_recommend_agent()
    records = []
    for case in dataset['cases']:
        print('Capturing ' + case['case_id'], flush=True)
        data = dict(case['input'])
        data.update(agent_run_id=uuid4(), missing_internal_rule=not any(p['policy_type'] == 'INTERNAL_RULE' for p in data['passages']),
                    retrieval='hybrid' if data['passages'] else 'empty',
                    fact_lines=[f'{k}: {v}' for k, v in data['facts'].items()])
        record = {'case_id': case['case_id'], 'case_digest': digest(case), 'scope': dataset['scope'],
                  'captured_at': datetime.now(timezone.utc).isoformat()}
        try:
            result = await asyncio.wait_for(agent.ainvoke({'handoff': CaseHandoff.model_validate(data)}), timeout)
            draft = result['draft']
            record.update(status='complete', actual={'report': draft.prose, 'answer': draft.chat_message,
                          'sanction_type': draft.decision.sanction_type,
                          'assessment': draft.assessment.model_dump(mode='json') if draft.assessment else None})
        except Exception as error:
            record.update(status='error', error_type=type(error).__name__)
        records.append(record)
        write(output / 'captures.json', records)
    return records


def semantic_scores(dataset, records, provider, model, timeout):
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    from eval.case_assessment.evaluate_ragas import make_judge, metric_rows, run_metric
    indexed = {r['case_id']: r for r in records}
    result = {}
    for channel in ('report', 'answer'):
        rows, ids = [], []
        for case in dataset['cases']:
            record = indexed.get(case['case_id'])
            if not record or record.get('status') != 'complete' or record.get('case_digest') != digest(case):
                continue
            assessment = record['actual'].get('assessment')
            if assessment and assessment.get('operational_status') != 'OK':
                continue
            ids.append(case['case_id'])
            rows.append({'user_input': case['input']['query'], 'response': record['actual'][channel],
                         'reference': case['reference_' + channel],
                         'retrieved_contexts': [p['content'] for p in case['input']['passages']]})
        result[channel] = {}
        for metric in ('faithfulness', 'factual_correctness'):
            try:
                values = run_metric(metric_rows(rows, metric, False), metric, make_judge(provider, model, timeout), timeout) if rows else []
                if len(values) != len(ids):
                    raise ValueError('Judge result count mismatch')
                result[channel][metric] = {'scores': dict(zip(ids, values)), 'errors': getattr(values, 'errors', [])}
            except Exception as error:
                result[channel][metric] = {'scores': dict.fromkeys(ids), 'errors': [{'error_type': type(error).__name__}]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=HERE / 'golden.json')
    parser.add_argument('--output-dir', type=Path, default=HERE / 'results/latest')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--allow-draft', action='store_true')
    parser.add_argument('--captures', type=Path)
    parser.add_argument('--judge', choices=['mistral', 'openai', 'gemini', 'openrouter', 'deepseek'])
    parser.add_argument('--judge-model')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    validate(dataset)
    if args.validate_only:
        print(f"Valid: {len(dataset['cases'])} draft cases; source hashes match")
        return 0
    if not args.allow_draft and any(c['review_status'] != 'approved' for c in dataset['cases']):
        parser.error('Labels require review; use --allow-draft for exploratory evaluation')
    if args.live == bool(args.captures):
        parser.error('Choose exactly one of --live or --captures')
    if args.judge and not args.judge_model:
        parser.error('--judge-model is required with --judge')
    records = asyncio.run(capture(dataset, args.output_dir, args.timeout)) if args.live else json.loads(args.captures.read_text())
    indexed = {r['case_id']: r for r in records}
    if len(indexed) != len(records) or set(indexed) - {c['case_id'] for c in dataset['cases']}:
        parser.error('Duplicate or unknown capture IDs')
    scores = [score_case(c, indexed.get(c['case_id'])) for c in dataset['cases']]
    scored = [s for s in scores if s['passed'] is not None]
    summary = {'dataset_sha256': digest(dataset), 'scope': dataset['scope'], 'review_status': dataset['review_status'],
               'total': len(scores), 'scored': len(scored), 'missing_or_failed': len(scores) - len(scored),
               'passed': sum(s['passed'] for s in scored),
               'pass_rate': sum(s['passed'] for s in scored) / len(scored) if scored else None,
               'judge': args.judge, 'judge_model': args.judge_model}
    semantic = semantic_scores(dataset, records, args.judge, args.judge_model, args.timeout) if args.judge else None
    if semantic is not None:
        write(args.output_dir / 'semantic_scores.json', semantic)
        summary['semantic_complete'] = all(len(m['scores']) == len(scores) and all(v is not None for v in m['scores'].values()) for channel in semantic.values() for m in channel.values())
    write(args.output_dir / 'scores.json', scores)
    write(args.output_dir / 'summary.json', summary)
    lines = ['# Assessment and answer quality', '', f"Scope: {dataset['scope']}", '',
             f"Draft labels. Scored {len(scored)}/{len(scores)}; passed {summary['passed']}/{len(scored)}.", '',
             '| Case | Status | Failed checks |', '| --- | --- | --- |']
    for score in scores:
        lines.append(f"| {score['case_id']} | {score['status']} | {', '.join(k for k, v in score['checks'].items() if not v)} |")
    (args.output_dir / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(summary, indent=2))
    return 0 if len(scored) == len(scores) and all(s['passed'] for s in scored) and summary.get('semantic_complete', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
