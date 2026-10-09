# Architecture

## Components

- Ingestion: reads markdown from `data/sample_docs`, splits by heading into
  parent sections, then into overlapping child chunks (parent-child chunking).
- Embeddings: gpt embeddings via Azure OpenAI (`text-embedding-3-large`, 3072 dims).
- Index: Azure AI Search index with a searchable `content` field and an
  `content_vector` field backed by an HNSW profile.
- Retrieval: pluggable strategies (`vector`, `hybrid`, `hybrid_rerank`). Hybrid
  uses keyword + vector (RRF); `hybrid_rerank` reorders parent sections with an
  LLM before synthesis.
- Synthesis: grounded answer generation with inline source citations (including
  section titles).
- Evaluation: groundedness and relevance evaluators over a golden set.

## Data flow

1. `python -m ragpipeline ingest`
   - create/update index
   - load documents -> chunk -> embed -> upload
2. `python -m ragpipeline ask "<question>"`
   - embed question
   - hybrid search (keyword + vector, fused by RRF)
   - synthesize a grounded answer with `[source <id>]` citations
3. `python eval/run_eval.py`
   - answer each golden question
   - score groundedness and relevance
   - write `eval/report.json`

## Deployment

`infra/main.bicep` provisions an AI Services account with two model
deployments and an Azure AI Search service on the free tier. `infra/azure.yaml`
enables `azd up`. `infra/teardown.ps1` removes everything.
