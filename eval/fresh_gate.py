"""Validate a fresh candidate report; archived quality_report.json is insufficient."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics

METRICS = ('relevance', 'groundedness', 'coherence', 'fluency')
FLOORS = {'relevance': 4.0, 'groundedness': 4.0, 'coherence': 3.0, 'fluency': 3.0}


def validate(report, expected, now=None, max_age_seconds=3600):
    failures = []
    if not isinstance(expected, dict) or not isinstance(expected.get('case_count'), int) or isinstance(expected.get('case_count'), bool) or expected['case_count'] <= 0:
        return ['malformed expectation manifest']
    if not isinstance(report, dict):
        return ['malformed report']
    provenance = report.get('provenance')
    provenance = provenance if isinstance(provenance, dict) else {}
    for field in ['source_revision', 'configuration_sha256', 'dataset_sha256', 'corpus_sha256', 'run_id']:
        if not expected.get(field) or provenance.get(field) != expected[field]:
            failures.append('provenance mismatch: ' + field)
    if report.get('schema_version') != 1 or report.get('execution_mode') != 'live_azure_application':
        failures.append('unsupported schema or execution mode')
    if report.get('status') != 'completed':
        failures.append('evaluation did not complete')
    try:
        created = datetime.fromisoformat(report['created_at_utc'])
        age = ((now or datetime.now(timezone.utc)) - created).total_seconds()
        if not 0 <= age <= max_age_seconds:
            failures.append('report outside freshness window')
    except (KeyError, ValueError, TypeError):
        failures.append('invalid report time')
    rows = report.get('rows')
    if not isinstance(rows, list) or not rows or len(rows) != expected.get('case_count'):
        return failures + ['missing or incomplete case set']
    if [r.get('query') if isinstance(r, dict) else None for r in rows] != expected.get('queries'):
        failures.append('case identity/order mismatch')
    values = {metric: [] for metric in METRICS}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f'malformed row: {index}')
            continue
        if row.get('errors') or not isinstance(row.get('answer'), str) or not row['answer'].strip() or not isinstance(row.get('sources'), list) or not row['sources']:
            failures.append(f'missing evidence or case error: {index}')
        sources = row.get('sources')
        if not isinstance(sources, list) or not any(isinstance(d, dict) and isinstance(d.get('parent_content') or d.get('content'), str) and (d.get('parent_content') or d.get('content')).strip() for d in sources):
            failures.append(f'missing source context: {index}')
        scores = row.get('scores')
        scores = scores if isinstance(scores, dict) else {}
        for metric in METRICS:
            value = scores.get(metric)
            valid = isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and 1 <= value <= 5
            if not valid:
                failures.append(f'invalid {metric}: {index}')
                continue
            values[metric].append(value)
            if value < 2:
                failures.append(f'critical per-case {metric}: {index}')
    for metric, floor in FLOORS.items():
        if len(values[metric]) != len(rows):
            continue
        mean = statistics.fmean(values[metric])
        metrics = report.get('metrics')
        reported = metrics.get(metric) if isinstance(metrics, dict) else None
        if not isinstance(reported, (int, float)) or isinstance(reported, bool) or not math.isfinite(reported) or not math.isclose(mean, reported, abs_tol=1e-8):
            failures.append('aggregate mismatch: ' + metric)
        if mean < floor:
            failures.append('mean below pilot floor: ' + metric)
    return failures


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', required=True)
    ap.add_argument('--expected', required=True, help='Fresh expectation manifest from this run, not from report metadata')
    args = ap.parse_args()
    try:
        report = json.loads(Path(args.report).read_text(encoding='utf-8'))
        expected = json.loads(Path(args.expected).read_text(encoding='utf-8'))
        failures = validate(report, expected)
    except (OSError, ValueError, TypeError) as exc:
        print('FRESH QUALITY BLOCKED:', type(exc).__name__)
        return 2
    print('FRESH QUALITY FAILED: ' + '; '.join(failures) if failures else 'FRESH QUALITY PASSED for recorded sample')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
