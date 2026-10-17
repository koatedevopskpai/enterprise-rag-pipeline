from copy import deepcopy
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'eval'))
from fresh_gate import validate
from fresh_quality import execute, expectation

CASES = [{'query': 'What is the refund deadline?'}]
CONFIG = {'mode': 'hybrid', 'index_revision': 'fixture-only'}


def fixture():
    expected = expectation(CASES, CONFIG, 'test-run')
    def application(query, mode):
        return {'answer': 'Refund within 30 days.', 'sources': [{'id': 'refund', 'content': 'Refund within 30 days.'}]}
    judges = {name: (lambda query, answer, context, name=name: {name: 5.0})
              for name in ['relevance', 'groundedness', 'coherence', 'fluency']}
    report = execute(CASES, CONFIG, expected, application, judges)
    return expected, report


def live_marked_fixture():
    expected, report = fixture()
    # Validator contract fixture only, not actual Azure execution evidence.
    report['execution_mode'] = 'live_azure_application'
    return expected, report


def test_offline_adapter_cannot_satisfy_live_release():
    expected, report = fixture()
    assert 'unsupported schema or execution mode' in validate(report, expected)


def test_complete_validator_contract_fixture_passes():
    expected, report = live_marked_fixture()
    assert validate(report, expected) == []


@pytest.mark.parametrize('field', ['source_revision', 'configuration_sha256', 'dataset_sha256', 'corpus_sha256', 'run_id'])
def test_stale_or_other_candidate_is_rejected(field):
    expected, report = live_marked_fixture()
    report['provenance'] = {**report['provenance'], field: 'other'}
    assert validate(report, expected)


@pytest.mark.parametrize('change', [
    {'rows': []}, {'rows': [None]}, {'status': 'blocked'}, {'provenance': None},
    {'created_at_utc': 'invalid'}, {'metrics': None},
])
def test_missing_or_malformed_report_cannot_pass(change):
    expected, report = live_marked_fixture()
    report.update(change)
    assert validate(report, expected)


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), 0, 6, '5'])
def test_invalid_scores_cannot_pass(value):
    expected, report = live_marked_fixture()
    report['rows'][0]['scores']['groundedness'] = value
    assert validate(report, expected)


def test_old_report_and_changed_aggregate_fail():
    expected, report = live_marked_fixture()
    report['created_at_utc'] = (datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    assert validate(report, expected)
    expected, report = live_marked_fixture()
    report['metrics']['relevance'] = 4.5
    assert validate(report, expected)


def test_changed_application_output_reaches_the_judge():
    captured = []
    def judge(query, answer, context):
        captured.append(answer)
        return {'groundedness': 1 if '999' in answer else 5}
    expected = expectation(CASES, CONFIG, 'test-run')
    judges = {name: (lambda q, a, c, name=name: {name: 5}) for name in ['relevance', 'coherence', 'fluency']}
    judges['groundedness'] = judge
    for answer in ['Refund within 30 days.', 'Refund within 999 days.']:
        report = execute(CASES, CONFIG, expected,
                         lambda q, mode: {'answer': answer, 'sources': [{'content': 'Refund within 30 days.'}]}, judges)
        report['execution_mode'] = 'live_azure_application'
        assert bool(validate(report, expected)) == ('999' in answer)
    assert captured == ['Refund within 30 days.', 'Refund within 999 days.']


def test_judge_exception_is_an_explicit_failed_row():
    expected = expectation(CASES, CONFIG, 'test-run')
    def broken(*args):
        raise TimeoutError('private provider text')
    report = execute(CASES, CONFIG, expected,
                     lambda q, mode: {'answer': 'answer', 'sources': [{'content': 'context'}]},
                     {name: broken for name in ['relevance', 'groundedness', 'coherence', 'fluency']})
    assert report['rows'][0]['errors']['evaluation'] == 'TimeoutError'
    assert validate(report, expected)
