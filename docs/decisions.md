# Design decisions

## Chunking

Documents are markdown, so chunking is structure-aware. Each heading defines a
**parent** section; the parent is split into overlapping **child** windows (~800
chars, 100 overlap). Children are embedded and indexed for precise retrieval;
each child carries its parent's full text and section title so synthesis can
reason over the complete section, not a fragment. This fixes the classic failure
where a table or a multi-sentence exception list gets split across chunks.

## Hybrid over pure vector

Pure vector search misses exact identifiers and rare terms. Hybrid
(keyword + vector, fused with reciprocal rank fusion) recovers exact matches
while keeping semantic recall.

## Retrieval modes and reranking

Retrieval is pluggable (`ragpipeline/strategies.py`):

- `vector` — pure vector similarity.
- `hybrid` — keyword + vector (RRF).
- `hybrid_rerank` — hybrid candidates, then an LLM reranker reorders the parent
  sections before synthesis.

The reranker uses the chat model to rank candidate parents (not a separate
cross-encoder), so no extra Azure service is required. `eval/compare_modes.py`
scores all three modes on the golden set so the choice is measured, not assumed.

## Citations

The system prompt requires inline `[source <id>]` citations and refuses to
answer when the context is insufficient. This is what makes the groundedness
evaluator meaningful and keeps hallucinations auditable.

## Auth

Local development uses API keys for speed. Production should use Microsoft
Entra ID with managed identity and RBAC; see the landing-zone project.
