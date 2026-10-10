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
