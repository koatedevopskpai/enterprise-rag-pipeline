from types import SimpleNamespace
import json
import pytest

from ragpipeline.inference_budget import InferenceBudget, budget_context, run_inference


def receipt(**kwargs):
    return SimpleNamespace(model='fixture-model', usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20))


def test_call_cap_blocks_before_transport_and_records_usage(tmp_path):
    budget = InferenceBudget(tmp_path/'ledger.json', max_calls=1)
    seen = []
    def transport(**kwargs):
        seen.append(kwargs)
        return receipt()
    with budget_context(budget):
        run_inference('generation', transport, model='fixture', messages=[])
        with pytest.raises(RuntimeError, match='allowance exhausted'):
            run_inference('generation', transport, model='fixture', messages=[])
    assert len(seen) == 1
    assert seen[0]['max_tokens'] == 512
    result = json.loads((tmp_path/'ledger.json').read_text())
    assert result['records'][0]['prompt_tokens'] == 100


def test_budget_failure_does_not_make_request(tmp_path):
    budget = InferenceBudget(tmp_path/'ledger.json', reservation_limit_usd=0)
    with budget_context(budget), pytest.raises(RuntimeError, match='allowance exhausted'):
        run_inference('judge', lambda **kw: pytest.fail('must not call provider'), model='fixture')


def test_failed_attempt_is_reserved_without_private_exception_text(tmp_path):
    budget = InferenceBudget(tmp_path/'ledger.json')
    def broken(**kwargs):
        raise TimeoutError('private error contents')
    with budget_context(budget), pytest.raises(TimeoutError):
        run_inference('embedding', broken, model='fixture', input=['fixture'])
    text = (tmp_path/'ledger.json').read_text()
    assert 'private error contents' not in text
    result = json.loads(text)
    assert result['reserved_usd'] > 0
    assert result['records'][0]['status'] == 'failed'


def test_without_opt_in_context_existing_application_contract_is_unchanged():
    kwargs = []
    def transport(**arguments):
        kwargs.append(arguments)
        return 'fixture'
    assert run_inference('generation', transport, model='fixture') == 'fixture'
    assert kwargs == [{'model': 'fixture'}]
