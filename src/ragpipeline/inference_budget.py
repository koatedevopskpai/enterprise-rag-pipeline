"""Opt-in, process-local usage guard for small controlled integration runs."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path

_active = ContextVar('inference_budget', default=None)


class InferenceBudget:
    def __init__(self, ledger, max_calls=30, reservation_limit_usd=2.0):
        self.ledger = Path(ledger)
        if self.ledger.exists():
            raise ValueError('choose a new usage ledger; previous calls must not be overwritten')
        self.max_calls = max_calls
        self.limit = reservation_limit_usd
        self.records = []

    def save(self):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps({
            'currency': 'USD', 'cost_basis': 'conservative allowance, NOT invoice or exact retail price',
            'allowance_per_million_tokens': {'chat_input': 2.0, 'chat_output': 10.0, 'embedding_input': 1.0},
            'reservation_limit_usd': self.limit, 'max_calls': self.max_calls,
            'reserved_usd': sum(r['reserved_usd'] for r in self.records),
            'conservative_usage_cost_usd': sum(r.get('conservative_usage_cost_usd', 0) for r in self.records),
            'records': self.records}, indent=2, allow_nan=False), encoding='utf-8')

    def call(self, kind, fn, kwargs):
        kwargs = dict(kwargs)
        if kind != 'embedding':
            kwargs['max_tokens'] = 512
        body = json.dumps(kwargs, default=str).encode('utf-8')
        if len(body) > 64000:
            raise RuntimeError('request exceeds input allowance')
        reserved = ((len(body)+256) * (1.0 if kind=='embedding' else 2.0) + (0 if kind=='embedding' else 5120)) / 1_000_000
        if len(self.records) >= self.max_calls or sum(r['reserved_usd'] for r in self.records)+reserved > self.limit:
            raise RuntimeError('inference allowance exhausted before provider call')
        record = {'kind': kind, 'deployment': kwargs.get('model'), 'reserved_usd': reserved,
                  'request_sha256': hashlib.sha256(body).hexdigest(), 'status': 'attempting'}
        self.records.append(record)
        self.save()
        try:
            response = fn(**kwargs)
            usage = response.usage
            prompt = usage.prompt_tokens
            completion = getattr(usage, 'completion_tokens', 0) or 0
            if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in [prompt, completion]):
                raise ValueError('missing or invalid usage')
            record.update(status='received', prompt_tokens=prompt, completion_tokens=completion,
                          resolved_model=getattr(response, 'model', None),
                          conservative_usage_cost_usd=(prompt*(1.0 if kind=='embedding' else 2.0)+completion*10.0)/1_000_000)
            return response
        except Exception as exc:
            record.update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            self.save()


@contextmanager
def budget_context(budget):
    token = _active.set(budget)
    try:
        yield budget
    finally:
        budget.save()
        _active.reset(token)


def current_budget():
    return _active.get()


def run_inference(kind, fn, **kwargs):
    budget = current_budget()
    return budget.call(kind, fn, kwargs) if budget is not None else fn(**kwargs)
