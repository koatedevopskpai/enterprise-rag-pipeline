# Evidence index

A reviewer's route through this repository. Everything here points at something
already in the repo or at a dated run — no claim is asserted without a location.

**Five-minute path:** this file → [Status](#what-it-is) → [strongest measured
result](#the-strongest-measured-result) → [how to reproduce](#how-to-reproduce) →
[what this does not establish](#what-this-does-not-establish).

---

## What it is

A reference implementation of Retrieval-Augmented Generation over enterprise
documents: hybrid retrieval (BM25 + vector + reciprocal rank fusion),
citation-prompted synthesis, a retrieval comparison harness, a provenance-bound
quality gate, and a deployable FastAPI service. Built on Azure OpenAI + Azure AI
Search.

| | |
|---|---|
| Scope | **Public reference build.** Self-funded, no customer deployment |
| Author | Koate Kpai — https://github.com/koatedevopskpai |
| Entry point | `app/main.py`, `src/ragpipeline/` |

## My contribution

Design and implementation of the retrieval layer and its evaluation:

- parent-child chunking (`src/ragpipeline/chunking.py`) — children retrieve,
  parents synthesise
- index design and HNSW vector profile (`src/ragpipeline/index.py`)
- the three retrieval strategies and rank fusion (`src/ragpipeline/strategies.py`,
  `eval/compare_modes.py`)
- the retrieval comparison and the quality gate
  (`eval/evaluate_quality.py`, `eval/gate.py`)
- the provenance-bound fresh candidate gate (`eval/fresh_quality.py`,
  `eval/fresh_gate.py`)

It is a reference build, not commercial delivery. Nothing here demonstrates
customer adoption, production scale or uptime.

---

## The strongest measured result

**Retrieval ranking, 20 queries per strategy**, from the committed artifact
[`eval/comparison.json`](eval/comparison.json):

| Strategy | Hit@1 | Hit@5 | MRR | nDCG@5 |
|---|---|---|---|---|
| bm25 | 0.05 | 0.10 | 0.0750 | 0.0815 |
| vector | 0.00 | 0.15 | 0.0600 | 0.0824 |
| hybrid | 0.00 | 0.10 | 0.0267 | 0.0443 |
| hybrid_rerank | 0.00 | 0.10 | 0.0267 | 0.0443 |

Read this as *ranking evidence only*. The artifact's relevance and groundedness
fields are `null`, so it says nothing about generated-answer quality. At 20
queries the differences between strategies are **not** statistically established.

**Answer quality, 16 questions**, from
[`eval/quality_report.json`](eval/quality_report.json) — a previously committed
run, not a new one:

| Metric | Mean (hybrid) | Threshold |
|---|---|---|
| relevance | 4.75 | ≥ 3.0 |
| groundedness | 5.00 | ≥ 3.0 |
| coherence | 4.06 | ≥ 3.0 |
| fluency | 3.06 | ≥ 3.0 |

**A live run worth naming (R01).** The actual application ingested **11 documents
into 41 chunks** in Azure AI Search, a three-question baseline scored **5/5** on
all four metrics, and a controlled unsupported-answer run failed at
**3.667 / 1.0 / 3.333 / 4.0** and was **blocked by the gate without changing
thresholds**. Method, provenance and limits: [`docs/R01.md`](docs/R01.md), raw
status in [`evidence/R01.md`](evidence/R01.md).

### A result I removed

The README previously headlined "hybrid MRR 0.93 vs vector 0.70". That figure is
not corroborated by the committed artifact, so it was replaced with the numbers
above and the discrepancy left visible in the README rather than quietly deleted.
Correcting a claim downward is part of the evidence trail, not a footnote to it.

---

## How to reproduce

**Offline, free, no cloud account** — this is what CI runs:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

The nightly-style offline baseline pins its own environment instead:

```bash
pip install -r requirements-offline.lock
pytest -p offline_guard tests -q      # no-network guard active
```

Offline baseline details: [`docs/OFFLINE_BASELINE.md`](docs/OFFLINE_BASELINE.md).
Test counts recorded in [`evidence/C03.md`](evidence/C03.md) and
[`evidence/R01.md`](evidence/R01.md).

**Live, billable** — needs an Azure account, and must be torn down:

```powershell
az login
powershell -ExecutionPolicy Bypass -File .\infra\provision.ps1 -WriteEnv
python -m ragpipeline ingest
python -m ragpipeline ask "What does the refund policy say about exceptions?"
python eval\compare_modes.py              # calls Azure Search + embeddings
powershell -ExecutionPolicy Bypass -File .\infra\teardown.ps1
```

`compare_modes.py` is **not** free: it calls Azure Search and the embedding
deployment. `SKIP_LLM_EVAL=1` skips the answer-quality judges, not all billable
services. Use `GOLDEN_LIMIT=N` to cap questions. Cost assumptions:
[`docs/cost.md`](docs/cost.md).

---

## One success trace, one failure

**Success.** `python -m ragpipeline ask "<question>"` answers with citations that
include section titles — the child chunk retrieved, the parent section supplied
to the model.

**Failure, and the recovery.** `hybrid` and `hybrid_rerank` score *identically*
(0.0267 MRR) because synchronous reranking cannot recover a document that never
entered the candidate pool, and at a fixed `top-k` fusion can displace a relevant
vector result. The honest recovery is to widen the candidate pool or prefer the
strategy the measured evidence supports — not to claim the reranker helped.

**Failure that is blocked by design.** R01's gate rejects stale, missing,
malformed, nonfinite or internally inconsistent evidence, and an unsupported
answer is blocked on per-case and mean checks. An offline adapter cannot satisfy a
live gate, which is verified rather than assumed.

---

## Decisions and trade-offs

| Decision | Where |
|---|---|
| Parent-child chunking, hybrid retrieval, Fusion vs rerank, and the rest | [`docs/decisions.md`](docs/decisions.md) |
| Fresh candidate gate: provenance, floors, and why limit ≠ work bound | [`docs/R01.md`](docs/R01.md) |
| Benchmark narrative, including what it does not show | [`docs/blog/retrieval-mode-benchmark.md`](docs/blog/retrieval-mode-benchmark.md) |
| Deploy, observability and cost | [`docs/deployment.md`](docs/deployment.md), [`docs/observability.md`](docs/observability.md), [`docs/cost.md`](docs/cost.md) |

---

## What this does not establish

- **Production scale.** The corpus is 11 sample documents; the query sets are 16
  and 20 questions.
- **Generated-answer quality at scale.** The retrieval artifact has null
  quality fields; the 16-question report is a saved run, not a fresh one.
- **Semantic ranking.** Free-tier availability is region-dependent; the R01 live
  run used a custom Azure OpenAI judge and does **not** report a reranked number.
- **That the comparisons transfer** to another corpus or language. Single index,
  English only, fixed child window size.
- **Commercial anything.** No customer, no uptime, no deployment currently live.

## Known weaknesses

- A result `LIMIT` is not a work bound — measured in the sibling
  `agentic-rag-hybrid` project, and the same reasoning applies to any cap applied
  after expansion.
- Hashes and revision identifiers establish **identity, not truth**: a runner must
  supply trusted expectations for a gate to mean anything.
- The evaluation workflow checks a committed report and skips when absent; it does
  not regenerate answers on every change, so a green workflow is not proof of a
  fresh quality-gated release.
