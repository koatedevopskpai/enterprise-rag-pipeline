# enterprise-rag-pipeline

Production-style Retrieval-Augmented Generation over enterprise documents:
hybrid retrieval (keyword + vector + RRF), grounded answers with citations, and
an automated groundedness/relevance evaluation gate. Built on Microsoft Foundry
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
Reports retrieval **hit-rate** and **MRR** (deterministic, no LLM calls) plus
relevance and groundedness. Set `SKIP_LLM_EVAL=1` for a fast, free retrieval-only
run, and `GOLDEN_LIMIT=N` to cap the number of questions. Results are written to
`eval/comparison.json`.

## Evaluation results

`eval/evaluate_quality.py` scores relevance, groundedness, coherence, and
fluency over the golden set (`eval/quality_report.{json,md}`).
`eval/gate.py` enforces thresholds for CI.

| Metric | Mean (hybrid) | Threshold |
|---|---|---|
| relevance | 4.75 | >= 3.0 |
| groundedness | 5.00 | >= 3.0 |
| coherence | 4.06 | >= 3.0 |
| fluency | 3.06 | >= 3.0 |

Live deployment latency (Container Apps + Application Insights) and the KQL
queries used are in `docs/observability.md`.

### Retrieval mode comparison (the honest result)

| Corpus | vector | hybrid | hybrid_rerank |
|---|---|---|---|
| 16 curated docs, 16 questions | 1.00 | 1.00 | 1.00 |
| 80 synthetic docs, code + context | 0.95 | 0.95 | 0.95 |
| 80 synthetic docs, bare codes | 0.95 | 0.95 | 0.95 |

*Metric: hit-rate@5 and MRR over the final 5 candidates (rerank pool = top 20
parents). MRR equaled hit-rate in every row — recovered sources were always rank
1 — so the metric is saturated before the reranker runs. This is an illustrative
validation run, not a large-N proof benchmark.*

**Finding:** on our corpora the modes tie. `text-embedding-3-large` is strong
enough that dense retrieval already recovers the needle — even random
identifiers in near-duplicate documents. Hybrid is a safe default (it never
recalls less than vector), and the LLM reranker changes *ordering* but not
*recall*, because MRR was already saturated. Reranking only pays off when
candidate ranking, not recall, is the bottleneck. The harness
(`eval/compare_modes.py`, `scripts/generate_eval_corpus.py`) is included so the
experiment can be repeated on your data.

## Cost

See `docs/cost.md`. Uses gpt-4.1-mini + text-embedding-3-large and an Azure AI
Search Free tier; the whole project runs for a few dollars. Run
`infra/teardown.ps1` when finished.

## Deploy

A FastAPI service (`app/main.py`) wraps the pipeline and emits OpenTelemetry
traces to Application Insights. Build and deploy with `azd up` (Container Apps,
scale-to-zero). See `docs/deployment.md`.

## Limitations

- Parent-child chunking with fixed child window size; heading-based parents.
- Single index, English only.
- API-key auth for local dev; managed identity (Entra ID) is supported when keys
  are absent.

## License

MIT (see LICENSE).
