# enterprise-rag-pipeline

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

### Retrieval mode comparison (measured)

Hit@5 / MRR over the final 5 candidates (rerank pool = top 20 parents), 80
synthetic docs across four 20-query sets:

| Query set | bm25 | vector | hybrid | hybrid_rerank |
|---|---|---|---|---|
| Bare reference codes | 1.00 / 1.00 | 0.95 / 0.95 | 0.90 / 0.90 | 0.90 / 0.90 |
| Code + context | 1.00 / 1.00 | 0.95 / 0.95 | 0.95 / 0.95 | 0.90 / 0.90 |
| Paraphrase (limit N) | 1.00 / 1.00 | 0.90 / 0.70 | 0.95 / 0.93 | 0.90 / 0.90 |
| Ambiguous topic | 0.40 / 0.10 | 0.35 / 0.11 | 0.40 / 0.12 | 0.40 / 0.12 |

Per-query latency (p50, dev box): **bm25 ~0.6 s, vector ~1.3 s, hybrid ~1.4 s,
hybrid_rerank ~2.4 s.**

Interpretation: lexical/identifier queries are a **BM25** win; paraphrase-style
queries are a **hybrid** win over vector (MRR 0.93 vs 0.70) for ~80 ms extra; the
LLM **reranker** added ~1 s and no recall. Ambiguous queries defeat all four.
Synthetic near-duplicate corpus, and small sample — an illustrative validation,
not a proof benchmark. See the blog post for the full per-question numbers.

### Reranker follow-up (semantic + crowded)

Built with `scripts/generate_eval_corpus.py --corpus semantic|crowded`
(40 docs, 20 queries each). Key metrics:

| Set | bm25 | vector | hybrid | hybrid_rerank |
|---|---|---|---|---|
| Semantic (low overlap) H@1 | 0.05 | 0.25 | 0.15 | **0.70** |
| Semantic (low overlap) H@5 | 0.10 | 0.55 | 0.45 | **0.95** |
| Crowded H@5 | 0.10 | 0.15 | 0.10 | 0.10 |
| Crowded H@1 | 0.05 | 0.00 | 0.00 | 0.00 |

The **reranker wins decisively on semantic paraphrases** (H@1 0.70 vs 0.25 for
vector) — the answer is in the pool but mis-ranked, which is the reranker's
purpose-built case. On **crowded near-duplicates** it can't help: the answer
leaves the top-20 candidate window for every mode. Full tables in the blog
(series post 3).

**Interpretation boundary:** the tables describe different small synthetic
query sets and do not establish one universally best strategy. At a fixed top-k,
fusion can displace a relevant vector result; hybrid is not guaranteed to retain
vector recall. Reranking can improve ordering when the relevant document is in
the candidate pool, but cannot recover a document excluded from that pool. These
published results have not been rerun for this wording correction.

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
