"""Opt-in Azure candidate smoke evaluation. Does not provision infrastructure."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fresh_gate import FLOORS, METRICS, validate


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expectation(cases, configuration, run_id, revision=None):
    revision = revision or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    corpus = [(p.relative_to(ROOT).as_posix(), digest(p.read_bytes()))
              for p in sorted((ROOT/'data').rglob('*.md'))]
    if not corpus:
        raise ValueError('no versioned source corpus')
    return {'source_revision': revision, 'run_id': run_id, 'case_count': len(cases),
            'queries': [case['query'] for case in cases],
            'configuration_sha256': digest(json.dumps(configuration, sort_keys=True).encode()),
            'dataset_sha256': digest(json.dumps(cases, sort_keys=True).encode()),
            'corpus_sha256': digest(json.dumps(corpus).encode())}


def execute(cases, configuration, expected, answer_fn, judges, execution_mode='offline_test_adapter'):
    report = {'schema_version': 1, 'execution_mode': execution_mode, 'status': 'completed',
              'created_at_utc': datetime.now(timezone.utc).isoformat(), 'provenance': expected,
              'configuration': configuration, 'policy_floors': FLOORS, 'rows': [], 'metrics': {}}
    for case in cases:
        row = {'query': case['query'], 'answer': None, 'sources': [], 'scores': {}, 'errors': {}}
        try:
            response = answer_fn(case['query'], mode=configuration['mode'])
            row['answer'] = response['answer']
            row['sources'] = response['sources']
            context = '\n\n'.join(d.get('parent_content') or d.get('content', '') for d in response['sources'])
            for name in METRICS:
                raw = judges[name](case['query'], row['answer'], context)
                value = raw.get(name, raw.get('gpt_'+name)) if isinstance(raw, dict) else None
                if not isinstance(value, (float, int)) or isinstance(value, bool):
                    raise ValueError('missing or nonnumeric evaluator score')
                import math
                if not math.isfinite(value):
                    raise ValueError('non-finite evaluator score')
                row['scores'][name] = value
        except Exception as exc:
            row['errors']['evaluation'] = type(exc).__name__
        report['rows'].append(row)
    for metric in METRICS:
        scores = [row['scores'].get(metric) for row in report['rows']]
        report['metrics'][metric] = statistics.fmean(scores) if scores and all(v is not None for v in scores) else None
    return report


def azure_adapters():
    from ragpipeline.pipeline import answer
    from ragpipeline.auth import openai_client
    from ragpipeline.inference_budget import run_inference
    client = openai_client()
    cache = {}
    def evaluate_all(query, response, context):
        identity = (query, response, context)
        if identity not in cache:
            result = run_inference('judge', client.chat.completions.create,
                model=os.environ['EVAL_DEPLOYMENT_NAME'], temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': 'Score the generated answer using only the question and supplied context. Return JSON with integer scores 1-5 for relevance, groundedness, coherence and fluency. 5 is best. Unsupported facts, changed limits or contradictions must lower groundedness. Do not reward fluent invented statements. Return only the four scores.'},
                    {'role': 'user', 'content': json.dumps({'question': query, 'generated_answer': response, 'context': context})},
                ])
            if result.choices[0].finish_reason != 'stop':
                raise ValueError('incomplete judge output')
            cache[identity] = json.loads(result.choices[0].message.content)
        return cache[identity]
    def wrap(name):
        return lambda query, response, context: {name: evaluate_all(query,response,context).get(name)}
    return answer, {name: wrap(name) for name in METRICS}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--index-revision', required=True, help='Identity of freshly ingested index snapshot; operator assertion')
    ap.add_argument('--max-cases', type=int, default=3)
    ap.add_argument('--fault-inject-unsupported-answer', action='store_true')
    args = ap.parse_args()
    if not 1 <= args.max_cases <= 3:
        ap.error('this smoke path allows 1-3 cases; larger B01 remains deferred')
    if not args.index_revision.strip():
        ap.error('index revision must not be empty')
    output = Path(args.output_dir)
    if output.exists():
        ap.error('use a fresh output directory to avoid stale result reuse')
    output.mkdir(parents=True)
    expected = None
    try:
        if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
            raise ValueError('candidate checkout must be clean before live inference')
        keys = ['AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_API_KEY', 'EVAL_DEPLOYMENT_NAME', 'SEARCH_ENDPOINT', 'SEARCH_KEY', 'SEARCH_INDEX_NAME', 'MODEL_DEPLOYMENT_NAME', 'EMBEDDING_DEPLOYMENT_NAME']
        if any(not os.getenv(key) for key in keys):
            raise ValueError('required Azure configuration missing')
        cases = [json.loads(line) for line in (ROOT/'eval/golden_set.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()][:args.max_cases]
        configuration = {key: os.getenv(key) for key in ['EVAL_DEPLOYMENT_NAME', 'MODEL_DEPLOYMENT_NAME', 'EMBEDDING_DEPLOYMENT_NAME', 'EMBEDDING_DIMENSIONS', 'SEARCH_INDEX_NAME', 'RETRIEVE_TOP_K', 'CHUNK_SIZE', 'CHUNK_OVERLAP', 'AZURE_OPENAI_API_VERSION']}
        configuration.update(mode='hybrid', index_revision=args.index_revision,
                             evaluator_identity='azure-openai-custom-four-score-v1', output_token_limit=512,
                             endpoint_hashes={key: digest(os.environ[key].encode()) for key in ['SEARCH_ENDPOINT', 'AZURE_OPENAI_ENDPOINT']},
                             fault_injected=args.fault_inject_unsupported_answer)
        expected = expectation(cases, configuration, str(uuid.uuid4()))
        # Written independently before inference; the gate does not trust the
        # report to define its own expected candidate or run identity.
        (output/'expected.json').write_text(json.dumps(expected, indent=2), encoding='utf-8')
        answer_fn, judges = azure_adapters()
        if args.fault_inject_unsupported_answer:
            original = answer_fn
            def faulty(query, mode):
                result = original(query, mode=mode)
                return {**result, 'answer': 'Every item is refundable without exception and all limits are unlimited.'}
            answer_fn = faulty
        from contextlib import nullcontext
        from ragpipeline.inference_budget import InferenceBudget, budget_context, current_budget
        existing = current_budget()
        guard = nullcontext() if existing is not None else budget_context(InferenceBudget(output/'usage.json'))
        with guard:
            report = execute(cases, configuration, expected, answer_fn, judges, execution_mode='live_azure_application')
        failures = validate(report, expected)
        report['gate_failures'] = failures
    except Exception as exc:
        report = {'schema_version': 1, 'status': 'blocked', 'execution_mode': 'live_azure_application',
                  'error_type': type(exc).__name__, 'provenance': expected, 'rows': []}
        failures = ['Azure evaluation did not complete']
    (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('Fresh candidate evaluation failed' if failures else 'Fresh candidate evaluation passed for smoke sample')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
