# enterprise-rag-pipeline

> **Reviewing this?** Start at [EVIDENCE.md](EVIDENCE.md) — a short index of what
> the project is, the strongest measured result, how to reproduce it, and what it
> does not establish.

Reference implementation of Retrieval-Augmented Generation over enterprise documents:
hybrid retrieval (keyword + vector + RRF), citation-prompted answers, and
an offline threshold check of a saved evaluation report. Built on Microsoft Foundry
(Azure OpenAI + Azure AI Search).

## Status

Runnable RAG pipeline with parent-child chunking, pluggable retrieval
(vector / hybrid / LLM rerank), evaluation harness, and a deployable FastAPI
service with Application Insights tracing.

## Architecture

```
                 +-------------------+
  documents ---> | ingest: chunk     |
                 +---------+---------+
                           |
                 +---------v---------+      +---------------------+
                 | embed (AOAI)      |----->| Azure AI Search     |
                 +-------------------+      |  - content (text)   |
                                            |  - content_vector   |
                                            +----------+----------+
                                                       |
  question --------------------------------------------+-----> hybrid retrieve
                                                              (BM25 + vector + RRF)
                                                       |
                                            +----------v----------+
                                            | synthesize          |
                                            |  grounded + cites   |
                                            +----------+----------+
                                                       |
                                                  answer + sources
```

## What it demonstrates

- Ingestion with structure-aware **parent-child chunking** (children for retrieval,
  parents for synthesis)
- Azure AI Search index design (searchable fields + HNSW vector profile)
- Hybrid retrieval with reciprocal rank fusion, deduplicated to parent sections
- Grounded synthesis with source citations including section titles
- Automated evaluation with groundedness and relevance evaluators
- Infrastructure as code and a one-command teardown

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

az login
powershell -ExecutionPolicy Bypass -File .\infra\provision.ps1 -WriteEnv
python -m ragpipeline ingest            # add --recreate after an index schema change
python -m ragpipeline ask "What does the refund policy say about exceptions?"
pytest

powershell -ExecutionPolicy Bypass -File .\infra\teardown.ps1
```

## Retrieval modes

`python -m ragpipeline ask "<question>" --mode <mode>`

| Mode | Strategy |
|---|---|
| `vector` | pure vector similarity |
| `hybrid` | keyword + vector (RRF), default |
| `hybrid_rerank` | hybrid candidates re-ranked by the LLM before synthesis |

Compare all three on the golden set:
```powershell
.\.venv\Scripts\python.exe eval\compare_modes.py
```
Reports retrieval **hit-rate** and **MRR** (deterministic metric calculations) plus
relevance and groundedness. Retrieval still calls Azure Search and embeddings;
`hybrid_rerank` also calls a model. `SKIP_LLM_EVAL=1` skips answer-quality judges,
not all billable services. This is not an offline or guaranteed-free command. Use
`GOLDEN_LIMIT=N` to cap the number of questions. Results are written to
`eval/comparison.json`.

## Evaluation results

`eval/evaluate_quality.py` scores relevance, groundedness, coherence, and
fluency over the golden set (`eval/quality_report.{json,md}`).
`eval/gate.py` checks thresholds against the supplied report. The current
evaluation workflow checks `eval/quality_report.json` if present and skips if it
is absent. It does not regenerate candidate application answers or prove a fresh
quality-gated release. The table below is a previously committed 16-question
report, not a new run from this documentation change.

| Metric | Mean (hybrid) | Threshold |
|---|---|---|
| relevance | 4.75 | >= 3.0 |
| groundedness | 5.00 | >= 3.0 |
| coherence | 4.06 | >= 3.0 |
| fluency | 3.06 | >= 3.0 |

Live deployment latency (Container Apps + Application Insights) and the KQL
queries used are in `docs/observability.md`.

### Retrieval comparison: committed artifact

The currently committed [comparison report](eval/comparison.json) contains 20
queries per strategy. Its expected source IDs use the `crowd_` prefix. It records
these results (rounded here; full precision remains in JSON):

| Strategy | Hit@1 | Hit@5 | MRR | nDCG@5 | Questions |
|---|---|---|---|---|---|
| bm25 | 0.05 | 0.10 | 0.0750 | 0.0815 | 20 |
| vector | 0.00 | 0.15 | 0.0600 | 0.0824 | 20 |
| hybrid | 0.00 | 0.10 | 0.0267 | 0.0443 | 20 |
| hybrid_rerank | 0.00 | 0.10 | 0.0267 | 0.0443 | 20 |

This artifact reports null relevance/groundedness fields, so it is retrieval
ranking evidence only. It does not establish generated-answer quality. No new
retrieval, model or cloud run was made for this documentation correction.

Earlier README tables reported different synthetic query sets, including an MRR
comparison of 0.93 versus 0.70. Those figures are not corroborated by this saved
artifact, and corresponding versioned per-run reports were not established in
this review. They are removed from the headline evidence pending provenance or a
controlled rerun; the saved report must not be relabelled as that earlier run.
The historical blog draft also needs its own evidence before publication.

At a fixed top-k, fusion can displace a relevant vector result. Hybrid is not
guaranteed to retain vector recall. Reranking cannot recover a document excluded
from its candidate pool. Compare strategies on the same versioned query set,
including failures and latency, before selecting a default for another workload.

## Cost

See `docs/cost.md`. Uses gpt-4.1-mini + text-embedding-3-large and an Azure AI
Search Free tier; the figures are historical estimates, not a current spend ceiling. Run
`infra/teardown.ps1` when finished.

## Deploy

A FastAPI service (`app/main.py`) wraps the pipeline and emits OpenTelemetry
traces to Application Insights when configured. Configuration is not proof of a
current deployment or achieved service level. Build and deploy with `azd up` (Container Apps,
scale-to-zero). See `docs/deployment.md`.

## Limitations

- Parent-child chunking with fixed child window size; heading-based parents.
- Single index, English only.
- API-key auth for local dev; managed identity (Entra ID) is supported when keys
  are absent.

## License

MIT (see LICENSE).

## Fresh candidate quality gate (R01)

The fresh runner binds evaluated application answers to candidate provenance.
A three-question Azure Search Free smoke baseline passed; a controlled unsupported
answer failed. Revision/configuration/run mismatch, stale evidence and a missing
score also blocked. This uses a custom Azure OpenAI judge with provisional floors,
not a broad benchmark. Temporary resources were deleted and absence verified.
See [R01 method, results and limits](docs/R01.md). Historical saved reports do not
satisfy a new release gate. Independent review and remote CI remain pending.
